# audio-rlm-tool

Analyze large audio files using Recursive Language Model patterns — no API keys, runs entirely through Claude Code.

## Architecture

```
audio file → transcribe.py (faster-whisper, local) → JSON transcript
                                                         ↓
                                              repl.py (exploration REPL)
                                              ├── peek, grep, time  → targeted search
                                              └── chunk → audio-subcall agents → synthesize
```

- **Root LLM**: Your Claude Code session (Opus/Sonnet)
- **Sub-LLM**: `audio-subcall` agent (Haiku by default — change in `.claude/agents/audio-subcall.md`)
- **Data**: JSON transcripts in `.claude/audio-rlm/transcripts/`, never loaded into context

## Quick start

```
/audio-rlm audio=/path/to/file.mp3 query="What was discussed?"
```

## Manual usage

```bash
# transcribe
python .claude/skills/audio-rlm/scripts/transcribe.py "recording.mp3"

# explore
python .claude/skills/audio-rlm/scripts/repl.py list
python .claude/skills/audio-rlm/scripts/repl.py load recording
python .claude/skills/audio-rlm/scripts/repl.py grep "budget"
python .claude/skills/audio-rlm/scripts/repl.py time 600 900
python .claude/skills/audio-rlm/scripts/repl.py chunk
```

## Requirements

- Python 3.10+
- `pip install faster-whisper`

## File layout

```
.claude/
├── skills/audio-rlm/
│   ├── SKILL.md              # orchestration skill
│   └── scripts/
│       ├── transcribe.py     # audio → JSON transcript
│       └── repl.py           # transcript exploration REPL
├── agents/
│   └── audio-subcall.md      # sub-LLM (bring your own model)
└── audio-rlm/                # data (gitignored)
    ├── transcripts/          # JSON transcript files
    ├── chunks/               # ephemeral chunk files
    └── session.json          # active transcript + buffers
```
