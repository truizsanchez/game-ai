# CLAUDE.md

Educational, Pythonic port of *Programming Game AI by Example*, visualized with arcade. Phases in `ROADMAP.md`.

## Sources (outside the repo, never commit them)
- Book as Markdown: `../game-ai-private/book-md/` (one file per chapter, `images/`). Equations are images.
- C++ source, **primary reference**: `../game-ai-private/Programming-Game-AI-by-Example-src-master/`.
- Java port, secondary reference: `../game-ai-private/game-ai-by-example/AI_Examples/`.

## Conventions
- Everything in English: code, docstrings, docs.
- Idiomatic Python, not a C++ transliteration: dataclasses, Protocols, Enums, generators, `match`, type hints.
  Document deviations from the book in `chapters/NN-*.md`.
- Don't explain Python internals in docs unless asked.
- AI logic is pure Python and testable without a window; arcade lives in a thin view layer.
- Shared code goes in `gameai.common`, mirroring the C++ `Common/` directory, only when a chapter needs it.
- Parameter files become TOML.

## Commands
- `uv run pytest` · `uv run ruff check` · `uv run ruff format` · `uv run mypy`
