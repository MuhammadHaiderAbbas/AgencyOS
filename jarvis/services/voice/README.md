# JARVIS Voice Service (Phase 6 — interface)

Pipeline: Mic → VAD (Silero/webrtcvad) → STT (Whisper local / cloud) → Intent → LLM → TTS (Piper / cloud) → Speaker

- Wake-word "Jarvis" runs locally (openWakeWord).
- Interruption via VAD energy.
- Indicators when mic active.
- No continuous cloud upload without consent.
