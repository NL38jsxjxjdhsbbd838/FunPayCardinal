#!/bin/bash
set -e

# Generate configs/_main.cfg from environment variables (skips interactive first_setup)
if [ ! -f "configs/_main.cfg" ]; then
  echo "[start.sh] No configs/_main.cfg found — generating from environment variables..."
  python generate_config.py
fi

# Ensure other required config files exist
touch configs/auto_response.cfg
touch configs/auto_delivery.cfg

# Launch FunPayCardinal
exec python main.py
