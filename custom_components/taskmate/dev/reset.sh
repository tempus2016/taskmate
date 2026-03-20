#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping any running containers..."
docker compose -f docker-compose.dev.yml down 2>/dev/null || true

echo "Removing generated files (keeping static config)..."
rm -rf dev/config/.storage/auth
rm -rf dev/config/.storage/auth_provider.homeassistant
rm -rf dev/config/custom_components/hacs
rm -rf dev/config/home-assistant_v2.db
rm -rf dev/config/home-assistant.log

echo "Reset complete. Run ./dev/start.sh to set up fresh."
