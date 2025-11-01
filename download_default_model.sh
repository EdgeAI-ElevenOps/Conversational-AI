#!/usr/bin/env bash
# Download a recommended small English VOSK model and install into ./model
# Usage: ./download_default_model.sh [DEST_DIR]
# Default DEST_DIR: ./model

set -euo pipefail
DEST=${1:-./model}
MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

echo "Downloading default VOSK model: $MODEL_URL"

mkdir -p "$DEST"
TMPZIP=$(mktemp --suffix=.zip)
curl -L "$MODEL_URL" -o "$TMPZIP"

echo "Unpacking model archive..."

# If unzip is available, use it; otherwise use Python's zipfile module to extract
if command -v unzip >/dev/null 2>&1; then
  unzip -q "$TMPZIP" -d /tmp/vosk_model
else
  echo "`unzip` not found; falling back to Python zipfile extraction."
  python3 - <<PYCODE
import sys, zipfile, os
zip_path = sys.argv[1]
out_dir = sys.argv[2]
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(out_dir)
print('Python unzip complete')
PYCODE
fi

# Find top-level extracted directory
TOPDIR=$(find /tmp/vosk_model -maxdepth 1 -type d | tail -n +2 | head -n 1)
if [ -z "$TOPDIR" ]; then
  echo "Failed to find extracted model dir" >&2
  rm -f "$TMPZIP"
  rm -rf /tmp/vosk_model
  exit 1
fi

echo "Installing model into $DEST (this may overwrite files)"
# Move contents
mkdir -p "$DEST"
mv "$TOPDIR"/* "$DEST"/

# cleanup
rm -rf /tmp/vosk_model
rm -f "$TMPZIP"

echo "Model installed into: $(realpath "$DEST")"

echo "Contents preview:"
ls -la "$DEST" | sed -n '1,50p'

echo "Done. To use: python tts_stt.py listen --model $(realpath "$DEST")"
