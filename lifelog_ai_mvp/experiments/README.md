# LifeLog AI — Academic Experiments

These are standalone CS4204 teaching experiments, not production features. They
use synthetic or explicitly selected sample data. No production account data is
read by these scripts. The Hugging Face examples download model weights when
first run; choose a model and data source whose license and privacy terms are
appropriate.

## Setup

From `lifelog_ai_mvp`:

```powershell
python -m venv .venv-experiments
.\.venv-experiments\Scripts\python.exe -m pip install -r .\experiments\requirements.txt
```

The main app's dependencies are separate. A CPU-only machine is sufficient for
the small synthetic examples. GPU training, large pretrained weights, StyleGAN
quality image synthesis, and CycleGAN datasets are intentionally not required.

## Generative model comparison

```powershell
python -m experiments.generative_models --samples 256 --epochs 10 --seed 7
```

The command trains a dense autoencoder, variational autoencoder, basic GAN,
and conditional GAN on the same two-component synthetic distribution, plus a
small DCGAN on synthetic stripe images. It reports reconstruction error, KL
divergence, adversarial losses, output diversity, and example samples.
It also runs shape checks for a DCGAN, conditional GAN, style-modulated generator,
and two-way CycleGAN generator.

`DiscreteHMM` demonstrates a categorical Hidden Markov Model. The other model
classes are small educational architectures:

| Model | Demonstration | Evaluation |
|---|---|---|
| Autoencoder | Dense encoder/decoder | Reconstruction MSE |
| VAE | Reparameterized latent distribution | Reconstruction MSE and KL |
| GAN | MLP generator/discriminator | Adversarial losses and sample spread |
| DCGAN | Convolutional 28×28 grayscale generator/discriminator | Adversarial losses and output mean |
| Conditional GAN | Class-label embeddings for generator and discriminator | Adversarial losses and label-conditioned output shapes |
| StyleGAN-inspired | Mapping network and per-layer style modulation | Modulated output shapes; not full StyleGAN |
| CycleGAN | Two mappings with cycle-consistency-ready architecture | Round-trip shape; not a trained image translator |

These tiny models are intentionally not state-of-the-art or production image
generators. The default comparison uses CPU and a synthetic 2-D dataset so that
training behavior is reproducible and cheap. Image GANs need real images,
longer training, careful hyperparameters, and substantially more compute for
meaningful visual quality. StyleGAN and CycleGAN here demonstrate core
architectural ideas only; they do not reproduce the original papers' results.

The data sample printed by the program is an example of model output, not a
claim that a pretrained model was evaluated. Compare runs using the same seed,
sample count, and epoch count. Losses alone do not measure perceptual quality or
mode collapse; inspect output spread and generated samples as well.

## Word-vector lab

```powershell
python -m experiments.word_embeddings
```

`sample_data/sample_vectors.txt` is a tiny illustrative vector file, not a
pretrained model. It demonstrates loading, cosine similarity, PCA, and prompt
enrichment. Supply a local, licensed GloVe/FastText text-vector file with
`--vectors PATH` for pretrained-vector exploration. No vectors are downloaded
automatically. `TinyWord2Vec` trains a small skip-gram negative-sampling model
on an in-memory corpus. `pca_2d` is dependency-light; `tsne_2d` uses
scikit-learn. Pass `--plot-dir .\experiments\outputs` to save PCA and t-SNE
plots. The output folder is generated only when requested.

Prompt enrichment reports added terms separately so the original prompt is
preserved. It is an experiment, not an automatic production prompt rewrite.

## Model integrations and prompt chain

```powershell
python -m experiments.model_integrations
```

Choose `sentiment`, `summary`, `chain`, or `parse` as the first argument to
select a task. The first two use downloaded Hugging Face model weights; `chain`
requires provider configuration unless a completion function is injected by
code; `parse` runs offline.

