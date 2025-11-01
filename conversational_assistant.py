#!/usr/bin/env python3
"""Conversational assistant: STT -> Ollama LLM -> TTS loop.

Usage:
  python conversational_assistant.py --model ./model --ollama-model tinyllama:1.1b

Requirements: `vosk`, `sounddevice`, `pyttsx3` (or `espeak`), `requests`.

This script listens for a spoken utterance, sends the transcription as a prompt
to a local Ollama model (HTTP API at localhost:11434 or `ollama` CLI fallback),
speaks the assistant reply and keeps short history to make the conversation coherent.
"""
import argparse
import json
import queue
import subprocess
import sys
import time
from typing import List

import requests

try:
    from vosk import Model, KaldiRecognizer
except Exception as e:
    print("Missing dependency 'vosk'. Install with: pip install vosk", file=sys.stderr)
    raise

try:
    import sounddevice as sd
except Exception as e:
    print("Missing dependency 'sounddevice' or PortAudio system library.", file=sys.stderr)
    raise

# reuse tts from project helper if available
try:
    from tts_stt import tts_say, verify_model
except Exception:
    # fallback: simple print if import fails
    def tts_say(text: str):
        print("TTS:", text)

    def verify_model(path: str):
        return


API_URL = "http://localhost:11434/api/generate"


def query_ollama_http(prompt: str, model: str) -> str:
    payload = {"model": model, "prompt": prompt}
    # Ollama local API often streams NDJSON fragments. Request streaming and
    # aggregate the 'response' fields into a single string.
    try:
        resp = requests.post(API_URL, json=payload, stream=True, timeout=60)
        resp.raise_for_status()
        pieces = []
        # iterate over lines (NDJSON or JSON fragments)
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            # Sometimes the server may send non-JSON control lines; skip those
            try:
                obj = json.loads(raw)
            except Exception:
                # if it's not JSON, try to append raw text
                pieces.append(raw)
                continue
            # Ollama streaming fragments commonly include a 'response' field
            if isinstance(obj, dict) and 'response' in obj:
                part = obj.get('response') or ''
                pieces.append(str(part))
            # If a final envelope with done=true is provided, break
            if isinstance(obj, dict) and obj.get('done'):
                break
        # Join and return the concatenated response
        return ''.join(pieces).strip()
    except Exception:
        # Let caller fallback to CLI if HTTP streaming fails
        raise


def query_ollama_cli(prompt: str, model: str) -> str:
    # Fallback using installed `ollama` CLI (if available)
    try:
        # Use `ollama query` which prints a response for small prompts
        proc = subprocess.run(["ollama", "query", model, prompt], capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            return proc.stdout.strip() or proc.stderr.strip()
        else:
            return (proc.stdout + proc.stderr).strip()
    except FileNotFoundError:
        return "[ERROR: ollama CLI not found]"


def query_ollama(prompt: str, model: str) -> str:
    # Try HTTP local API first, then CLI fallback
    try:
        return query_ollama_http(prompt, model)
    except Exception:
        return query_ollama_cli(prompt, model)


def clean_reply(text: str) -> str:
    """Heuristically clean model output:

    - If the model returned JSON-like fragments, try to remove role labels like
      'Assistant:' or 'User:' that are sometimes included in the generated text.
    - Collapse repeated whitespace and strip.
    """
    if not text:
        return text
    # If the response looks like a JSON object (starts with { and contains "response"),
    # try to extract the 'response' field repeatedly until we get a string.
    try:
        # Sometimes the model returns a full JSON object string; try parsing.
        obj = json.loads(text)
        if isinstance(obj, dict):
            # prefer a 'response' or 'output' key
            for k in ("response", "output", "text", "result"):
                if k in obj and isinstance(obj[k], str):
                    text = obj[k]
                    break
    except Exception:
        # not JSON — continue
        pass

    # Remove common role prefixes at line starts: 'AI:', 'Assistant:', 'User:', 'System:'
    import re
    text = re.sub(r'^(?:AI|Assistant|User|System):\s*', '', text, flags=re.MULTILINE)
    # Remove any stray repeated labels like 'User: ... Assistant:' within the text
    text = re.sub(r'\b(?:User|Assistant|AI|System):\s*', '', text)
    # Collapse multiple whitespace/newlines
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def listen_once(model: Model, device: int | None, sample_rate: int = 16000, timeout: float | None = None) -> str:
    """Listen from the default microphone until a final VOSK result is produced.

    Returns the recognized text (possibly empty string).
    """
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)
    q: queue.Queue[bytes] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=8000, dtype='int16', channels=1,
                               callback=callback, device=device):
            start = time.time()
            print("Listening (speak now)...")
            while True:
                try:
                    data = q.get(timeout=0.5)
                except queue.Empty:
                    if timeout and (time.time() - start) > timeout:
                        return ""
                    continue
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    return res.get('text', '')
                else:
                    # partial = json.loads(rec.PartialResult())
                    pass
    except KeyboardInterrupt:
        return ""
    except sd.PortAudioError as e:
        print("PortAudio error while opening the input stream:", e, file=sys.stderr)
        raise


def build_prompt(history: List[dict], user_text: str) -> str:
    # Simple role-annotated conversation history to provide context
    out = []
    for m in history[-10:]:
        role = m.get('role', 'user')
        text = m.get('text', '')
        out.append(f"{role.capitalize()}: {text}")
    out.append(f"User: {user_text}")
    out.append("Assistant:")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='./model', help='Path to VOSK model directory')
    parser.add_argument('--device', type=int, default=None, help='sounddevice device id')
    parser.add_argument('--rate', type=int, default=16000, help='sample rate')
    parser.add_argument('--ollama-model', default='tinyllama:1.1b', help='Ollama model name')
    parser.add_argument('--timeout', type=float, default=None, help='Listen timeout in seconds (per utterance)')
    parser.add_argument('--no-clean', action='store_true', help="Don't post-process/clean the model reply")
    args = parser.parse_args()

    try:
        verify_model(args.model)
    except Exception as e:
        print("VOSK model verification failed:", e, file=sys.stderr)
        return

    # Load VOSK model once
    vosk_model = Model(args.model)

    history: List[dict] = []
    print("Conversational assistant started. Press Ctrl+C to exit.")
    try:
        while True:
            user_text = listen_once(vosk_model, args.device, sample_rate=args.rate, timeout=args.timeout)
            if not user_text:
                # no speech detected
                continue
            print("Heard:", user_text)
            history.append({'role': 'user', 'text': user_text})

            prompt = build_prompt(history, user_text)
            print("Querying LLM...")
            reply = query_ollama(prompt, args.ollama_model)
            if not reply:
                reply = "Sorry, I couldn't produce a response."
            if not args.no_clean:
                try:
                    reply = clean_reply(reply)
                except Exception:
                    # if cleaning fails, keep raw reply
                    pass
            print("Assistant:", reply)
            history.append({'role': 'assistant', 'text': reply})

            # Speak the reply
            try:
                tts_say(reply)
            except Exception as e:
                print("TTS failed:", e, file=sys.stderr)

    except KeyboardInterrupt:
        print('\nExiting')


if __name__ == '__main__':
    main()
