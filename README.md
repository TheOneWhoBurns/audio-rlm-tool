# Audio RLM tool

Local audio/video transcription with faster-whisper and a persistent transcript explorer. Search, inspect timestamps, and split long transcripts into chunks for analysis by your coding agent.

## Requirements

- Python 3.10+
- ffmpeg on your PATH
- Install Python dependencies: `python3 -m pip install -r requirements.txt`

Transcription runs locally. Whisper model weights may download on first use. Any transcript excerpts you give your coding agent are handled by that agent and its provider.

## Codex and standalone Python

The current Codex skill and scripts are in `skills/audio-rlm/`.

```sh
git clone https://github.com/TheOneWhoBurns/audio-rlm-tool.git
cd audio-rlm-tool
python3 -m pip install -r requirements.txt
python3 skills/audio-rlm/scripts/transcribe.py /path/to/recording.mp3 --model small
python3 skills/audio-rlm/scripts/repl.py list
python3 skills/audio-rlm/scripts/repl.py load recording
python3 skills/audio-rlm/scripts/repl.py info
python3 skills/audio-rlm/scripts/repl.py grep "budget"
python3 skills/audio-rlm/scripts/repl.py time 600 900
python3 skills/audio-rlm/scripts/repl.py chunk --size 50
```

For Codex, copy `skills/audio-rlm/` into your skills directory (normally `~/.codex/skills/audio-rlm/`). Use real files, not symlinks. Start a new session after installation.

Data is stored in `${AUDIO_RLM_HOME:-${CODEX_HOME:-~/.codex}/audio-rlm}`. Both scripts accept `--data-dir /path/to/data` to override it. Recordings, transcripts, model weights, and session data are not included in this repository.

## Claude Code

The original Claude Code integration remains in `.claude/skills/audio-rlm/` with its optional `.claude/agents/audio-subcall.md` agent. See [CLAUDE.md](CLAUDE.md) for its workflow and separate data location.

## Skill collection

The Codex skill is also included in the private [agent-skills repository](https://github.com/TheOneWhoBurns/agent-skills).
