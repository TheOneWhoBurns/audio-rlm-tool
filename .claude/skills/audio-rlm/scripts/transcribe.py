#!/usr/bin/env python3
"""Transcribe an audio file with faster-whisper and save as JSON.

Usage:
    python transcribe.py <audio_file> [--model small] [--language en] [--name custom_name]

Output: .claude/audio-rlm/transcripts/<name>.json
"""

import sys
import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

TRANSCRIPTS_DIR = Path(".claude/audio-rlm/transcripts")


def transcribe(audio_path: str, model_size: str = "small", language: str | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper", file=sys.stderr)
        sys.exit(1)

    print(f"Loading whisper model '{model_size}'...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing '{audio_path}'...", file=sys.stderr)
    raw_segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=False,
    )

    segments = []
    for seg in raw_segments:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    # file fingerprint so we can detect re-transcription of same file
    with open(audio_path, "rb") as f:
        file_hash = hashlib.sha256(f.read(1024 * 1024)).hexdigest()[:16]  # first 1MB

    return {
        "source": os.path.abspath(audio_path),
        "source_hash": file_hash,
        "whisper_model": model_size,
        "language": info.language,
        "language_probability": round(info.language_probability, 2),
        "duration_seconds": round(info.duration, 2),
        "segment_count": len(segments),
        "transcribed_at": datetime.now(timezone.utc).isoformat(),
        "segments": segments,
    }


def derive_name(audio_path: str) -> str:
    """Derive a transcript name from the audio filename."""
    return Path(audio_path).stem.lower().replace(" ", "-")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    audio_path = sys.argv[1]
    if not os.path.isfile(audio_path):
        print(f"ERROR: File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    model_size = "small"
    language = None
    name = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            model_size = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--language" and i + 1 < len(sys.argv):
            language = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
            name = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if name is None:
        name = derive_name(audio_path)

    result = transcribe(audio_path, model_size, language)

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPTS_DIR / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    # summary to stdout (this is what the agent sees)
    duration = result["duration_seconds"]
    h, m, s = int(duration // 3600), int((duration % 3600) // 60), int(duration % 60)
    print(f"Transcription saved: {out_path}")
    print(f"  Name:     {name}")
    print(f"  Duration: {h:02d}:{m:02d}:{s:02d}")
    print(f"  Language: {result['language']} ({result['language_probability']})")
    print(f"  Segments: {result['segment_count']}")


if __name__ == "__main__":
    main()
