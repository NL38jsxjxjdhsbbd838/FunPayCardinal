#!/bin/bash
set -e

# Activate venv if it exists (Railway/nixpacks creates /opt/venv)
if [ -f "/opt/venv/bin/activate" ]; then
  echo "[start.sh] Activating /opt/venv..."
  . /opt/venv/bin/activate
fi

# Force correct tonutils version (plugin requires 0.5.8, newer versions renamed tonutils.client)
echo "[start.sh] Ensuring tonutils==0.5.8..."
pip install "tonutils==0.5.8" --quiet --force-reinstall 2>/dev/null || true

# Generate configs/_main.cfg from environment variables (skips interactive first_setup)
if [ ! -f "configs/_main.cfg" ]; then
  echo "[start.sh] No configs/_main.cfg found — generating from environment variables..."
  python generate_config.py
fi

# Generate plugins/stars_config.json from env vars if STARS_MNEMONIC is set
if [ -n "$STARS_MNEMONIC" ]; then
  echo "[start.sh] STARS_MNEMONIC detected — generating plugins/stars_config.json..."
  python generate_stars_config.py
fi

# Ensure storage dirs exist
mkdir -p storage/cache

# Ensure other required config files exist
touch configs/auto_response.cfg
touch configs/auto_delivery.cfg

# Launch FunPayCardinal
exec python main.py
