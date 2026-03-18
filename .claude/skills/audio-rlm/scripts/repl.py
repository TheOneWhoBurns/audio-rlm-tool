#!/usr/bin/env python3
"""Persistent REPL for exploring audio transcripts.

Operates on JSON transcript files produced by transcribe.py.
State (buffers, active transcript) stored as JSON — no pickle.

Commands:
    python repl.py list                          # list available transcripts
    python repl.py load <name>                   # set active transcript
    python repl.py info                          # metadata for active transcript
    python repl.py peek [start_idx] [count]      # show segments by index
    python repl.py grep <pattern> [--max N]      # search segments
    python repl.py time <start_sec> <end_sec>    # segments in time range
    python repl.py chunk [--size N]              # write timestamped chunks to disk
    python repl.py buffer add <text>             # append to buffer
    python repl.py buffer list                   # show buffers
    python repl.py buffer clear                  # clear buffers
    python repl.py exec "<python_code>"          # arbitrary code (ephemeral vars)
    python repl.py reset                         # clear session + chunks
"""

import sys
import os
import json
import re
import io
from pathlib import Path

DATA_DIR = Path(".claude/audio-rlm")
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
CHUNKS_DIR = DATA_DIR / "chunks"
SESSION_FILE = DATA_DIR / "session.json"
MAX_OUTPUT = 8000


# --- Session management (JSON, not pickle) ---

def load_session() -> dict:
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            return json.load(f)
    return {"active": None, "buffers": []}


