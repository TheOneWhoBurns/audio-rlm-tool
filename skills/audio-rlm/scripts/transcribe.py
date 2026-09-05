#!/usr/bin/env python3
"""Transcribe an audio file with faster-whisper and save it as JSON.

Usage:
    python3 transcribe.py /path/to/file.mp3 [--model small] [--language en]
    python3 transcribe.py /path/to/file.mp3 [--name custom-name] [--data-dir /tmp/audio-rlm]

Default output:
    ${AUDIO_RLM_HOME:-${CODEX_HOME:-~/.codex}/audio-rlm}/transcripts/<name>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def default_data_dir() -> Path:
    return Path(
        os.environ.get("AUDIO_RLM_HOME", str(default_codex_home() / "audio-rlm"))
    ).expanduser()


def derive_name(audio_path: Path) -> str:
    return audio_path.stem.lower().replace(" ", "-")


def file_fingerprint(audio_path: Path) -> str:
    with audio_path.open("rb") as handle:
        return hashlib.sha256(handle.read(1024 * 1024)).hexdigest()[:16]


def transcribe(audio_path: Path, model_size: str, language: str | None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print(
            "ERROR: faster-whisper is not installed for python3. Run: python3 -m pip install faster-whisper",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading Whisper model '{model_size}'...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing '{audio_path}'...", file=sys.stderr)
    raw_segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        word_timestamps=False,
    )

    segments = []
    for segment in raw_segments:
        segments.append(
            {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
        )

    return {
        "source": str(audio_path),
        "source_hash": file_fingerprint(audio_path),
        "whisper_model": model_size,
        "language": info.language,
        "language_probability": round(info.language_probability, 2),
        "duration_seconds": round(info.duration, 2),
        "segment_count": len(segments),
        "transcribed_at": datetime.now(timezone.utc).isoformat(),
        "segments": segments,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio_file", help="Path to a local audio or video file")
    parser.add_argument(
        "--model",
        default="small",
        help="Whisper model size: tiny, base, small, medium, large-v3",
    )
    parser.add_argument("--language", help="Optional language hint such as en or es")
    parser.add_argument("--name", help="Transcript name override")
    parser.add_argument(
        "--data-dir",
        help="Override transcript storage directory "
        "(default: ${AUDIO_RLM_HOME:-${CODEX_HOME:-~/.codex}/audio-rlm})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    audio_path = Path(args.audio_file).expanduser().resolve()
    if not audio_path.is_file():
        print(f"ERROR: File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    transcripts_dir = data_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    name = args.name or derive_name(audio_path)
    result = transcribe(audio_path, args.model, args.language)

    out_path = transcripts_dir / f"{name}.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    duration = result["duration_seconds"]
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    print(f"Transcription saved: {out_path}")
    print(f"  Name:     {name}")
    print(f"  Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
    print(f"  Language: {result['language']} ({result['language_probability']})")
    print(f"  Segments: {result['segment_count']}")


if __name__ == "__main__":
    main()
