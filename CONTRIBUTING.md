# Contributing

1. Read [AGENTS.md](AGENTS.md) and [docs/DECISIONS.md](docs/DECISIONS.md). Only Confirmed decisions bind.
2. Pick a package from [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md). Branch `wp/<id>-<short-name>`.
3. Set up: `uv sync` then `uv run pytest`.
4. Before a pull request run:
   - `uv run ruff check . && uv run ruff format --check .`
   - `uv run pyright`
   - `uv run lint-imports`
   - `uv run python tools/i18n.py update && uv run python tools/i18n.py compile && uv run python tools/i18n.py check`
   - `QT_QPA_PLATFORM=offscreen uv run pytest`
5. Every user-visible string goes through gettext and gets an English source and a Vietnamese translation in the same change.
6. Use Conventional Commits. Write everything on GitHub in English.
7. Do not add vendor SDK files to the repository. Do not add personal metadata to fixtures.
