# audio-rlm-tool

A Claude Code tool for analyzing large audio files using Recursive Language Model patterns.

## How it works

1. Transcribes audio locally with faster-whisper
2. Stores the transcript in a persistent REPL (outside context window)
3. The root LLM explores via helper functions: `peek`, `grep`, `time_range`, `peek_segments`
4. For broad queries, chunks the transcript and delegates to `audio-subcall` subagents in parallel

## Usage

Use the `/audio-rlm` skill:
```
/audio-rlm audio=/path/to/file.mp3 query="What topics were discussed?"
```

Or manually:
```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py init "path/to/audio.mp3"
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(info())"
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(grep('topic'))"
```

## Requirements

- Python 3.10+
- faster-whisper (`pip install faster-whisper`)

## Sub-model

The subcall agent uses Haiku by default. Change the `model:` field in `.claude/agents/audio-subcall.md` to use a different sub-LLM.
