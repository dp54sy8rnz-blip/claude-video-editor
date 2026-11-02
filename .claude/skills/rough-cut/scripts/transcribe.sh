#!/usr/bin/env bash
# Transcribe raw/ and broll/ once with WhisperX large-v3 + wav2vec2 alignment.
# Re-running skips straight to the saved transcripts.
# The WhisperX env lives in ~/.cache/video-editor/whisperx (3-5 GB, built once by uv).
set -euo pipefail

JOB="${1:?usage: transcribe.sh projects/<job>}"
ENV_DIR="${WHISPERX_ENV:-$HOME/.cache/video-editor/whisperx}"
LANG_CODE="${WHISPERX_LANG:-en}"
mkdir -p "$JOB/transcript"

if [ ! -x "$ENV_DIR/bin/whisperx" ]; then
  echo "Building WhisperX environment in $ENV_DIR (one time, several minutes)..."
  uv venv --python 3.11 "$ENV_DIR"
  uv pip install --python "$ENV_DIR/bin/python" whisperx
fi

DEVICE=cpu; COMPUTE=int8
if command -v nvidia-smi >/dev/null 2>&1; then DEVICE=cuda; COMPUTE=float16; fi

transcribe_dir() {
  local src="$1" out_json="$2"
  if [ -f "$out_json" ]; then
    echo "Already transcribed: $out_json (skipping)"; return
  fi
  shopt -s nullglob
  # Declare, then assign: macOS bash 3.2 under `set -u` loses a `local arr=(...)` array.
  local -a files
  files=("$src"/*.{mp4,mov,mkv,m4v,wav,m4a,mp3,MP4,MOV})
  if [ ${#files[@]} -eq 0 ]; then echo "No media in $src"; return; fi
  local tmp; tmp="$(mktemp -d)"
  for f in "${files[@]}"; do
    "$ENV_DIR/bin/whisperx" "$f" --model large-v3 --language "$LANG_CODE" \
      --device "$DEVICE" --compute_type "$COMPUTE" \
      --output_format json --output_dir "$tmp"
  done
  # Merge into {"clips": {"raw/A001.mp4": <whisperx json>, ...}}
  python3 - "$src" "$tmp" "$out_json" "${files[@]}" <<'PY'
import json, os, sys
src, tmp, out, *files = sys.argv[1:]
job_rel = os.path.basename(os.path.normpath(src))
clips = {}
for f in files:
    stem = os.path.splitext(os.path.basename(f))[0]
    with open(os.path.join(tmp, stem + ".json")) as fh:
        clips[f"{job_rel}/{os.path.basename(f)}"] = json.load(fh)
with open(out, "w") as fh:
    json.dump({"clips": clips}, fh, indent=1)
print(f"Wrote {out} ({len(clips)} clips)")
PY
  rm -rf "$tmp"
}

transcribe_dir "$JOB/raw" "$JOB/transcript/transcript.json"
[ -d "$JOB/broll" ] && transcribe_dir "$JOB/broll" "$JOB/transcript/broll.json"
