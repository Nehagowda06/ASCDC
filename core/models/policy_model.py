from __future__ import annotations

from typing import List

import torch
from torch import nn


ACTION_SPACE: List[dict[str, str | None]] = [
    {"type": "noop", "target": None},
    {"type": "restart", "target": "A"},
    {"type": "restart", "target": "B"},
    {"type": "restart", "target": "C"},
    {"type": "scale", "target": "A"},
    {"type": "scale", "target": "B"},
    {"type": "scale", "target": "C"},
    {"type": "throttle", "target": "A"},
    {"type": "throttle", "target": "B"},
    {"type": "throttle", "target": "C"},
]


class PolicyNetwork(nn.Module):
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 32,
        output_dim: int = len(ACTION_SPACE),
    ) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


__all__ = ["ACTION_SPACE", "PolicyNetwork"]
