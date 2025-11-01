#!/usr/bin/env python3
"""Simple offline STT (VOSK) + TTS (pyttsx3/espeak) demo for Raspberry Pi.

Usage:
  python tts_stt.py demo --model ./model
  python tts_stt.py listen --model ./model
  python tts_stt.py say "Hello"

The script uses sounddevice for audio capture and a streaming recognizer.
"""
import argparse
import sys
import queue
import threading
import json
import subprocess
import os

try:
    from vosk import Model, KaldiRecognizer
except Exception as e:
    print("Missing dependency 'vosk'. Install with: pip install vosk", file=sys.stderr)
    raise

try:
    import sounddevice as sd
except Exception as e:
    # sounddevice can raise an OSError when PortAudio system library is missing
    print("Missing dependency 'sounddevice' or PortAudio system library.", file=sys.stderr)
    print("If you're on Debian/Ubuntu/Raspbian (including Raspberry Pi), install PortAudio with:", file=sys.stderr)
    print("  sudo apt update && sudo apt install -y libportaudio2 portaudio19-dev", file=sys.stderr)
    print("Then (in your virtualenv) reinstall the Python package:", file=sys.stderr)
    print("  pip install --upgrade pip && pip install sounddevice", file=sys.stderr)
    # re-raise so the exception trace is still visible to the user
    raise

# TTS: try pyttsx3, fallback to espeak via subprocess
try:
    import pyttsx3
    _have_pyttsx3 = True
except Exception:
    _have_pyttsx3 = False

AUDIO_QUEUE = queue.Queue()


def list_audio_devices():
    """Print available audio devices with their indices and input channel counts."""
    try:
        devices = sd.query_devices()
    except Exception as e:
        print("Failed to query audio devices:", e, file=sys.stderr)
        return
    print("Available audio devices (index: name | max_input_channels):")
    for i, dev in enumerate(devices):
        # dev can be a dict-like object
        name = dev.get('name') if isinstance(dev, dict) else str(dev)
        max_in = dev.get('max_input_channels', 'N/A') if isinstance(dev, dict) else 'N/A'
        print(f"{i}: {name} | inputs: {max_in}")



def tts_say(text: str):
    """Speak text using pyttsx3 or espeak fallback."""
    if _have_pyttsx3:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    else:
        # fallback to espeak (must be installed on system)
        subprocess.run(["espeak", text])


def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    # convert to bytes
    AUDIO_QUEUE.put(bytes(indata))


def verify_model(path: str) -> None:
    """Basic checks for a VOSK model directory and raise a helpful error if missing.

    This does not replace the actual VOSK check, but gives clearer diagnostics
    (absolute path, existence of common files) before calling into the native
    library which can fail with an opaque message.
    """
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Model path does not exist: {abs_path}")

    # Common files VOSK models contain (some variants differ). Check several
    # possibilities to provide a useful hint to the user.
    candidates = [
        os.path.join(abs_path, 'am', 'final.mdl'),
        os.path.join(abs_path, 'final.mdl'),
        os.path.join(abs_path, 'graph', 'Gr.fst'),
        os.path.join(abs_path, 'ivector', 'final.ie'),
    ]

    missing = [c for c in candidates if not os.path.exists(c)]
    # If *all* candidates are missing, warn the user. If at least one exists,
    # most likely the model is present (different model layouts exist).
    if len(missing) == len(candidates):
        details = '\n'.join(f" - {c}" for c in candidates)
        raise FileNotFoundError(
            f"No expected model files were found under {abs_path}.\n"
            f"Checked (none present):\n{details}\n"
            "Make sure you downloaded and extracted a VOSK model into this folder."
        )

    # VOSK expects a words.txt in the graph directory; check explicitly to
    # provide a clearer hint when it's missing (this was the observed failure).
    words_path = os.path.join(abs_path, 'graph', 'words.txt')
    if not os.path.exists(words_path):
        raise FileNotFoundError(
            f"Missing required file: {words_path}\n"
            "This usually means the model archive wasn't fully extracted or the"
            " chosen model is incomplete. Re-download a VOSK model and extract"
            " it so that the `graph/words.txt` file exists under the model folder."
        )


