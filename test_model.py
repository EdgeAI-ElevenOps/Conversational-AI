#!/usr/bin/env python3
"""Quick script to verify a VOSK model can be loaded."""
import sys
from vosk import Model

if len(sys.argv) < 2:
    print("Usage: python test_model.py /path/to/model")
    sys.exit(2)

model_path = sys.argv[1]
print(f"Trying to load model from: {model_path}")
try:
    m = Model(model_path)
    print("Model loaded successfully.")
    # print some basic info if available
    # VOSK Model doesn't expose much metadata in python binding; success is enough.
except Exception as e:
    print("Failed to load model:", e)
    sys.exit(1)
