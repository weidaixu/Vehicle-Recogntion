"""Load local server-only configuration without exposing secret values."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env(path: Path | None = None) -> bool:
    """Load a non-empty DeepSeek key from the project .env file.

    The project-local value intentionally replaces a stale process value so
    restarting DriveScope consistently uses the key the user placed in .env.
    """
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return False

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != "DEEPSEEK_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1].strip()
        if not value:
            return False
        os.environ["DEEPSEEK_API_KEY"] = value
        return True
    return False
