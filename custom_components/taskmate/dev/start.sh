#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Download HACS if not present
if [ ! -d "dev/config/custom_components/hacs" ]; then
  echo "First run - running setup..."
  ./dev/setup.sh
fi

echo "Starting Choremander dev environment..."
docker compose -f docker-compose.dev.yml up -d

echo ""
echo "Home Assistant starting at http://localhost:8123"
echo "Login: dev / dev"
echo "Test dashboard: http://localhost:8123/choremander-test"
echo ""
echo "Commands:"
echo "  ./dev/stop.sh     - Stop the container"
echo "  ./dev/restart.sh  - Restart to pick up code changes"
echo "  ./dev/logs.sh     - View logs"
