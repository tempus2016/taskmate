# Contributing to TaskMate

Thanks for your interest in improving TaskMate! This is a Home Assistant custom
integration for family chore and points tracking. Contributions of all kinds are
welcome — bug reports, feature ideas, translations, docs, and code.

## Before you start

- **Bugs and features:** please open an issue first using the
  [issue templates](https://github.com/tempus2016/taskmate/issues/new/choose).
  For features especially, it's worth agreeing on the approach before writing
  code.
- **Questions and ideas:** use
  [Discussions](https://github.com/tempus2016/taskmate/discussions) rather than
  an issue.
- **Check the [Troubleshooting wiki](https://github.com/tempus2016/taskmate/wiki/Troubleshooting)**
  first for common problems.

## Project layout

```
custom_components/taskmate/
├── __init__.py            # integration setup
├── config_flow.py         # UI config & options flow
├── coordinator.py         # core data coordinator
├── coord_*.py             # per-domain coordinators (chores, points, badges, …)
├── sensor.py              # sensors the cards read from
├── services.yaml          # service definitions
├── websocket.py           # WebSocket API commands
├── translations/          # backend strings (de, en, en-GB, fr, nb, nn, pt, pt-BR)
├── strings.json           # source strings
└── www/                   # Lovelace cards (LitElement) + panel + locales
```

- **Backend** is Python. Follow the existing patterns — don't introduce new
  frameworks or heavy dependencies without discussing it first.
- **Cards** (`www/taskmate-*-card.js`) are **LitElement**-based. Other frontend
  code is vanilla JS. Cards read chore/child data from the sensors, not by
  calling services directly to fetch state.

## Development setup

### One-click: dev container / Codespaces

The repo ships a dev container. Open it in GitHub Codespaces, or in VS Code with
the Dev Containers extension ("Reopen in Container"). Setup installs the test
harness, ruff, ESLint and pre-commit, and creates a scratch HA config at
`dev-config/` with the integration symlinked in — so `hass -c dev-config` gives
you a real Home Assistant on port 8123 with your working copy live.

### Manual

The fastest loop is a real Home Assistant instance with the integration
bind-mounted:

1. Mount or copy `custom_components/taskmate` into your HA config's
   `custom_components/` directory.
2. Restart Home Assistant to pick up Python changes.
3. For card (`.js`) changes, **hard-refresh** the browser — the cards are
   cache-busted by the manifest version, so a hard refresh is needed after JS
   edits.

## Code quality

Run these locally before pushing:

```bash
# Lint and formatting (both match the "Ruff" CI check)
ruff check custom_components/taskmate tests scripts
ruff format --check custom_components/taskmate tests scripts   # drop --check to fix

# Cards and panel (matches the "ESLint" CI check)
npm ci && npm run lint

# Tests (matches the "Run tests" CI check)
pytest

# Every locale matches en.json (matches the "Translation parity" CI check)
python3 scripts/check_translations.py

# Blueprints, sentences and packaging metadata parse (matches "Data files")
python3 scripts/check_data_files.py
```

Or install the hooks once and let them run on commit:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

`hassfest`, HACS validation, dependency review and a workflow-security audit
(`zizmor`) also run in CI, alongside GitHub's CodeQL code scanning.

## Translations

TaskMate ships in several languages. **Any new user-facing string must be added
to every locale in the same PR** — `de`, `fr`, `nb`, `nn`, `pt`, and `pt-BR`
(plus the English source). English-only PRs with a "translate later" note will
be asked to include the translations.

Backend strings live in `custom_components/taskmate/translations/` and
`strings.json`; card strings live under `www/locales/`.

This is enforced in CI: `scripts/check_translations.py` fails the build if any
locale's key set differs from `en.json` in either catalogue. Run it locally to
see exactly which keys are missing.

## Submitting a pull request

1. Fork and create a feature branch.
2. Make your change, keeping the PR focused on one logical thing.
3. Run `ruff` and `pytest` locally.
4. Test the change on a real Home Assistant instance.
5. Open a PR using the template. Link the issue it closes
   (`Closes #123`) so it auto-closes on merge.
6. If your change is release-bound and affects behaviour, bump the
   `manifest.json` version.

A maintainer will review, and may ask for changes. Once it's green and approved,
it gets merged.

## Code of Conduct

By participating you agree to abide by our
[Code of Conduct](../CODE_OF_CONDUCT.md).