def save_session(session: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def load_transcript(name: str) -> dict | None:
    path = TRANSCRIPTS_DIR / f"{name}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_active_transcript(session: dict) -> tuple[str, dict]:
    """Load the active transcript, or error."""
    name = session.get("active")
    if not name:
        print("ERROR: No active transcript. Run: python repl.py load <name>")
        print("       See available: python repl.py list")
        sys.exit(1)
    data = load_transcript(name)
    if data is None:
        print(f"ERROR: Transcript '{name}' not found. Run: python repl.py list")
        sys.exit(1)
    return name, data


# --- Helpers ---

def ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_segment(seg: dict) -> str:
    return f"[{ts(seg['start'])} -> {ts(seg['end'])}] {seg['text']}"


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n... [truncated at {MAX_OUTPUT} chars]"


# --- Commands ---

def cmd_list(_args):
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(TRANSCRIPTS_DIR.glob("*.json"))
    if not files:
        print("No transcripts found. Run transcribe.py first.")
        return

    session = load_session()
    active = session.get("active")

    for f in files:
        name = f.stem
        marker = " *" if name == active else ""
        try:
            with open(f) as fh:
                meta = json.load(fh)
            dur = meta.get("duration_seconds", 0)
            lang = meta.get("language", "?")
            segs = meta.get("segment_count", 0)
            print(f"  {name}{marker}  [{ts(dur)}] {lang} ({segs} segments)")
        except (json.JSONDecodeError, KeyError):
            print(f"  {name}{marker}  [corrupt]")


def cmd_load(args):
    if not args:
        print("Usage: python repl.py load <name>")
        sys.exit(1)

    name = args[0]
    data = load_transcript(name)
    if data is None:
        print(f"ERROR: Transcript '{name}' not found.")
        cmd_list([])
        sys.exit(1)

    session = load_session()
    session["active"] = name
    session["buffers"] = []  # fresh buffers for new transcript
    save_session(session)

    dur = data.get("duration_seconds", 0)
    print(f"Loaded '{name}'  [{ts(dur)}]  {data.get('language', '?')}  ({data.get('segment_count', 0)} segments)")


def cmd_info(_args):
    session = load_session()
    name, data = get_active_transcript(session)
    meta = {k: v for k, v in data.items() if k != "segments"}
    meta["active_name"] = name
    meta["buffer_count"] = len(session.get("buffers", []))
    print(json.dumps(meta, indent=2))


def cmd_peek(args):
    session = load_session()
    _, data = get_active_transcript(session)
    segments = data["segments"]

    start_idx = int(args[0]) if len(args) > 0 else 0
    count = int(args[1]) if len(args) > 1 else 20

    sliced = segments[start_idx:start_idx + count]
    if not sliced:
        print(f"No segments at index {start_idx}. Total: {len(segments)}")
        return

    lines = [f"[idx {start_idx + i}] {format_segment(seg)}" for i, seg in enumerate(sliced)]
    print(truncate("\n".join(lines)))


def cmd_grep(args):
    if not args:
        print("Usage: python repl.py grep <pattern> [--max N]")
        sys.exit(1)

    pattern = args[0]
    max_matches = 10

    i = 1
    while i < len(args):
        if args[i] == "--max" and i + 1 < len(args):
            max_matches = int(args[i + 1])
            i += 2
        else:
            i += 1

    session = load_session()
    _, data = get_active_transcript(session)

    results = []
    for idx, seg in enumerate(data["segments"]):
        if re.search(pattern, seg["text"], re.IGNORECASE):
            results.append(f"[idx {idx}] {format_segment(seg)}")
            if len(results) >= max_matches:
                break

    if results:
        print(truncate("\n".join(results)))
    else:
        print(f"No matches for '{pattern}'.")


def cmd_time(args):
    if len(args) < 2:
        print("Usage: python repl.py time <start_sec> <end_sec>")
        sys.exit(1)

    start_sec = float(args[0])
    end_sec = float(args[1])

    session = load_session()
    _, data = get_active_transcript(session)

    results = []
    for seg in data["segments"]:
        if seg["end"] >= start_sec and seg["start"] <= end_sec:
            results.append(format_segment(seg))

    if results:
        print(truncate("\n".join(results)))
    else:
        print(f"No segments between {ts(start_sec)} and {ts(end_sec)}.")


def cmd_chunk(args):
    """Write timestamped chunks to disk for subcall agents."""
    session = load_session()
    name, data = get_active_transcript(session)
    segments = data["segments"]

    # default: ~50 segments per chunk (respects speech boundaries)
    segs_per_chunk = 50
    i = 0
    while i < len(args):
        if args[i] == "--size" and i + 1 < len(args):
            segs_per_chunk = int(args[i + 1])
            i += 2
        else:
            i += 1

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    # clear old chunks
    for old in CHUNKS_DIR.glob(f"{name}_*.txt"):
        old.unlink()

    paths = []
    for chunk_idx in range(0, len(segments), segs_per_chunk):
        chunk_segs = segments[chunk_idx:chunk_idx + segs_per_chunk]
        # write with timestamps so subcall agents can cite them
        lines = [format_segment(seg) for seg in chunk_segs]

        chunk_path = CHUNKS_DIR / f"{name}_{chunk_idx:04d}.txt"
        chunk_path.write_text("\n".join(lines))
        paths.append(str(chunk_path))

        t_start = ts(chunk_segs[0]["start"])
        t_end = ts(chunk_segs[-1]["end"])
        print(f"  {chunk_path}  ({len(chunk_segs)} segs, {t_start} -> {t_end})")

    print(f"\n{len(paths)} chunks written to {CHUNKS_DIR}/")
    print(json.dumps(paths))


def cmd_buffer(args):
    if not args:
        print("Usage: python repl.py buffer add|list|clear")
        sys.exit(1)

    session = load_session()
    sub = args[0]

    if sub == "add":
        text = " ".join(args[1:]) if len(args) > 1 else ""
        if not text:
            # read from stdin if no inline text
            text = sys.stdin.read().strip()
        if not text:
            print("ERROR: No text provided.")
            sys.exit(1)
        session.setdefault("buffers", []).append(text)
        save_session(session)
        print(f"Buffer added ({len(session['buffers'])} total)")

    elif sub == "list":
        buffers = session.get("buffers", [])
        if not buffers:
            print("(no buffers)")
            return
        for i, buf in enumerate(buffers):
            print(f"--- buffer {i} ---")
            print(truncate(buf))

    elif sub == "clear":
        session["buffers"] = []
        save_session(session)
        print("Buffers cleared.")

    else:
        print(f"Unknown buffer command: {sub}")


def cmd_exec(args):
    """Run arbitrary Python with transcript helpers in scope. Variables are ephemeral."""
    code = args[0] if args else sys.stdin.read()
    if not code.strip():
        print("ERROR: No code provided.")
        sys.exit(1)

    session = load_session()
    name, data = get_active_transcript(session)
    segments = data["segments"]
    content = " ".join(seg["text"] for seg in segments)

    # build exec environment
    env = {
        "content": content,
        "segments": segments,
        "data": data,
        "session": session,
        "ts": ts,
        "format_segment": format_segment,
        "re": re,
        "json": json,
    }

    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()

    try:
        exec(code, env)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    finally:
        sys.stdout = old_stdout

    output = capture.getvalue()

    # persist buffer changes if exec modified session
    save_session(session)

    print(truncate(output), end="")


def cmd_reset(_args):
    import shutil
    for path in [SESSION_FILE, CHUNKS_DIR]:
        if path.is_file():
            path.unlink()
            print(f"Removed {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            print(f"Removed {path}/")
    print("Session reset. Transcripts preserved.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    commands = {
        "list": cmd_list,
        "load": cmd_load,
        "info": cmd_info,
        "peek": cmd_peek,
        "grep": cmd_grep,
        "time": cmd_time,
        "chunk": cmd_chunk,
        "buffer": cmd_buffer,
        "exec": cmd_exec,
        "reset": cmd_reset,
    }

    if cmd in commands:
        commands[cmd](rest)
    else:
        print(f"Unknown command: {cmd}")
        print("Available: " + ", ".join(commands.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