The Hugging Face sentiment and summarization wrappers load models lazily. Model
IDs can be set with `LIFELOG_SENTIMENT_MODEL` and
`LIFELOG_SUMMARIZATION_MODEL`. First use may download weights and require
internet access. `run_prompt_chain` is a two-stage, provider-injected chain;
pass a callable for offline testing or configure the app's OpenAI-compatible
provider before using the default completion function. `parse_structured_output`
validates JSON with Pydantic.

## Transformer, pretraining, and multimodal concepts

`experiments.transformer_lab` includes causal multi-head self-attention, a
decoder-only next-token model, a training loss, autoregressive generation, and
an image-feature projector into the text embedding space. The tiny language
model is randomly initialized and is not a foundation model.

To demonstrate pretraining vs. fine-tuning, train the same model first on a
general text token batch, then continue training those same weights on a
smaller domain-specific batch using `train_next_token`. This illustrates the
workflow only; useful foundation-model fine-tuning needs pretrained weights,
representative data, and evaluation for memorization and regression.

The multimodal projector accepts precomputed image features. It demonstrates
shared representations but does not encode images or audio itself. The main
application's selected external LLM is configured through
`LIFELOG_LLM_API_KEY`, `LIFELOG_LLM_BASE_URL`, and `LIFELOG_LLM_MODEL` and is
called through the OpenAI-compatible client; academic scripts do not silently
inherit user memories or credentials.

## Prompt patterns and evaluation

`prompt_lab.build_prompt` provides versioned root/system, persona, structured,
comparative, multi-part, and tone-controlled prompt variants. Source notes are
placed in a separate untrusted-data section; the system prompt explicitly
rejects instructions embedded in personal notes. This reduces prompt-injection
risk but is not a security guarantee. Chain-of-thought is not requested or
returned.

`compare_prompt_outputs` runs the same source through multiple prompt versions.
Its lexical grounding score is only a word-overlap heuristic, not a factuality
or safety evaluation. Evaluate factuality manually or with a separately
validated judge and curated examples.

## User-selected memory RAG

```powershell
python -m experiments.rag --question "What did I do in the garden?" --user-id 10
```

`experiments.rag` accepts memory documents and a user ID, applies the ownership
filter before scoring or selecting excerpts, and returns dated citations. It
uses local token-weighted retrieval and extractive answers; it does not call an
LLM or read the app database. Questions with no matching memory receive an
explicit abstention. `sample_data/notes.json` includes a second user to exercise
isolation.

## Agent and tool-use demonstration

`experiments.agent_tools.run_memory_tool` exposes one read-only memory search
tool and validates the question and selected memory IDs. Unknown or mutating
tools are rejected. The user ID is supplied by the caller and is checked by
the RAG layer before retrieval. This is a safe tool-dispatch demonstration,
not an autonomous production agent.

## Tests and evaluation

From the project directory:

```powershell
python -m unittest discover -s experiments\tests -v
```

The tests cover HMM likelihood/sampling, Word2Vec output, prompt separation,
structured parsing, RAG user isolation, tool allow-listing, and tiny
Transformer training/generation. Neural-network shape and AE/VAE/GAN/
conditional-GAN/DCGAN training checks run when PyTorch is installed. Hugging
Face examples are deliberately not invoked by tests because they require
network downloads and potentially gated model terms.

Example evaluation output from the seeded CPU smoke run
(`--samples 32 --epochs 1 --seed 3`, PyTorch 2.15.0):

```text
autoencoder reconstruction MSE: 1.22645
VAE reconstruction MSE / KL:    1.43251 / 0.07180
GAN generator / discriminator:  0.87450 / 1.47945
Conditional GAN generator / discriminator: 0.75073 / 1.41263
DCGAN generator / discriminator: 0.72434 / 1.37466
```

These are smoke metrics on tiny synthetic data, not evidence of image quality
or a benchmark. A research comparison needs larger datasets, multiple seeds,
more epochs, and sample inspection. The sample-vector run ranks `diary`
closest to `journal` (cosine similarity 0.98298); the sample RAG run returns
the dated garden sentence as memory `1` for user `10`. These examples use
bundled illustrative data, not pretrained weights or production memories.
