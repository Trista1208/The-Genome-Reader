#!/bin/bash
# AMRFinderPlus batch over downloaded genomes (Genome Firewall, features/ area)
# Docker image pins tool 4.2.7 + DB 2026-03-24.1. Resumable: skips existing TSVs.
# Usage: ./run_amrfinder_batch.sh [parallel_jobs] [threads_per_job]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GENOMES="$ROOT/data/genomes"
OUT="$ROOT/features/amrfinder"
LOG="$ROOT/features/batch_failures.txt"
IMG="staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1"
JOBS="${1:-6}"
THREADS="${2:-2}"
ORGANISM="${ORGANISM:-Escherichia}"
mkdir -p "$OUT"
: > "$LOG"

total=$(ls "$GENOMES"/*.fna | wc -l | tr -d ' ')
echo "[$(date +%H:%M:%S)] AMRFinderPlus batch: $total genomes, $JOBS parallel x $THREADS threads, organism=$ORGANISM"

ls "$GENOMES"/*.fna | xargs -P "$JOBS" -n 1 sh -c '
  fna="$0"
  id=$(basename "$fna" .fna)
  out="'"$OUT"'/${id}.tsv"
  [ -s "$out" ] && exit 0
  docker run --rm --platform linux/amd64 \
    -v "'"$ROOT"'/data:/data:ro" -v "'"$OUT"':/out" \
    '"$IMG"' amrfinder -n "/data/genomes/${id}.fna" -O "'"$ORGANISM"'" \
    --plus --threads '"$THREADS"' -o "/out/${id}.tsv" >/dev/null 2>&1 \
    || echo "$id" >> "'"$LOG"'"
'

done_n=$(ls "$OUT" | wc -l | tr -d ' ')
fail_n=$(wc -l < "$LOG" | tr -d ' ')
echo "[$(date +%H:%M:%S)] BATCH DONE: $done_n TSVs present, $fail_n failures"
