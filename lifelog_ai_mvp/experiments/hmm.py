"""Categorical Hidden Markov Model for a small sequence-generation lab."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DiscreteHMM:
    """Categorical Hidden Markov Model with a sampling and likelihood demo."""

    initial: np.ndarray
    transitions: np.ndarray
    emissions: np.ndarray

    def __post_init__(self) -> None:
        initial = np.asarray(self.initial, dtype=float)
        transitions = np.asarray(self.transitions, dtype=float)
        emissions = np.asarray(self.emissions, dtype=float)
        if initial.ndim != 1:
            raise ValueError("The initial state distribution must be one-dimensional.")
        states = initial.shape[0]
        if (
            transitions.shape != (states, states)
            or emissions.ndim != 2
            or emissions.shape[0] != states
        ):
            raise ValueError("HMM probability arrays have incompatible shapes.")
        if (
            np.any(initial < 0)
            or np.any(transitions < 0)
            or np.any(emissions < 0)
            or not np.isclose(initial.sum(), 1)
            or not np.allclose(transitions.sum(axis=1), 1)
            or not np.allclose(emissions.sum(axis=1), 1)
        ):
            raise ValueError("HMM probability rows must be non-negative and sum to one.")

    def sample(
        self, length: int, rng: np.random.Generator | None = None
    ) -> tuple[list[int], list[int]]:
        if length < 1:
            raise ValueError("Sample length must be positive.")
        generator = rng or np.random.default_rng()
        state = int(generator.choice(len(self.initial), p=self.initial))
        states = [state]
        observations = [
            int(generator.choice(self.emissions.shape[1], p=self.emissions[state]))
        ]
        for _ in range(length - 1):
            state = int(generator.choice(len(self.initial), p=self.transitions[state]))
            states.append(state)
            observations.append(
                int(generator.choice(self.emissions.shape[1], p=self.emissions[state]))
            )
        return states, observations

    def sequence_log_likelihood(self, observations: list[int]) -> float:
        if not observations:
            raise ValueError("At least one observation is required.")
        if any(value < 0 or value >= self.emissions.shape[1] for value in observations):
            raise ValueError("Observation index is outside the emission vocabulary.")
        probabilities = self.initial * self.emissions[:, observations[0]]
        likelihood = 0.0
        scale = probabilities.sum()
        if scale == 0:
            return float("-inf")
        probabilities /= scale
        likelihood += np.log(scale)
        for observation in observations[1:]:
            probabilities = (
                probabilities @ self.transitions
            ) * self.emissions[:, observation]
            scale = probabilities.sum()
            if scale == 0:
                return float("-inf")
            probabilities /= scale
            likelihood += np.log(scale)
        return float(likelihood)
