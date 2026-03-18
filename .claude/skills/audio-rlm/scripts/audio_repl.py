#!/usr/bin/env python3
"""
Persistent REPL for audio-rlm-tool.

Handles: transcription (via faster-whisper), state persistence,
and helper functions for exploring transcripts from within Claude Code.

Usage:
    python audio_repl.py init <audio_file> [--model small] [--language en]
    python audio_repl.py exec "<python_code>"
    python audio_repl.py reset
"""

import sys
import os
import pickle
import json
import re
import textwrap
from pathlib import Path

STATE_DIR = Path(".claude/rlm_state")
STATE_FILE = STATE_DIR / "state.pkl"
CHUNKS_DIR = STATE_DIR / "chunks"
MAX_OUTPUT = 8000


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)
    return {}


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "wb") as f:
        pickle.dump(state, f)


def transcribe(audio_path: str, model_size: str = "small", language: str | None = None) -> dict:
    """Run faster-whisper on an audio file. Returns dict with segments and full text."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")
        sys.exit(1)

    print(f"Loading whisper model '{model_size}'...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing '{audio_path}'...")
    raw_segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=False,
    )

    segments = []
    full_text_parts = []
    for seg in raw_segments:
        entry = {
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        }
        segments.append(entry)
        full_text_parts.append(seg.text.strip())

    full_text = " ".join(full_text_parts)

    return {
        "segments": segments,
        "full_text": full_text,
        "language": info.language,
        "language_probability": round(info.language_probability, 2),
        "duration": round(info.duration, 2),
    }


def fmt_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# --- Helper functions injected into the REPL exec environment ---

def make_helpers(state: dict) -> dict:
    """Build helper functions that close over the current state."""

    content = state.get("full_text", "")
    segments = state.get("segments", [])

    def peek(start: int = 0, end: int = 500) -> str:
        """Peek at a slice of the full transcript text."""
        return content[start:end]

    def peek_segments(start_idx: int = 0, count: int = 20) -> str:
        """Show a range of timestamped segments."""
        sliced = segments[start_idx:start_idx + count]
        lines = []
        for s in sliced:
            lines.append(f"[{fmt_timestamp(s['start'])} -> {fmt_timestamp(s['end'])}] {s['text']}")
        return "\n".join(lines)

    def grep(pattern: str, max_matches: int = 10, window: int = 200, flags: int = re.IGNORECASE) -> str:
        """Search the transcript for a regex pattern. Returns matches with surrounding context."""
        results = []
        for match in re.finditer(pattern, content, flags):
            start = max(0, match.start() - window)
            end = min(len(content), match.end() + window)
            snippet = content[start:end]
            char_pos = match.start()
            # find which segment this falls in
            ts = "??"
            running = 0
            for seg in segments:
                seg_len = len(seg["text"]) + 1  # +1 for space
                if running + seg_len > char_pos:
                    ts = fmt_timestamp(seg["start"])
                    break
                running += seg_len
            results.append(f"[~{ts}] (char {char_pos}): ...{snippet}...")
            if len(results) >= max_matches:
                break
        return "\n---\n".join(results) if results else "No matches found."

    def grep_segments(pattern: str, max_matches: int = 10, flags: int = re.IGNORECASE) -> str:
        """Search segments by regex, returning timestamped matches."""
        results = []
        for seg in segments:
            if re.search(pattern, seg["text"], flags):
                results.append(f"[{fmt_timestamp(seg['start'])} -> {fmt_timestamp(seg['end'])}] {seg['text']}")
                if len(results) >= max_matches:
                    break
        return "\n".join(results) if results else "No matches found."

    def time_range(start_sec: float, end_sec: float) -> str:
        """Get all transcript text between two timestamps (in seconds)."""
        parts = []
        for seg in segments:
            if seg["end"] >= start_sec and seg["start"] <= end_sec:
                parts.append(f"[{fmt_timestamp(seg['start'])}] {seg['text']}")
        return "\n".join(parts) if parts else "No segments in that range."

    def chunk_indices(size: int = 200_000, overlap: int = 1000) -> list[tuple[int, int]]:
        """Return (start, end) character spans for chunking the transcript."""
        indices = []
        start = 0
        while start < len(content):
            end = min(start + size, len(content))
            indices.append((start, end))
            start = end - overlap
        return indices

    def write_chunks(out_dir: str = None, size: int = 200_000, overlap: int = 1000, prefix: str = "chunk") -> str:
        """Write transcript chunks to disk files. Returns list of file paths."""
        target = Path(out_dir) if out_dir else CHUNKS_DIR
        target.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, (s, e) in enumerate(chunk_indices(size, overlap)):
            p = target / f"{prefix}_{i:04d}.txt"
            p.write_text(content[s:e])
            paths.append(str(p))
        return json.dumps(paths)

    def info() -> str:
        """Show metadata about the loaded audio."""
        meta = {k: v for k, v in state.items() if k not in ("full_text", "segments")}
        meta["transcript_length"] = len(content)
        meta["segment_count"] = len(segments)
        return json.dumps(meta, indent=2)

    buffers = state.get("buffers", [])

    def add_buffer(text: str):
        """Append to the results buffer."""
        buffers.append(text)
        state["buffers"] = buffers

    def get_buffers() -> str:
        """Return all buffered results."""
        return "\n---\n".join(buffers) if buffers else "(empty)"

    def clear_buffers():
        """Clear the results buffer."""
        buffers.clear()
        state["buffers"] = []

    return {
        "content": content,
        "segments": segments,
        "peek": peek,
        "peek_segments": peek_segments,
        "grep": grep,
        "grep_segments": grep_segments,
        "time_range": time_range,
        "chunk_indices": chunk_indices,
        "write_chunks": write_chunks,
        "info": info,
        "add_buffer": add_buffer,
        "get_buffers": get_buffers,
        "clear_buffers": clear_buffers,
        "fmt_timestamp": fmt_timestamp,
        "buffers": buffers,
        "re": re,
        "json": json,
    }


def cmd_init(args):
    audio_path = args[0]
    if not os.path.isfile(audio_path):
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    model_size = "small"
    language = None
    i = 1
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model_size = args[i + 1]
            i += 2
        elif args[i] == "--language" and i + 1 < len(args):
            language = args[i + 1]
            i += 2
        else:
            i += 1

    result = transcribe(audio_path, model_size, language)

    state = {
        "source_file": os.path.abspath(audio_path),
        "model_size": model_size,
        "full_text": result["full_text"],
        "segments": result["segments"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "duration": result["duration"],
        "buffers": [],
    }

    save_state(state)

    print(f"Transcription complete.")
    print(f"  Duration: {fmt_timestamp(result['duration'])}")
    print(f"  Language: {result['language']} ({result['language_probability']})")
    print(f"  Segments: {len(result['segments'])}")
    print(f"  Characters: {len(result['full_text'])}")
    print(f"  State saved to: {STATE_FILE}")


def cmd_exec(args):
    code = args[0] if args else ""
    if not code.strip():
        print("ERROR: No code provided.")
        sys.exit(1)

    state = load_state()
    if not state:
        print("ERROR: No state loaded. Run 'init' first.")
        sys.exit(1)

    helpers = make_helpers(state)

    # capture stdout
    import io
    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()

    try:
        exec(code, helpers)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    finally:
        sys.stdout = old_stdout

    output = capture.getvalue()

    # save any state mutations (buffers, etc)
    save_state(state)

    # truncate output
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n... [truncated at {MAX_OUTPUT} chars, {len(output)} total]"

    print(output, end="")


def cmd_reset(_args):
    import shutil
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print("State cleared.")
    else:
        print("No state to clear.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    commands = {
        "init": cmd_init,
        "exec": cmd_exec,
        "reset": cmd_reset,
    }

    if cmd in commands:
        commands[cmd](rest)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
