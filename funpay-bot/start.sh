#!/bin/bash
set -e

# Activate venv if it exists (Railway/nixpacks creates /opt/venv)
if [ -f "/opt/venv/bin/activate" ]; then
  echo "[start.sh] Activating /opt/venv..."
  . /opt/venv/bin/activate
fi

# Check and fix tonutils version (plugin requires 0.5.8, newer versions renamed tonutils.client)
TONUTILS_VER=$(python -c "import importlib.metadata; print(importlib.metadata.version('tonutils'))" 2>/dev/null || echo "none")
echo "[start.sh] tonutils installed: $TONUTILS_VER"
if [ "$TONUTILS_VER" != "0.5.8" ]; then
  echo "[start.sh] Installing tonutils==0.5.8..."
  pip install "tonutils==0.5.8" --quiet --no-deps 2>/dev/null || true
  echo "[start.sh] tonutils==0.5.8 installed."
else
  echo "[start.sh] tonutils==0.5.8 already correct, skipping."
fi

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
