#!/usr/bin/env bash
# Download BV-BRC assembled FASTA (.fna) for genome IDs via lftp.
set -euo pipefail

GENOME_LIST="${1:-data/processed/cohort/genome_list.txt}"
OUT_DIR="${2:-data/raw/bvbrc/genomes}"
WORKERS="${3:-6}"

mkdir -p "$OUT_DIR"

download_one() {
  local genome_id="$1"
  local out_dir="$2"
  local dest="${out_dir}/${genome_id}.fna"
  if [[ -s "$dest" ]]; then
    echo "skip ${genome_id}"
    return 0
  fi
  lftp -u anonymous,guest ftp.bv-brc.org -e "
set ftp:ssl-force true
set ftp:ssl-protect-data true
set ssl:verify-certificate no
set net:max-retries 4
set net:reconnect-interval-base 3
set xfer:clobber on
get -c /genomes/${genome_id}/${genome_id}.fna -o ${dest}.partial
bye
" && mv -f "${dest}.partial" "$dest" && echo "ok ${genome_id}" || {
    rm -f "${dest}.partial"
    echo "fail ${genome_id}" >&2
    return 1
  }
}

export -f download_one
export OUT_DIR

echo "Downloading genomes from ${GENOME_LIST} -> ${OUT_DIR} (workers=${WORKERS})"
pids=()
while IFS= read -r genome_id; do
  [[ -z "$genome_id" ]] && continue
  download_one "$genome_id" "$OUT_DIR" &
  pids+=("$!")
  if ((${#pids[@]} >= WORKERS)); then
    wait "${pids[0]}"
    pids=("${pids[@]:1}")
  fi
done < <(grep -v '^#' "$GENOME_LIST" | grep -v '^[[:space:]]*$')
for pid in "${pids[@]}"; do
  wait "$pid"
done

echo "Done. Count: $(ls -1 "$OUT_DIR"/*.fna 2>/dev/null | wc -l | tr -d ' ')"
du -sh "$OUT_DIR"
