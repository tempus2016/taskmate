#!/usr/bin/env bash
# Provisions the dev container: test harness, linters, and a throwaway Home
# Assistant config with TaskMate symlinked in. Runs once, on container create.
set -euo pipefail

echo "==> Installing Python tooling"
python -m pip install --upgrade pip
pip install -r requirements_test.txt
pip install ruff==0.15.12 pre-commit homeassistant

echo "==> Installing Node tooling"
npm ci

echo "==> Installing git hooks"
pre-commit install || echo "pre-commit install skipped"

echo "==> Preparing a Home Assistant config at ./dev-config"
mkdir -p dev-config/custom_components
# Symlink, not copy — edits to the integration are live in the running HA.
ln -sfn "$(pwd)/custom_components/taskmate" dev-config/custom_components/taskmate

if [ ! -f dev-config/configuration.yaml ]; then
  cat > dev-config/configuration.yaml <<'YAML'
# Minimal Home Assistant config for TaskMate development.
default_config:

logger:
  default: info
  logs:
    custom_components.taskmate: debug

# Cards are served by the integration itself at /taskmate/<card>.js and
# registered automatically, so no lovelace resources block is needed here.
YAML
fi

cat <<'EOF'

Setup complete.

  Run tests            pytest -v
  Lint                 ruff check custom_components/taskmate tests scripts && npm run lint
  Data checks          python3 scripts/check_translations.py && python3 scripts/check_data_files.py
  Start Home Assistant hass -c dev-config
                       then open the forwarded port 8123 and add the
                       TaskMate integration from Settings -> Devices & services

EOF
