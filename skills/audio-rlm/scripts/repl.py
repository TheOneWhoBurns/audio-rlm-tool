#!/usr/bin/env python3
"""Persistent transcript explorer for audio-rlm.

Global option:
    --data-dir /path/to/audio-rlm-home

Commands:
    python3 repl.py list
    python3 repl.py load <name>
    python3 repl.py info
    python3 repl.py peek [start_idx] [count]
    python3 repl.py grep <pattern> [--max N]
    python3 repl.py time <start_sec> <end_sec>
    python3 repl.py chunk [--size N]
    python3 repl.py buffer add <text>
    python3 repl.py buffer list
    python3 repl.py buffer clear
    python3 repl.py exec "<python_code>"
    python3 repl.py reset
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
from pathlib import Path


MAX_OUTPUT = 8000
DATA_DIR = Path(".")
TRANSCRIPTS_DIR = Path(".")
CHUNKS_DIR = Path(".")
SESSION_FILE = Path(".")


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def default_data_dir() -> Path:
    return Path(
        os.environ.get("AUDIO_RLM_HOME", str(default_codex_home() / "audio-rlm"))
    ).expanduser()


def configure_paths(data_dir: Path) -> None:
    global DATA_DIR, TRANSCRIPTS_DIR, CHUNKS_DIR, SESSION_FILE
    DATA_DIR = data_dir
    TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
    CHUNKS_DIR = DATA_DIR / "chunks"
    SESSION_FILE = DATA_DIR / "session.json"


def parse_global_args(argv: list[str]) -> list[str]:
    data_dir = None
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--data-dir":
            if index + 1 >= len(argv):
                print("ERROR: --data-dir requires a value.")
                sys.exit(1)
            data_dir = Path(argv[index + 1]).expanduser()
            index += 2
            continue
        rest.append(token)
        index += 1

    configure_paths(data_dir or default_data_dir())
    return rest


def load_session() -> dict:
    if SESSION_FILE.exists():
        with SESSION_FILE.open(encoding="utf-8") as handle:
            return json.load(handle)
    return {"active": None, "buffers": []}


def save_session(session: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SESSION_FILE.open("w", encoding="utf-8") as handle:
        json.dump(session, handle, indent=2, ensure_ascii=False)


def load_transcript(name: str) -> dict | None:
    path = TRANSCRIPTS_DIR / f"{name}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_active_transcript(session: dict) -> tuple[str, dict]:
    name = session.get("active")
    if not name:
        print("ERROR: No active transcript. Run: python3 repl.py load <name>")
        print("       See available: python3 repl.py list")
        sys.exit(1)

    data = load_transcript(name)
    if data is None:
        print(f"ERROR: Transcript '{name}' not found. Run: python3 repl.py list")
        sys.exit(1)
    return name, data


def ts(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_segment(segment: dict) -> str:
    return f"[{ts(segment['start'])} -> {ts(segment['end'])}] {segment['text']}"


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n... [truncated at {MAX_OUTPUT} chars]"


def cmd_list(_args: list[str]) -> None:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(TRANSCRIPTS_DIR.glob("*.json"))
    if not files:
        print(f"No transcripts found in {TRANSCRIPTS_DIR}. Run transcribe.py first.")
        return

    session = load_session()
    active = session.get("active")

    for path in files:
        name = path.stem
        marker = " *" if name == active else ""
        try:
            with path.open(encoding="utf-8") as handle:
                meta = json.load(handle)
            duration = meta.get("duration_seconds", 0)
            language = meta.get("language", "?")
            segments = meta.get("segment_count", 0)
            print(f"  {name}{marker}  [{ts(duration)}] {language} ({segments} segments)")
        except (json.JSONDecodeError, KeyError):
            print(f"  {name}{marker}  [corrupt]")


def cmd_load(args: list[str]) -> None:
    if not args:
        print("Usage: python3 repl.py load <name>")
        sys.exit(1)

    name = args[0]
    data = load_transcript(name)
    if data is None:
        print(f"ERROR: Transcript '{name}' not found.")
        cmd_list([])
        sys.exit(1)

    session = load_session()
    session["active"] = name
    session["buffers"] = []
    save_session(session)

    duration = data.get("duration_seconds", 0)
    language = data.get("language", "?")
    segments = data.get("segment_count", 0)
    print(f"Loaded '{name}'  [{ts(duration)}]  {language}  ({segments} segments)")


def cmd_info(_args: list[str]) -> None:
    session = load_session()
    name, data = get_active_transcript(session)
    meta = {key: value for key, value in data.items() if key != "segments"}
    meta["active_name"] = name
    meta["buffer_count"] = len(session.get("buffers", []))
    meta["data_dir"] = str(DATA_DIR)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


def cmd_peek(args: list[str]) -> None:
    session = load_session()
    _, data = get_active_transcript(session)
    segments = data["segments"]

    start_idx = int(args[0]) if len(args) > 0 else 0
    count = int(args[1]) if len(args) > 1 else 20
    sliced = segments[start_idx : start_idx + count]
    if not sliced:
        print(f"No segments at index {start_idx}. Total: {len(segments)}")
        return

    lines = [
        f"[idx {start_idx + offset}] {format_segment(segment)}"
        for offset, segment in enumerate(sliced)
    ]
    print(truncate("\n".join(lines)))


def cmd_grep(args: list[str]) -> None:
    if not args:
        print("Usage: python3 repl.py grep <pattern> [--max N]")
        sys.exit(1)

    pattern = args[0]
    max_matches = 10

    index = 1
    while index < len(args):
        if args[index] == "--max" and index + 1 < len(args):
            max_matches = int(args[index + 1])
            index += 2
            continue
        index += 1

    session = load_session()
    _, data = get_active_transcript(session)

    results = []
    for idx, segment in enumerate(data["segments"]):
        if re.search(pattern, segment["text"], re.IGNORECASE):
            results.append(f"[idx {idx}] {format_segment(segment)}")
            if len(results) >= max_matches:
                break

    if results:
        print(truncate("\n".join(results)))
    else:
        print(f"No matches for '{pattern}'.")


def cmd_time(args: list[str]) -> None:
    if len(args) < 2:
        print("Usage: python3 repl.py time <start_sec> <end_sec>")
        sys.exit(1)

    start_sec = float(args[0])
    end_sec = float(args[1])

    session = load_session()
    _, data = get_active_transcript(session)

    results = []
    for segment in data["segments"]:
        if segment["end"] >= start_sec and segment["start"] <= end_sec:
            results.append(format_segment(segment))

    if results:
        print(truncate("\n".join(results)))
    else:
        print(f"No segments between {ts(start_sec)} and {ts(end_sec)}.")


def cmd_chunk(args: list[str]) -> None:
    session = load_session()
    name, data = get_active_transcript(session)
    segments = data["segments"]
    segs_per_chunk = 50

    index = 0
    while index < len(args):
        if args[index] == "--size" and index + 1 < len(args):
            segs_per_chunk = int(args[index + 1])
            index += 2
            continue
        index += 1

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    for old_path in CHUNKS_DIR.glob(f"{name}_*.txt"):
        old_path.unlink()

    chunk_paths = []
    for chunk_idx in range(0, len(segments), segs_per_chunk):
        chunk_segments = segments[chunk_idx : chunk_idx + segs_per_chunk]
        lines = [format_segment(segment) for segment in chunk_segments]
        chunk_path = CHUNKS_DIR / f"{name}_{chunk_idx:04d}.txt"
        chunk_path.write_text("\n".join(lines), encoding="utf-8")
        chunk_paths.append(str(chunk_path))

        start_ts = ts(chunk_segments[0]["start"])
        end_ts = ts(chunk_segments[-1]["end"])
        print(f"  {chunk_path}  ({len(chunk_segments)} segs, {start_ts} -> {end_ts})")

    print(f"\n{len(chunk_paths)} chunks written to {CHUNKS_DIR}/")
    print(json.dumps(chunk_paths, ensure_ascii=False))


def cmd_buffer(args: list[str]) -> None:
    if not args:
        print("Usage: python3 repl.py buffer add|list|clear")
        sys.exit(1)

    session = load_session()
    subcommand = args[0]

    if subcommand == "add":
        text = " ".join(args[1:]) if len(args) > 1 else sys.stdin.read().strip()
        if not text:
            print("ERROR: No text provided.")
            sys.exit(1)
        session.setdefault("buffers", []).append(text)
        save_session(session)
        print(f"Buffer added ({len(session['buffers'])} total)")
        return

    if subcommand == "list":
        buffers = session.get("buffers", [])
        if not buffers:
            print("(no buffers)")
            return
        for idx, buffer_text in enumerate(buffers):
            print(f"--- buffer {idx} ---")
            print(truncate(buffer_text))
        return

    if subcommand == "clear":
        session["buffers"] = []
        save_session(session)
        print("Buffers cleared.")
        return

    print(f"Unknown buffer command: {subcommand}")
    sys.exit(1)


def cmd_exec(args: list[str]) -> None:
    code = args[0] if args else sys.stdin.read()
    if not code.strip():
        print("ERROR: No code provided.")
        sys.exit(1)

    session = load_session()
    name, data = get_active_transcript(session)
    segments = data["segments"]
    content = " ".join(segment["text"] for segment in segments)

    env = {
        "content": content,
        "segments": segments,
        "data": data,
        "name": name,
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
    except Exception as exc:  # noqa: S102
        print(f"ERROR: {type(exc).__name__}: {exc}")
    finally:
        sys.stdout = old_stdout

    save_session(session)
    print(truncate(capture.getvalue()), end="")


def cmd_reset(_args: list[str]) -> None:
    for path in (SESSION_FILE, CHUNKS_DIR):
        if path.is_file():
            path.unlink()
            print(f"Removed {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            print(f"Removed {path}/")
    print("Session reset. Transcripts preserved.")


def main() -> None:
    argv = parse_global_args(sys.argv[1:])
    if not argv:
        print(__doc__)
        sys.exit(1)

    command = argv[0]
    rest = argv[1:]
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

    handler = commands.get(command)
    if handler is None:
        print(f"Unknown command: {command}")
        print("Available: " + ", ".join(commands.keys()))
        sys.exit(1)
    handler(rest)


if __name__ == "__main__":
    main()
