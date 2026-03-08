from __future__ import annotations

import os
from pathlib import Path


def load_env(root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in (".env", ".env.example"):
        path = root / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def get_env_value(root: Path, key: str) -> str | None:
    return os.environ.get(key) or load_env(root).get(key)
