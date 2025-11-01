#!/usr/bin/env bash
# Usage: ./download_model.sh "MODEL_URL" DEST_DIR
# Example MODEL_URL: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip

set -euo pipefail
MODEL_URL=${1:-}
DEST=${2:-./model}

if [ -z "$MODEL_URL" ]; then
  echo "Usage: $0 \"MODEL_URL\" DEST_DIR"
  echo "Visit https://alphacephei.com/vosk/models to pick a model and copy the URL."
  exit 1
fi

mkdir -p "$DEST"
TMPZIP=$(mktemp --suffix=.zip)

echo "Downloading model..."
curl -L "$MODEL_URL" -o "$TMPZIP"

echo "Unzipping to $DEST..."
unzip -q "$TMPZIP" -d /tmp/vosk_model
# Move contents to DEST
# Many models have a top-level folder; move its contents into DEST
TOPDIR=$(find /tmp/vosk_model -maxdepth 1 -type d | tail -n +2 | head -n 1)
if [ -z "$TOPDIR" ]; then
  echo "Failed to find extracted model dir"
  exit 1
fi
mv "$TOPDIR"/* "$DEST"/
rm -rf /tmp/vosk_model
rm "$TMPZIP"

echo "Model installed into $DEST"
