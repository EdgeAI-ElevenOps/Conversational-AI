# Conversation AI - Raspberry Pi 4: Offline TTS + LLM Processing + STT demo

This small project demonstrates offline speech-to-text (STT) using VOSK and text-to-speech (TTS) using `pyttsx3` (which uses `espeak` on Linux) on a Raspberry Pi 4.

Files
- `tts_stt.py` — main demo script. Modes: `demo`, `listen`, `say`.
- `requirements.txt` — Python packages to install in a virtualenv.
- `download_model.sh` — helper to download a VOSK model (you must provide a model URL or download manually).

Quick setup (on Raspberry Pi OS / Debian):

1. System packages (run as root or with sudo):

```bash
apt update
apt install -y python3 python3-venv python3-pip build-essential libsndfile1 ffmpeg \
  libportaudio2 portaudio19-dev espeak curl unzip
```

2. Create a virtualenv and install Python deps:

```bash
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

3. Download a VOSK model (small models recommended on Pi 4). Visit https://alphacephei.com/vosk/models to pick a model. Example download flow (replace MODEL_URL with chosen model):

```bash
# from project root
./download_model.sh "MODEL_URL" ./model
```

If you prefer manual download, download and unzip the model into `./model` so the model files are in `./model`.

4. Run the demo (with the virtualenv activated):

- Demo mode: recognizes speech and speaks back the recognized text.

```bash
python tts_stt.py demo --model ./model
```

- Listen-only (prints recognized text):

```bash
python tts_stt.py listen --model ./model
```

- Say text (TTS):

```bash
python tts_stt.py say "Hello from Raspberry Pi"
```

Notes and tips
- VOSK prefers 16 kHz mono audio. The script attempts to open your default microphone at 16kHz. If you have a different device, set `--device`.
- For better accuracy, use a higher-quality model if you can afford memory/CPU.
- If `pyttsx3` doesn't work, `espeak` should be available as a fallback; ensure `espeak` is installed.

Troubleshooting: PortAudio / sounddevice errors

If you run `python tts_stt.py` and see an error like "PortAudio library not found" or "OSError: PortAudio library not found", install the PortAudio system packages and then reinstall the Python package inside your virtualenv:

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
# then inside your venv
pip install --upgrade pip
pip install sounddevice
```

If you're on a different Linux distribution, use your package manager to install the PortAudio runtime and development headers (the package names may differ).

Next steps
- Try `whisper.cpp` or OpenAI Whisper (if you have a GPU or heavy CPU) for better accuracy.
- Consider offline neural TTS (Coqui TTS / VITS) if you need more natural voice (requires more resources).

