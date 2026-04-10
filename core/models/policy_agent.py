from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import torch
from huggingface_hub import HfApi, hf_hub_download

from core.models.policy_model import ACTION_SPACE, PolicyNetwork


class PolicyAgent:
    def __init__(
        self,
        model_path: str | Path | None = None,
        repo_id: str = "ascdc-policy-model",
        token: Optional[str] = None,
        seed: int = 42,
    ) -> None:
        self.model_path = Path(model_path or "artifacts/ascdc-policy-model.pt")
        self.repo_id = repo_id
        self.token = token
        self.seed = seed
        self.api = HfApi()
        self.source = "unavailable"
        self.loaded = False

        torch.manual_seed(self.seed)
        self.model = PolicyNetwork()
        self.model.eval()

        self._load_model()

    def predict(self, observation: Any) -> Dict[str, Any]:
        inputs = self._flatten_observation(observation)
        with torch.no_grad():
            logits = self.model(inputs)
            probabilities = torch.softmax(logits, dim=-1).squeeze(0)

        best_index = int(torch.argmax(probabilities).item())
        best_action = self._action_from_index(best_index)

        return {
            "action": self._response_action(best_action),
            "probabilities": [
                {
                    "action": self._response_action(action),
                    "score": round(float(probabilities[index].item()), 6),
                }
                for index, action in enumerate(ACTION_SPACE)
            ],
        }

    def score_action(self, observation: Any, action: Mapping[str, Any]) -> float:
        inputs = self._flatten_observation(observation)
        with torch.no_grad():
            logits = self.model(inputs)
            probabilities = torch.softmax(logits, dim=-1).squeeze(0)

        action_index = self._action_index(action)
        if action_index is None:
            return 0.0
        return round(float(probabilities[action_index].item()), 6)

    def save_model(self, path: str | Path | None = None) -> str:
        target = Path(path or self.model_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.model.state_dict(),
                "seed": self.seed,
            },
            target,
        )
        self.model_path = target
        self.loaded = True
        self.source = "local"
        return str(target)

    def push_to_hub(self, token: Optional[str] = None, repo_id: Optional[str] = None) -> str:
        resolved_repo_id = self._resolve_repo_id(repo_id or self.repo_id, token or self.token)
        saved_path = self.save_model()
        self.api.create_repo(repo_id=resolved_repo_id, exist_ok=True, token=token or self.token)
        self.api.upload_file(
            repo_id=resolved_repo_id,
            path_or_fileobj=saved_path,
            path_in_repo=self.model_path.name,
            token=token or self.token,
        )
        self.repo_id = resolved_repo_id
        return resolved_repo_id

    def model_info(self) -> Dict[str, Any]:
        return {
            "loaded": self.loaded,
            "source": self.source,
            "repo_id": self.repo_id,
            "model_path": str(self.model_path),
        }

    def _load_model(self) -> None:
        if self.model_path.exists():
            self._load_state(self.model_path)
            self.source = "local"
            self.loaded = True
            return

        try:
            downloaded = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.model_path.name,
                token=self.token,
            )
        except Exception:
            self.source = "unavailable"
            self.loaded = False
            return

        self._load_state(Path(downloaded))
        self.source = "hf"
        self.loaded = True

    def _load_state(self, path: Path) -> None:
        payload = torch.load(path, map_location="cpu")
        state_dict = payload["state_dict"] if isinstance(payload, dict) and "state_dict" in payload else payload
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def _flatten_observation(self, observation: Any) -> torch.Tensor:
        snapshot = self._snapshot(observation)
        queues = snapshot.get("queues", {})
        latencies = snapshot.get("latencies", {})

        values = [
            float(queues.get("A", 0.0)),
            float(queues.get("B", 0.0)),
            float(queues.get("C", 0.0)),
            float(latencies.get("A", 0.0)),
            float(latencies.get("B", 0.0)),
            float(latencies.get("C", 0.0)),
            float(snapshot.get("system_pressure", 0.0)),
            float(snapshot.get("remaining_budget", snapshot.get("budget", 0.0))),
        ]
        return torch.tensor([values], dtype=torch.float32)

    def _action_index(self, action: Mapping[str, Any]) -> Optional[int]:
        action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
        target = action.get("target")
        for index, candidate in enumerate(ACTION_SPACE):
            if candidate["type"] == action_type and candidate["target"] == target:
                return index
        return None

    @staticmethod
    def _action_from_index(index: int) -> Dict[str, Any]:
        action = ACTION_SPACE[index]
        return {"type": action["type"], "target": action["target"]}

    @staticmethod
    def _response_action(action: Mapping[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
        response = {
            "type": action_type,
            "action_type": action_type,
        }
        if action.get("target") is not None:
            response["target"] = action.get("target")
        return response

    @staticmethod
    def _snapshot(observation: Any) -> Dict[str, Any]:
        if isinstance(observation, Mapping):
            return dict(observation)
        if hasattr(observation, "model_dump") and callable(observation.model_dump):
            return observation.model_dump()
        if hasattr(observation, "dict") and callable(observation.dict):
            return observation.dict()
        if hasattr(observation, "__dict__"):
            return {
                key: value
                for key, value in vars(observation).items()
                if not key.startswith("_")
            }
        return {}

    def _resolve_repo_id(self, repo_id: str, token: Optional[str]) -> str:
        if "/" in repo_id:
            return repo_id
        try:
            whoami = self.api.whoami(token=token)
        except Exception:
            return repo_id

        username = str(whoami.get("name", "")).strip()
        if not username:
            return repo_id
        return f"{username}/{repo_id}"


__all__ = ["PolicyAgent"]
