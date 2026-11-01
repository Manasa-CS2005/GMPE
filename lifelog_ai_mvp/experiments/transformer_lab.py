"""Toy causal Transformer, next-token training, and multimodal projection lab."""

from __future__ import annotations

import math

import torch
from torch import Tensor, nn
from torch.nn import functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, embedding_dim: int, heads: int) -> None:
        super().__init__()
        if heads < 1 or embedding_dim % heads:
            raise ValueError("Embedding dimension must be divisible by the head count.")
        self.embedding_dim = embedding_dim
        self.heads = heads
        self.head_dim = embedding_dim // heads
        self.query_key_value = nn.Linear(embedding_dim, embedding_dim * 3)
        self.output = nn.Linear(embedding_dim, embedding_dim)

    def forward(self, inputs: Tensor) -> Tensor:
        if inputs.ndim != 3:
            raise ValueError("Attention input must have shape (batch, sequence, embedding).")
        batch, sequence = inputs.shape[:2]
        query, key, value = self.query_key_value(inputs).chunk(3, dim=-1)

        def split_heads(tensor: Tensor) -> Tensor:
            return tensor.view(batch, sequence, self.heads, self.head_dim).transpose(1, 2)

        query, key, value = map(split_heads, (query, key, value))
        scores = (query @ key.transpose(-2, -1)) / math.sqrt(self.head_dim)
        causal_mask = torch.triu(
            torch.ones(sequence, sequence, dtype=torch.bool, device=inputs.device),
            diagonal=1,
        )
        weights = scores.masked_fill(causal_mask, float("-inf")).softmax(dim=-1)
        attended = weights @ value
        attended = attended.transpose(1, 2).contiguous().view(
            batch, sequence, self.embedding_dim
        )
        return self.output(attended)


class TransformerBlock(nn.Module):
    def __init__(self, embedding_dim: int, heads: int) -> None:
        super().__init__()
        self.attention_norm = nn.LayerNorm(embedding_dim)
        self.attention = CausalSelfAttention(embedding_dim, heads)
        self.feed_forward_norm = nn.LayerNorm(embedding_dim)
        self.feed_forward = nn.Sequential(
            nn.Linear(embedding_dim, embedding_dim * 4),
            nn.GELU(),
            nn.Linear(embedding_dim * 4, embedding_dim),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        inputs = inputs + self.attention(self.attention_norm(inputs))
        return inputs + self.feed_forward(self.feed_forward_norm(inputs))


class TinyTransformerLanguageModel(nn.Module):
    """A small decoder-only model illustrating next-token sequence modeling."""

    def __init__(
        self,
        vocabulary_size: int,
        embedding_dim: int = 32,
        heads: int = 4,
        layers: int = 2,
        max_sequence_length: int = 64,
    ) -> None:
        super().__init__()
        if min(vocabulary_size, embedding_dim, heads, layers, max_sequence_length) < 1:
            raise ValueError("Transformer dimensions must be positive.")
        self.max_sequence_length = max_sequence_length
        self.token_embedding = nn.Embedding(vocabulary_size, embedding_dim)
        self.position_embedding = nn.Embedding(max_sequence_length, embedding_dim)
        self.blocks = nn.ModuleList(
            TransformerBlock(embedding_dim, heads) for _ in range(layers)
        )
        self.norm = nn.LayerNorm(embedding_dim)
        self.language_head = nn.Linear(embedding_dim, vocabulary_size, bias=False)

    def forward(self, token_ids: Tensor) -> Tensor:
        if token_ids.ndim != 2:
            raise ValueError("Token input must have shape (batch, sequence).")
        _, sequence = token_ids.shape
        if sequence > self.max_sequence_length:
            raise ValueError("Token sequence exceeds the configured context length.")
        positions = torch.arange(sequence, device=token_ids.device)
        hidden = self.token_embedding(token_ids) + self.position_embedding(positions)
        for block in self.blocks:
            hidden = block(hidden)
        return self.language_head(self.norm(hidden))

    @torch.no_grad()
    def generate(self, prefix: Tensor, new_tokens: int = 8) -> Tensor:
        if new_tokens < 0:
            raise ValueError("Number of generated tokens cannot be negative.")
        if prefix.ndim != 2 or prefix.shape[1] == 0:
            raise ValueError("Generation prefix must be a non-empty (batch, sequence) tensor.")
        tokens = prefix
        for _ in range(new_tokens):
            context = tokens[:, -self.max_sequence_length :]
            next_logits = self(context)[:, -1, :]
            next_token = next_logits.argmax(dim=-1, keepdim=True)
            tokens = torch.cat((tokens, next_token), dim=1)
        return tokens


def next_token_loss(model: TinyTransformerLanguageModel, token_batch: Tensor) -> Tensor:
    if token_batch.ndim != 2 or token_batch.shape[1] < 2:
        raise ValueError("Next-token training needs a batch of sequences of length two or more.")
    inputs = token_batch[:, :-1]
    targets = token_batch[:, 1:]
    logits = model(inputs)
    return F.cross_entropy(
        logits.reshape(-1, logits.shape[-1]),
        targets.reshape(-1),
    )


def train_next_token(
    model: TinyTransformerLanguageModel,
    token_batch: Tensor,
    epochs: int = 1,
    learning_rate: float = 0.001,
) -> list[float]:
    """Train in place; call on broad text first and a small domain corpus second."""
    if epochs < 1 or learning_rate <= 0:
        raise ValueError("Training epochs and learning rate must be positive.")
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    history: list[float] = []
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = next_token_loss(model, token_batch)
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return history


class MultimodalProjector(nn.Module):
    """Project image features beside text tokens into one Transformer space."""

    def __init__(
        self, vocabulary_size: int, image_feature_dim: int, embedding_dim: int
    ) -> None:
        super().__init__()
        self.text = nn.Embedding(vocabulary_size, embedding_dim)
        self.image = nn.Linear(image_feature_dim, embedding_dim)

    def forward(self, token_ids: Tensor, image_features: Tensor) -> Tensor:
        if token_ids.ndim != 2 or image_features.ndim != 2:
            raise ValueError("Text IDs and image features must both be batched 2-D tensors.")
        if token_ids.shape[0] != image_features.shape[0]:
            raise ValueError("Text and image batches must have equal sizes.")
        text_tokens = self.text(token_ids)
        image_token = self.image(image_features).unsqueeze(1)
        return torch.cat((image_token, text_tokens), dim=1)
