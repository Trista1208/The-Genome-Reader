#!/bin/bash
# Genome Firewall — live status dashboard. Run: ./status.sh  (or: watch -n 30 ./status.sh)
ROOT="$(cd "$(dirname "$0")" && pwd)"
TSV_DIR="$ROOT/features/amrfinder"
FAIL="$ROOT/features/batch_failures.txt"
DONE=$(ls "$TSV_DIR" 2>/dev/null | wc -l | tr -d ' ')
FAILED=$([ -f "$FAIL" ] && wc -l < "$FAIL" | tr -d ' ' || echo 0)
PCT=$((DONE * 100 / 3000))
BAR=$(printf '%*s' "$((PCT / 5))" '' | tr ' ' '#')
echo "=== Genome Firewall status — $(date '+%H:%M:%S') ==="
echo "Feature extraction (AMRFinderPlus): [$BAR$(printf '%*s' "$((20 - PCT / 5))" '')] $DONE/3000 ($PCT%)  failures: $FAILED"
if [ "$DONE" -gt 0 ]; then
  FIRST=$(stat -f %B "$TSV_DIR"/*.tsv 2>/dev/null | sort -n | head -1)
  NOW=$(date +%s)
  [ -n "$FIRST" ] && echo "rate: $((DONE * 60 / (NOW - FIRST + 1)))/min  ETA full batch: $(( (3000 - DONE) * (NOW - FIRST) / (DONE * 60) )) min"
fi
echo ""
echo "Clean labels: $(wc -l < "$ROOT/data/clean/labels_clean_ecoli.csv" 2>/dev/null | tr -d ' ') rows (ecoli)"
echo ""
echo "Latest batch log:"
tail -2 "$ROOT/features/batch.log" 2>/dev/null || echo "(batch log written to task output)"
echo ""
echo "Git: $(git -C "$ROOT" branch --show-current) | $(git -C "$ROOT" log --oneline -1)"
