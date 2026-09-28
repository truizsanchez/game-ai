"""Locate files from the original C++ distribution (maps, etc.), which are not in this repo.

The directory defaults to ``../game-ai-private/Programming-Game-AI-by-Example-src-master``
next to the repository and can be overridden with the ``GAMEAI_ORIGINAL_SOURCE`` variable.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ORIGINAL_SOURCE = (
    _REPO_ROOT.parent / "game-ai-private" / "Programming-Game-AI-by-Example-src-master"
)


def original_source_dir() -> Path:
    return Path(os.environ.get("GAMEAI_ORIGINAL_SOURCE", DEFAULT_ORIGINAL_SOURCE))


def original_file(*parts: str) -> Path | None:
    """Path to a file of the original distribution, or None if it isn't available."""
    path = original_source_dir().joinpath(*parts)
    return path if path.exists() else None
