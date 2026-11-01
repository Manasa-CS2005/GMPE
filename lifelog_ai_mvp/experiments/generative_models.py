"""Small synthetic experiments for classical and deep generative models.

The StyleGenerator is an educational style-modulated MLP, not an implementation
of the full StyleGAN paper. Synthetic data keeps the experiments reproducible
and avoids downloading private or third-party datasets.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

class Autoencoder(nn.Module):
    def __init__(self, input_dim: int = 2, latent_dim: int = 2) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(), nn.Linear(32, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32), nn.ReLU(), nn.Linear(32, input_dim)
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.decoder(self.encoder(inputs))


class VariationalAutoencoder(nn.Module):
    def __init__(self, input_dim: int = 2, latent_dim: int = 2) -> None:
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 32), nn.ReLU())
        self.mean = nn.Linear(32, latent_dim)
        self.log_variance = nn.Linear(32, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32), nn.ReLU(), nn.Linear(32, input_dim)
        )

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        hidden = self.encoder(inputs)
        mean = self.mean(hidden)
        log_variance = self.log_variance(hidden).clamp(-12, 12)
        latent = mean + torch.randn_like(mean) * torch.exp(0.5 * log_variance)
        return self.decoder(latent), mean, log_variance


class GANGenerator(nn.Module):
    def __init__(self, noise_dim: int = 8, output_dim: int = 2) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(noise_dim, 32),
            nn.LeakyReLU(0.2),
            nn.Linear(32, 32),
            nn.LeakyReLU(0.2),
            nn.Linear(32, output_dim),
        )

    def forward(self, noise: Tensor) -> Tensor:
        return self.network(noise)


class GANDiscriminator(nn.Module):
    def __init__(self, input_dim: int = 2) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.LeakyReLU(0.2),
            nn.Linear(32, 1),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs)


class ConditionalGenerator(nn.Module):
    def __init__(
        self, noise_dim: int = 8, num_classes: int = 2, embedding_dim: int = 8
    ) -> None:
        super().__init__()
        self.labels = nn.Embedding(num_classes, embedding_dim)
        self.network = GANGenerator(noise_dim + embedding_dim, output_dim=2)

    def forward(self, noise: Tensor, labels: Tensor) -> Tensor:
        return self.network(torch.cat((noise, self.labels(labels)), dim=1))


class ConditionalDiscriminator(nn.Module):
    def __init__(self, num_classes: int = 2, embedding_dim: int = 8) -> None:
        super().__init__()
        self.labels = nn.Embedding(num_classes, embedding_dim)
        self.network = GANDiscriminator(input_dim=2 + embedding_dim)

    def forward(self, inputs: Tensor, labels: Tensor) -> Tensor:
        return self.network(torch.cat((inputs, self.labels(labels)), dim=1))


class DCGANGenerator(nn.Module):
    """Compact convolutional GAN generator for 28x28 grayscale samples."""

    def __init__(self, noise_dim: int = 64) -> None:
        super().__init__()
        self.noise_dim = noise_dim
        self.project = nn.Linear(noise_dim, 128 * 7 * 7)
        self.network = nn.Sequential(
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.ConvTranspose2d(64, 1, 4, stride=2, padding=1),
            nn.Tanh(),
        )

    def forward(self, noise: Tensor) -> Tensor:
        features = self.project(noise).reshape(-1, 128, 7, 7)
        return self.network(features)


class DCGANDiscriminator(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(1, 32, 4, stride=2, padding=1),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(32, 64, 4, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2, True),
            nn.Flatten(),
            nn.Linear(64 * 7 * 7, 1),
        )

    def forward(self, images: Tensor) -> Tensor:
        return self.network(images)


class StyleGenerator(nn.Module):
    """A small style-modulated generator illustrating mapping and modulation."""

    def __init__(self, noise_dim: int = 8, hidden_dim: int = 32, output_dim: int = 2):
        super().__init__()
        self.mapping = nn.Sequential(
            nn.Linear(noise_dim, hidden_dim), nn.LeakyReLU(0.2),
            nn.Linear(hidden_dim, hidden_dim), nn.LeakyReLU(0.2),
        )
        self.constant = nn.Parameter(torch.randn(1, hidden_dim))
        self.layers = nn.ModuleList(nn.Linear(hidden_dim, hidden_dim) for _ in range(2))
        self.styles = nn.ModuleList(nn.Linear(hidden_dim, hidden_dim * 2) for _ in range(2))
        self.output = nn.Linear(hidden_dim, output_dim)

    def forward(self, noise: Tensor) -> Tensor:
        style = self.mapping(noise)
        features = self.constant.expand(noise.shape[0], -1)
        for layer, modulation in zip(self.layers, self.styles):
            scale, bias = modulation(style).chunk(2, dim=-1)
            features = F.leaky_relu(layer(features) * (1 + scale) + bias, 0.2)
        return self.output(features)


class CycleGenerator(nn.Module):
    def __init__(self, input_dim: int = 2, output_dim: int = 2) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
            nn.Linear(32, output_dim),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs)


class CycleDiscriminator(nn.Module):
    def __init__(self, input_dim: int = 2) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 32), nn.LeakyReLU(0.2), nn.Linear(32, 1)
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs)


def synthetic_mixture(samples: int, seed: int = 7) -> tuple[Tensor, Tensor]:
    if samples < 4:
        raise ValueError("Use at least four samples for the synthetic mixture.")
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, 2, size=samples)
    centers = np.where(labels[:, None] == 0, [-1.5, 0.0], [1.5, 0.0])
    values = centers + rng.normal(0, 0.35, size=(samples, 2))
    return torch.tensor(values, dtype=torch.float32), torch.tensor(labels, dtype=torch.long)


def synthetic_images(samples: int, seed: int = 7) -> Tensor:
    """Create deterministic stripe images so DCGAN training needs no downloads."""
    if samples < 2:
        raise ValueError("Use at least two images for DCGAN training.")
    generator = torch.Generator().manual_seed(seed)
    labels = torch.randint(0, 2, (samples,), generator=generator)
    images = torch.zeros(samples, 1, 28, 28)
    for index, label in enumerate(labels.tolist()):
        if label == 0:
            images[index, 0, ::4, :] = 1
        else:
            images[index, 0, :, ::4] = 1
    noise = torch.randn(images.shape, generator=generator) * 0.05
    return (images + noise).clamp(-1, 1)


def cycle_consistency_loss(
    real_a: Tensor,
    real_b: Tensor,
    generator_ab: CycleGenerator,
    generator_ba: CycleGenerator,
    cycle_weight: float = 10.0,
) -> Tensor:
    if cycle_weight < 0:
        raise ValueError("Cycle consistency weight cannot be negative.")
    reconstructed_a = generator_ba(generator_ab(real_a))
    reconstructed_b = generator_ab(generator_ba(real_b))
    return cycle_weight * (
        F.l1_loss(reconstructed_a, real_a) + F.l1_loss(reconstructed_b, real_b)
    )


def train_comparison(samples: int = 256, epochs: int = 10, seed: int = 7) -> dict[str, object]:
    """Train AE, VAE, GAN, conditional GAN and DCGAN on synthetic data."""
    if epochs < 1:
        raise ValueError("Epoch count must be positive.")
    torch.manual_seed(seed)
    data, labels = synthetic_mixture(samples, seed)
    batch = data
    reconstruction_loss = nn.MSELoss()

    autoencoder = Autoencoder()
    autoencoder_optimizer = torch.optim.Adam(autoencoder.parameters(), lr=0.01)
    autoencoder_loss = 0.0
    for _ in range(epochs):
        autoencoder_optimizer.zero_grad()
        loss = reconstruction_loss(autoencoder(batch), batch)
        loss.backward()
        autoencoder_optimizer.step()
        autoencoder_loss = float(loss.detach())

    vae = VariationalAutoencoder()
    vae_optimizer = torch.optim.Adam(vae.parameters(), lr=0.01)
    vae_reconstruction = 0.0
    vae_kl = 0.0
    for _ in range(epochs):
        vae_optimizer.zero_grad()
        decoded, mean, log_variance = vae(batch)
        mse = reconstruction_loss(decoded, batch)
        kl = -0.5 * torch.mean(
            1 + log_variance - mean.square() - log_variance.exp()
        )
        loss = mse + kl
        loss.backward()
        vae_optimizer.step()
        vae_reconstruction = float(mse.detach())
        vae_kl = float(kl.detach())

    generator = GANGenerator()
    discriminator = GANDiscriminator()
    generator_optimizer = torch.optim.Adam(generator.parameters(), lr=0.002)
    discriminator_optimizer = torch.optim.Adam(discriminator.parameters(), lr=0.002)
    adversarial_loss = nn.BCEWithLogitsLoss()
    generator_loss = 0.0
    discriminator_loss = 0.0
    for _ in range(epochs):
        noise = torch.randn(samples, 8)
        fake = generator(noise).detach()
        discriminator_optimizer.zero_grad()
        real_loss = adversarial_loss(discriminator(batch), torch.ones(samples, 1))
        fake_loss = adversarial_loss(discriminator(fake), torch.zeros(samples, 1))
        d_loss = real_loss + fake_loss
        d_loss.backward()
        discriminator_optimizer.step()

        generator_optimizer.zero_grad()
        generated = generator(torch.randn(samples, 8))
        g_loss = adversarial_loss(
            discriminator(generated), torch.ones(samples, 1)
        )
        g_loss.backward()
        generator_optimizer.step()
        generator_loss = float(g_loss.detach())
        discriminator_loss = float(d_loss.detach())

    conditional_generator = ConditionalGenerator()
    conditional_discriminator = ConditionalDiscriminator()
    conditional_generator_optimizer = torch.optim.Adam(
        conditional_generator.parameters(), lr=0.002
    )
    conditional_discriminator_optimizer = torch.optim.Adam(
        conditional_discriminator.parameters(), lr=0.002
    )
    conditional_generator_loss = 0.0
    conditional_discriminator_loss = 0.0
    for _ in range(epochs):
        fake = conditional_generator(torch.randn(samples, 8), labels).detach()
        conditional_discriminator_optimizer.zero_grad()
        real_loss = adversarial_loss(
            conditional_discriminator(batch, labels), torch.ones(samples, 1)
        )
        fake_loss = adversarial_loss(
            conditional_discriminator(fake, labels), torch.zeros(samples, 1)
        )
        d_loss = real_loss + fake_loss
        d_loss.backward()
        conditional_discriminator_optimizer.step()

        conditional_generator_optimizer.zero_grad()
        conditioned = conditional_generator(torch.randn(samples, 8), labels)
        g_loss = adversarial_loss(
            conditional_discriminator(conditioned, labels), torch.ones(samples, 1)
        )
        g_loss.backward()
        conditional_generator_optimizer.step()
        conditional_generator_loss = float(g_loss.detach())
        conditional_discriminator_loss = float(d_loss.detach())

    with torch.no_grad():
        generated_samples = generator(torch.randn(128, 8))

    images = synthetic_images(samples, seed)
    image_generator = DCGANGenerator()
    image_discriminator = DCGANDiscriminator()
    image_generator_optimizer = torch.optim.Adam(
        image_generator.parameters(), lr=0.0002, betas=(0.5, 0.999)
    )
    image_discriminator_optimizer = torch.optim.Adam(
        image_discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999)
    )
    dcgan_generator_loss = 0.0
    dcgan_discriminator_loss = 0.0
    for _ in range(epochs):
        image_noise = torch.randn(samples, 64)
        fake_images = image_generator(image_noise).detach()
        image_discriminator_optimizer.zero_grad()
        real_loss = adversarial_loss(
            image_discriminator(images), torch.ones(samples, 1)
        )
        fake_loss = adversarial_loss(
            image_discriminator(fake_images), torch.zeros(samples, 1)
        )
        d_loss = real_loss + fake_loss
        d_loss.backward()
        image_discriminator_optimizer.step()

        image_generator_optimizer.zero_grad()
        generated_images = image_generator(torch.randn(samples, 64))
        g_loss = adversarial_loss(
            image_discriminator(generated_images), torch.ones(samples, 1)
        )
        g_loss.backward()
        image_generator_optimizer.step()
        dcgan_generator_loss = float(g_loss.detach())
        dcgan_discriminator_loss = float(d_loss.detach())

    with torch.no_grad():
        generated_images = image_generator(torch.randn(16, 64))
    return {
        "seed": seed,
        "samples": samples,
        "epochs": epochs,
        "device": "cpu",
        "autoencoder_reconstruction_mse": autoencoder_loss,
        "vae_reconstruction_mse": vae_reconstruction,
        "vae_kl_divergence": vae_kl,
        "gan_generator_loss": generator_loss,
        "gan_discriminator_loss": discriminator_loss,
        "gan_generated_std": generated_samples.std(dim=0).tolist(),
        "gan_generated_sample": generated_samples[:5].tolist(),
        "conditional_gan_generator_loss": conditional_generator_loss,
        "conditional_gan_discriminator_loss": conditional_discriminator_loss,
        "dcgan_generator_loss": dcgan_generator_loss,
        "dcgan_discriminator_loss": dcgan_discriminator_loss,
        "dcgan_generated_mean": float(generated_images.mean()),
    }


def smoke_model_shapes() -> dict[str, tuple[int, ...]]:
    """Run one forward pass through each deep-model demonstration."""
    noise = torch.randn(4, 8)
    image_noise = torch.randn(4, 64)
    inputs = torch.randn(4, 2)
    labels = torch.tensor([0, 1, 0, 1], dtype=torch.long)
    autoencoder = Autoencoder()
    vae = VariationalAutoencoder()
    conditional_generator = ConditionalGenerator()
    conditional_discriminator = ConditionalDiscriminator()
    dcgan_generator = DCGANGenerator()
    dcgan_discriminator = DCGANDiscriminator()
    style_generator = StyleGenerator()
    cycle_generator = CycleGenerator()
    cycle_discriminator = CycleDiscriminator()
    return {
        "autoencoder": tuple(autoencoder(inputs).shape),
        "vae": tuple(vae(inputs)[0].shape),
        "gan": tuple(GANGenerator()(noise).shape),
        "conditional_gan": tuple(
            conditional_discriminator(
                conditional_generator(noise, labels), labels
            ).shape
        ),
        "dcgan": tuple(dcgan_discriminator(dcgan_generator(image_noise)).shape),
        "stylegan_inspired": tuple(style_generator(noise).shape),
        "cyclegan": tuple(cycle_generator(cycle_generator(inputs)).shape),
        "cyclegan_discriminator": tuple(cycle_discriminator(inputs).shape),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(json.dumps(train_comparison(args.samples, args.epochs, args.seed), indent=2))
    print(json.dumps({key: list(value) for key, value in smoke_model_shapes().items()}, indent=2))


if __name__ == "__main__":
    main()
