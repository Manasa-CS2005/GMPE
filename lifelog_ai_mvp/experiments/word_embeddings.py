"""Word-vector loading, semantic similarity, Word2Vec and prompt enrichment."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z'-]*")
SAMPLE_CORPUS = (
    "I kept a journal after a calm walk in the garden.",
    "A quiet walk helped me reflect on the day.",
    "My journal holds small memories and stories.",
    "I met a friend after class and shared a kind moment.",
    "The peaceful park made the afternoon feel calm.",
)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def load_text_vectors(path: str | Path) -> dict[str, np.ndarray]:
    """Read whitespace-separated word vectors (one token followed by floats)."""
    vectors: dict[str, np.ndarray] = {}
    dimensions: int | None = None
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            parts = line.strip().split()
            if not parts:
                continue
            if line_number == 1 and len(parts) == 2:
                try:
                    int(parts[0])
                    int(parts[1])
                except ValueError:
                    pass
                else:
                    continue
            try:
                values = np.asarray([float(value) for value in parts[1:]], dtype=float)
            except ValueError as error:
                raise ValueError(f"Invalid vector on line {line_number}.") from error
            if not parts[0] or values.size == 0:
                raise ValueError(f"Missing token or vector on line {line_number}.")
            if not np.all(np.isfinite(values)):
                raise ValueError(f"Vector contains non-finite values on line {line_number}.")
            if dimensions is None:
                dimensions = int(values.size)
            if values.size != dimensions:
                raise ValueError(f"Vector dimension mismatch on line {line_number}.")
            vectors[parts[0].lower()] = values
    if not vectors:
        raise ValueError("The vector file contains no word vectors.")
    return vectors


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0:
        return 0.0
    return float(np.dot(left, right) / denominator)


def most_similar(
    word: str, vectors: dict[str, np.ndarray], limit: int = 5
) -> list[tuple[str, float]]:
    query = word.lower()
    if query not in vectors:
        raise KeyError(f"No vector is available for {word!r}.")
    if limit < 1:
        raise ValueError("Similarity result limit must be positive.")
    return sorted(
        (
            (token, cosine_similarity(vectors[query], vector))
            for token, vector in vectors.items()
            if token != query
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]


def pca_2d(vectors: dict[str, np.ndarray]) -> dict[str, list[float]]:
    if len(vectors) < 2:
        raise ValueError("PCA visualization requires at least two words.")
    words = list(vectors)
    matrix = np.stack([vectors[word] for word in words])
    centered = matrix - matrix.mean(axis=0)
    left, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    components = left[:, :2] * singular_values[:2]
    if components.shape[1] == 1:
        components = np.pad(components, ((0, 0), (0, 1)))
    return {word: components[index].astype(float).tolist() for index, word in enumerate(words)}


def tsne_2d(
    vectors: dict[str, np.ndarray], seed: int = 7
) -> dict[str, list[float]]:
    if len(vectors) < 3:
        raise ValueError("t-SNE visualization requires at least three words.")
    from sklearn.manifold import TSNE

    words = list(vectors)
    matrix = np.stack([vectors[word] for word in words])
    perplexity = min(30.0, max(2.0, (len(words) - 1) / 3))
    coordinates = TSNE(
        n_components=2,
        init="pca",
        learning_rate="auto",
        perplexity=perplexity,
        random_state=seed,
    ).fit_transform(matrix)
    return {
        word: coordinates[index].astype(float).tolist()
        for index, word in enumerate(words)
    }


def save_embedding_plot(
    coordinates: dict[str, list[float]], destination: str | Path, title: str
) -> None:
    if not coordinates:
        raise ValueError("Cannot plot an empty embedding projection.")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 6))
    for word, point in coordinates.items():
        axis.scatter(point[0], point[1])
        axis.annotate(word, (point[0], point[1]))
    axis.set_title(title)
    figure.tight_layout()
    figure.savefig(destination, dpi=140)
    plt.close(figure)


class TinyWord2Vec:
    """Minimal skip-gram negative-sampling trainer for small teaching corpora."""

    def __init__(
        self,
        vector_size: int = 24,
        window: int = 2,
        negatives: int = 3,
        epochs: int = 30,
        learning_rate: float = 0.025,
        seed: int = 7,
    ) -> None:
        if min(vector_size, window, negatives, epochs) < 1 or learning_rate <= 0:
            raise ValueError("Word2Vec dimensions and training settings must be positive.")
        self.vector_size = vector_size
        self.window = window
        self.negatives = negatives
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.seed = seed

    def fit(self, sentences: Iterable[str]) -> dict[str, np.ndarray]:
        tokenized = [tokenize(sentence) for sentence in sentences]
        tokenized = [sentence for sentence in tokenized if sentence]
        if not tokenized:
            raise ValueError("Word2Vec training requires at least one token.")
        vocabulary = sorted({word for sentence in tokenized for word in sentence})
        indices = {word: index for index, word in enumerate(vocabulary)}
        counts = np.zeros(len(vocabulary), dtype=float)
        pairs: list[tuple[int, int]] = []
        for sentence in tokenized:
            encoded = [indices[word] for word in sentence]
            for center, center_id in enumerate(encoded):
                counts[center_id] += 1
                start = max(0, center - self.window)
                end = min(len(encoded), center + self.window + 1)
                pairs.extend(
                    (center_id, encoded[context])
                    for context in range(start, end)
                    if context != center
                )
        if not pairs:
            raise ValueError("Word2Vec corpus needs at least one context pair.")

        rng = np.random.default_rng(self.seed)
        input_vectors = rng.uniform(
            -0.5 / self.vector_size,
            0.5 / self.vector_size,
            size=(len(vocabulary), self.vector_size),
        )
        output_vectors = np.zeros_like(input_vectors)
        negative_distribution = counts**0.75
        negative_distribution /= negative_distribution.sum()

        for _ in range(self.epochs):
            rng.shuffle(pairs)
            for center_id, context_id in pairs:
                negative_ids = rng.choice(
                    len(vocabulary),
                    size=self.negatives,
                    replace=True,
                    p=negative_distribution,
                )
                target_ids = np.concatenate(([context_id], negative_ids))
                labels = np.zeros(len(target_ids))
                labels[0] = 1.0
                center_vector = input_vectors[center_id].copy()
                context_vectors = output_vectors[target_ids].copy()
                logits = np.clip(context_vectors @ center_vector, -20, 20)
                probabilities = 1 / (1 + np.exp(-logits))
                gradient = (probabilities - labels) * self.learning_rate
                input_vectors[center_id] -= gradient @ context_vectors
                np.add.at(
                    output_vectors,
                    target_ids,
                    -gradient[:, None] * center_vector[None, :],
                )
        return {
            word: (input_vectors[index] + output_vectors[index]).astype(np.float32)
            for word, index in indices.items()
        }


def enrich_prompt(
    prompt: str,
    vectors: dict[str, np.ndarray],
    limit: int = 3,
) -> tuple[str, list[str]]:
    """Append nearest known domain words without rewriting the original prompt."""
    if limit < 1:
        raise ValueError("Prompt enrichment limit must be positive.")
    query_words = list(dict.fromkeys(tokenize(prompt)))
    query_vectors = [vectors[word] for word in query_words if word in vectors]
    if not query_vectors:
        return prompt, []
    query_vector = np.mean(query_vectors, axis=0)
    original_words = set(query_words)
    suggestions = sorted(
        (
            (word, cosine_similarity(query_vector, vector))
            for word, vector in vectors.items()
            if word not in original_words
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]
    related = [word for word, _ in suggestions]
    if not related:
        return prompt, []
    enriched = f"{prompt.rstrip()} Related ideas: {', '.join(related)}."
    return enriched, related


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vectors",
        default=str(Path(__file__).parent / "sample_data" / "sample_vectors.txt"),
        help="Text word-vector file (sample vectors are illustrative, not pretrained).",
    )
    parser.add_argument("--word", default="journal")
    parser.add_argument("--prompt", default="Write a journal about a calm day.")
    parser.add_argument(
        "--plot-dir",
        help="Optional output directory for PCA and t-SNE visualization PNGs.",
    )
    args = parser.parse_args()
    vectors = load_text_vectors(args.vectors)
    enriched, related = enrich_prompt(args.prompt, vectors)
    word2vec_vectors = TinyWord2Vec(seed=7).fit(SAMPLE_CORPUS)
    comparison = {
        "original": args.prompt,
        "enriched": enriched,
        "added_terms": related,
        "added_term_count": len(related),
    }
    projections = {"pca": pca_2d(vectors)}
    if len(vectors) >= 3:
        projections["tsne"] = tsne_2d(vectors)
    if args.plot_dir:
        plot_directory = Path(args.plot_dir)
        plot_directory.mkdir(parents=True, exist_ok=True)
        for projection, coordinates in projections.items():
            save_embedding_plot(
                coordinates,
                plot_directory / f"{projection}.png",
                f"LifeLog word vectors — {projection.upper()}",
            )
    print(
        json.dumps(
            {
                "similar_words": most_similar(args.word, vectors),
                "trained_word2vec_similar": most_similar(
                    "journal", word2vec_vectors, limit=3
                ),
                "projections": projections,
                "prompt_comparison": comparison,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
