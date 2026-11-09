#!/usr/bin/env bash
# Download one Nasdaq TotalView-ITCH 5.0 sample day into data/ and decompress it.
#
#   scripts/fetch_itch_sample.sh [FILE]
#   HEAD_MB=512 scripts/fetch_itch_sample.sh [FILE]   # keep only the first 512 MB
#
# FILE defaults to 01302019.NASDAQ_ITCH50.gz. The available days are listed at
#   https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/
# Each file is a full trading day: several GB compressed, much larger
# decompressed. Check the size in that listing and your free disk space first.
#
# ITCH_BASE_URL overrides the server, e.g. for a local mirror.

set -euo pipefail

BASE_URL="${ITCH_BASE_URL:-https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH}"
FILE="${1:-01302019.NASDAQ_ITCH50.gz}"
HEAD_MB="${HEAD_MB:-0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT}/data"
GZ="${DATA_DIR}/${FILE}"
RAW="${GZ%.gz}"

mkdir -p "${DATA_DIR}"

# A complete, valid file is kept. A missing or truncated one is (re)downloaded;
# --continue-at - resumes from where a previous attempt stopped.
if [[ -f "${GZ}" ]] && gzip --test "${GZ}" 2>/dev/null; then
  echo "Already downloaded: ${GZ}"
else
  echo "Downloading ${BASE_URL}/${FILE}"
  curl --fail --location --continue-at - --output "${GZ}" "${BASE_URL}/${FILE}"
  echo "Checking gzip integrity"
  gzip --test "${GZ}"
fi

if [[ "${HEAD_MB}" -gt 0 ]]; then
  OUT="${RAW}.head${HEAD_MB}M"
  echo "Extracting the first ${HEAD_MB} MB to ${OUT}"
  # head exits once it has enough bytes, and gzip then dies of SIGPIPE
  # (exit status 141). That is expected; any other failure is not.
  gzip -dc "${GZ}" | head -c "$((HEAD_MB * 1024 * 1024))" > "${OUT}" || [[ $? -eq 141 ]]
  echo "Note: the cut can land mid-message; the parser must handle a truncated last message."
else
  OUT="${RAW}"
  echo "Decompressing to ${OUT}"
  gzip -dc "${GZ}" > "${OUT}"
fi

ls -lh "${OUT}"
