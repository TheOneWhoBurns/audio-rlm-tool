---
name: audio-rlm
description: Analyze large audio files using RLM patterns. Transcribes with Whisper, explores via persistent REPL, delegates to subcall agents.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
---

# audio-rlm

Use when the user provides an audio file and wants information extracted from it.

## Inputs

From `$ARGUMENTS`:
- `audio=<path>` — path to audio file (required for first use)
- `query=<question>` — what to find or analyze (required)
- `model=<size>` — whisper model: tiny, base, small (default), medium, large-v3
- `name=<name>` — custom transcript name (default: derived from filename)

If arguments are missing, ask the user.

## Workflow

### 1. Transcribe (skip if already done)

Check if transcript exists:
```bash
python .claude/skills/audio-rlm/scripts/repl.py list
```

If not, transcribe:
```bash
python .claude/skills/audio-rlm/scripts/transcribe.py "<audio_path>" --model small
```

Then load:
```bash
python .claude/skills/audio-rlm/scripts/repl.py load <name>
```

### 2. Scout

```bash
python .claude/skills/audio-rlm/scripts/repl.py info
python .claude/skills/audio-rlm/scripts/repl.py peek 0 30
```

### 3. Search (for targeted queries)

```bash
python .claude/skills/audio-rlm/scripts/repl.py grep "keyword"
python .claude/skills/audio-rlm/scripts/repl.py grep "keyword" --max 20
python .claude/skills/audio-rlm/scripts/repl.py time 120 300
python .claude/skills/audio-rlm/scripts/repl.py peek 50 20
```

### 4. Chunk & delegate (for broad queries)

When the query needs full-transcript coverage (summaries, theme extraction, comprehensive search):

```bash
python .claude/skills/audio-rlm/scripts/repl.py chunk --size 50
```

Then for each chunk path, spawn an `audio-subcall` agent **in parallel**:
```
Agent(name="audio-subcall", prompt="Chunk: <path>\nQuery: <query>")
```

Store each result:
```bash
python .claude/skills/audio-rlm/scripts/repl.py buffer add "<result_summary>"
```

### 5. Synthesize

```bash
python .claude/skills/audio-rlm/scripts/repl.py buffer list
```

Produce the final answer with timestamp citations.

## Decision tree

| Query type | Strategy |
|---|---|
| "what did they say about X?" | grep → read surrounding segments |
| "what happened at minute 30?" | time 1800 1860 |
| "summarize this" | chunk → delegate → synthesize |
| "what topics came up?" | peek start + end, then chunk → delegate |
| "find all mentions of X" | grep --max 50 |

## Rules

1. NEVER read full transcript into context. Use the REPL.
2. One operation per REPL call — keep calls focused.
3. Prefer grep/time over reading whole chunks yourself.
4. Use `audio-subcall` agent for chunk analysis, not inline reading.
5. Cite timestamps `[HH:MM:SS]` in your final answer.
6. Run subcall agents in parallel when possible.