class STTWorker(threading.Thread):
    def __init__(self, model_path: str, sample_rate: int = 16000):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.sample_rate = sample_rate
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        # perform basic checks to give a clearer error if model files are missing
        try:
            verify_model(self.model_path)
        except Exception as e:
            print("Model verification failed:", e, file=sys.stderr)
            return

        model = Model(self.model_path)
        rec = KaldiRecognizer(model, self.sample_rate)
        rec.SetWords(True)
        print("STT worker started")
        while not self._stop.is_set():
            try:
                data = AUDIO_QUEUE.get(timeout=0.1)
            except queue.Empty:
                continue
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text = res.get("text", "")
                if text:
                    print("RECOGNIZED:", text)
                    # optionally speak back
                    # tts_say(text)
            else:
                # partial = json.loads(rec.PartialResult())
                pass
        print("STT worker stopping")


def run_listen(model_path: str, device: int | None, sample_rate: int = 16000):
    print(f"Loading model from: {model_path}")
    worker = STTWorker(model_path, sample_rate=sample_rate)
    worker.start()
    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=8000, dtype='int16', channels=1,
                               callback=audio_callback, device=device):
            print("Listening... Press Ctrl+C to stop")
            while True:
                sd.sleep(1000)
    except KeyboardInterrupt:
        print("Stopping...")
    except sd.PortAudioError as e:
        print("PortAudio error while opening the input stream:", e, file=sys.stderr)
        print("Possible causes: no input device available, wrong device index, or permissions.")
        print("Use the 'devices' command to list available audio devices and their indices." , file=sys.stderr)
        list_audio_devices()
        print("Then run: python tts_stt.py listen --model ./model --device <index>", file=sys.stderr)
    finally:
        worker.stop()
        worker.join()


def run_demo(model_path: str, device: int | None, sample_rate: int = 16000):
    print("Demo: will recognize speech and speak back the recognized text.")
    print("You can interrupt with Ctrl+C")
    # start STT worker which will call tts on recognized text
    try:
        verify_model(model_path)
    except Exception as e:
        print("Model verification failed:", e, file=sys.stderr)
        return

    model = Model(model_path)
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)

    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=8000, dtype='int16', channels=1,
                               callback=audio_callback, device=device):
            print("Listening... say something")
            while True:
                try:
                    data = AUDIO_QUEUE.get(timeout=0.1)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get('text', '')
                    if text:
                        print('RECOGNIZED:', text)
                        tts_say(text)
                else:
                    pass
    except KeyboardInterrupt:
        print('Interrupted, exiting')
    except sd.PortAudioError as e:
        print("PortAudio error while opening the input stream:", e, file=sys.stderr)
        print("Use the 'devices' command to list available audio devices and their indices.", file=sys.stderr)
        list_audio_devices()
        print("Then run: python tts_stt.py demo --model ./model --device <index>", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')

    p_demo = sub.add_parser('demo', help='recognize and speak back')
    p_demo.add_argument('--model', required=True, help='Path to VOSK model directory')
    p_demo.add_argument('--device', type=int, default=None, help='sounddevice device id')
    p_demo.add_argument('--rate', type=int, default=16000, help='sample rate')

    p_listen = sub.add_parser('listen', help='listen and print recognized text')
    p_listen.add_argument('--model', required=True, help='Path to VOSK model directory')
    p_listen.add_argument('--device', type=int, default=None, help='sounddevice device id')
    p_listen.add_argument('--rate', type=int, default=16000, help='sample rate')

    p_say = sub.add_parser('say', help='text-to-speech a given phrase')
    p_say.add_argument('text', help='Text to speak')

    p_devices = sub.add_parser('devices', help='list audio devices and indices')

    args = parser.parse_args()

    if args.cmd == 'demo':
        run_demo(args.model, args.device, args.rate)
    elif args.cmd == 'listen':
        run_listen(args.model, args.device, args.rate)
    elif args.cmd == 'say':
        tts_say(args.text)
    elif args.cmd == 'devices':
        list_audio_devices()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
