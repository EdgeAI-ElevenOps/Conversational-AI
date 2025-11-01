import os
import sys
import traceback

try:
    from vosk import Model
except Exception as e:
    print("Failed to import vosk:", e, file=sys.stderr)
    raise

MODEL_PATH = sys.argv[1] if len(sys.argv) > 1 else './model'
abs_path = os.path.abspath(MODEL_PATH)
print('Testing model path:', abs_path)
if not os.path.exists(abs_path):
    print('Path does not exist')
    sys.exit(2)

candidates = [
    os.path.join(abs_path, 'am', 'final.mdl'),
    os.path.join(abs_path, 'final.mdl'),
    os.path.join(abs_path, 'graph', 'Gr.fst'),
    os.path.join(abs_path, 'ivector', 'final.ie'),
]
for c in candidates:
    print(c, '->', 'FOUND' if os.path.exists(c) else 'MISSING')

print('\nAttempting to create vosk.Model...')
try:
    m = Model(abs_path)
    print('Model created successfully:', type(m))
except Exception:
    print('Model creation raised an exception:')
    traceback.print_exc()
    sys.exit(3)

print('Done')
