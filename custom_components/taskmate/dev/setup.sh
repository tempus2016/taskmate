#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

echo "Setting up Choremander dev environment..."

# Create .storage directory if needed
mkdir -p "$CONFIG_DIR/.storage"

# Download HACS if not present
if [ ! -d "$CONFIG_DIR/custom_components/hacs" ]; then
  echo "Downloading HACS..."
  mkdir -p "$CONFIG_DIR/custom_components"
  cd "$CONFIG_DIR"
  wget -q -O hacs.zip "https://github.com/hacs/integration/releases/latest/download/hacs.zip"
  unzip -q -o hacs.zip -d custom_components/hacs
  rm hacs.zip
  echo "HACS downloaded."
fi

# Auth files are now pre-created in the repository
# Username: dev, Password: dev

echo "Setup complete!"
echo "Auth files are pre-configured. Login with dev/dev"
