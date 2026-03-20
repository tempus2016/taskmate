#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
docker compose -f docker-compose.dev.yml logs -f homeassistant 2>&1 | grep --line-buffered -E "(choremander|ERROR|WARNING|custom_components)"
