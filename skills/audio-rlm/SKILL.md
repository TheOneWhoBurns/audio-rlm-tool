---
name: audio-rlm
description: Analyze local audio or video recordings with local Whisper transcription and transcript search. Use when the user provides or references an audio file such as mp3, wav, m4a, mp4, mov, or webm and wants summaries, timestamped findings, topic extraction, quote finding, or answers to "what did they say about X?" without sending audio to an external API.
---

# Audio RLM

Use this skill for recordings, interviews, meetings, podcasts, voice notes, and screen captures where the useful content is spoken audio.

## Quick Start

Use the skill scripts from anywhere:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/audio-rlm"

python3 "$SKILL_DIR/scripts/transcribe.py" "/absolute/path/to/file.mp3" --model small
python3 "$SKILL_DIR/scripts/repl.py" list
python3 "$SKILL_DIR/scripts/repl.py" load file
python3 "$SKILL_DIR/scripts/repl.py" info
python3 "$SKILL_DIR/scripts/repl.py" peek 0 20
```

Data is stored in `${AUDIO_RLM_HOME:-${CODEX_HOME:-$HOME/.codex}/audio-rlm}`:

- `transcripts/` for JSON transcripts
- `chunks/` for timestamped chunk files
- `session.json` for the active transcript and scratch buffers

## Workflow

1. Transcribe once unless a matching transcript already exists.
2. Load the transcript and scout with `info` and `peek`.
3. For targeted questions, prefer `grep`, `time`, and nearby `peek`.
4. For broad questions, run `chunk --size 50` and inspect chunk files progressively.
5. If the user explicitly asks for sub-agents or parallel agent work, delegate chunk review in parallel. Otherwise inspect chunks locally.
6. Answer with timestamp citations like `[00:12:34]`.

## Useful Commands

Targeted search:

```bash
python3 "$SKILL_DIR/scripts/repl.py" grep "budget"
python3 "$SKILL_DIR/scripts/repl.py" grep "budget" --max 20
python3 "$SKILL_DIR/scripts/repl.py" time 600 900
python3 "$SKILL_DIR/scripts/repl.py" peek 50 20
```

Broad coverage:

```bash
python3 "$SKILL_DIR/scripts/repl.py" chunk --size 50
python3 "$SKILL_DIR/scripts/repl.py" buffer add "summary text"
python3 "$SKILL_DIR/scripts/repl.py" buffer list
```

Maintenance:

```bash
python3 "$SKILL_DIR/scripts/repl.py" list
python3 "$SKILL_DIR/scripts/repl.py" reset
```

## Rules

- Never load a full long transcript into context if `grep`, `time`, `peek`, or `chunk` can narrow the search.
- Reuse existing transcripts when possible.
- Prefer direct transcript evidence over inference.
- Call out low confidence when the audio is noisy, clipped, multilingual, or poorly transcribed.
- Mention the transcript path or chunk path when it materially helps the user continue work.

## Requirements

- Python 3.10+
- `faster-whisper` installed in the Python environment used by `python3`
- `ffmpeg` available on the system path
