#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "Restarting Home Assistant to pick up code changes..."
docker compose -f docker-compose.dev.yml restart homeassistant
echo "Restarted. Wait a few seconds for HA to come back up."
