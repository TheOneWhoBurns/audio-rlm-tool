# Audio RLM

Analyze large audio files using Recursive Language Model patterns. Transcribes audio with Whisper, then explores the transcript through a persistent REPL — keeping the full text outside your context window.

## Arguments
- `audio=<path>` — Path to an audio file (mp3, wav, m4a, etc.)
- `query=<question>` — What to find or analyze in the audio
- `model=<whisper_model>` — Whisper model size (default: small). Options: tiny, base, small, medium, large-v3
- `language=<code>` — Language code (default: auto-detect)

## Allowed tools
Read, Write, Edit, Bash, Glob, Grep, Agent

## Instructions

You are an RLM root orchestrator. Your job is to answer the user's query about an audio file by exploring its transcript efficiently — never loading the full transcript into your context.

### Phase 1: Transcribe (skip if state already exists)

Run the REPL init command:
```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py init "<audio_path>" --model <model>
```

### Phase 2: Scout

Use the REPL to understand the transcript structure:
```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(info())"
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(peek(0, 1000))"
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(peek_segments(0, 30))"
```

### Phase 3: Search & Navigate

Use targeted exploration based on the query:
```bash
# Search for keywords
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(grep('keyword'))"
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(grep_segments('pattern'))"

# Get a time range
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(time_range(120, 300))"

# Peek at segments
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(peek_segments(50, 20))"
```

### Phase 4: Chunk & Delegate (for broad queries)

If the query requires understanding the full transcript (summarization, comprehensive extraction), chunk and delegate to subagents:

```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(write_chunks())"
```

Then for each chunk file, spawn an `audio-subcall` agent:
```
Agent(subagent_type="audio-subcall", prompt="Analyze chunk: <path>\nQuery: <query>")
```

Run subcall agents **in parallel** where possible.

Collect subcall results using the buffer:
```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "add_buffer('chunk_0: <summary>')"
```

### Phase 5: Synthesize

Review buffered results and produce a final answer:
```bash
python .claude/skills/audio-rlm/scripts/audio_repl.py exec "print(get_buffers())"
```

### Strategy guide

- **Factual lookup** ("what did they say about X?") → grep first, read surrounding segments
- **Timeline/summary** ("summarize the meeting") → chunk & delegate to subcalls
- **Specific moment** ("what happened at minute 30?") → time_range directly
- **Theme extraction** ("what topics were discussed?") → peek start/end, then chunk & delegate

### Rules
1. NEVER load the full transcript into your context. Use the REPL helpers.
2. Prefer grep/time_range over reading full chunks yourself.
3. When delegating, use the `audio-subcall` agent — it's configured as the sub-LLM.
4. Keep REPL exec calls focused. One operation per call.
5. Always cite timestamps in your final answer when possible.
