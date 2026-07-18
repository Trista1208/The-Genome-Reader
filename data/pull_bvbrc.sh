#!/bin/bash
# BV-BRC rehearsal data pull for Genome Firewall (per CONTRACT.md data/ layout)
# Usage: ./pull_bvbrc.sh [max_genomes_per_species]
# Pulls: lab-only AST labels (API, CSV) for the 3 likeliest species,
#        then up to N .fna genomes (FTPS, parallel) for E. coli.
set -euo pipefail

DATA_DIR="$(cd "$(dirname "$0")" && pwd)"
GENOME_DIR="$DATA_DIR/genomes"
mkdir -p "$GENOME_DIR"
MAX_GENOMES="${1:-3000}"
API="https://www.bv-brc.org/api"
FTP="ftp://ftp.bv-brc.org/genomes"
PAGE=25000

log() { echo "[$(date +%H:%M:%S)] $*"; }

# --- labels: page the genome_amr API, lab-measured rows only ---
pull_labels() {
  local taxon=$1 name=$2
  local out="$DATA_DIR/labels_${name}.csv"
  if [ -s "$out" ] && [ "$(wc -l < "$out")" -gt 1 ]; then
    log "$name labels already present ($(($(wc -l < "$out") - 1)) rows), skipping"
    return
  fi
  : > "$out"
  local offset=0 header_done=0
  while true; do
    local tmp; tmp=$(mktemp)
    curl -sf --retry 3 --retry-delay 2 \
      "$API/genome_amr/?eq(taxon_id,${taxon})&eq(evidence,Laboratory%20Method)&limit(${PAGE},${offset})" \
      -H "Accept: text/csv" -o "$tmp"
    local rows; rows=$(($(wc -l < "$tmp") - 1))
    if [ "$header_done" -eq 0 ]; then
      cat "$tmp" >> "$out"; header_done=1
    else
      tail -n +2 "$tmp" >> "$out"
    fi
    rm -f "$tmp"
    log "$name labels: +$rows rows (offset $offset)"
    [ "$rows" -lt "$PAGE" ] && break
    offset=$((offset + PAGE))
    sleep 0.2
  done
  log "$name labels DONE: $(($(wc -l < "$out") - 1)) total rows -> $out"
}

# --- unique genome ids from a labels csv (first column = genome_id) ---
extract_ids() {
  python3 -c "
import csv
with open('$1') as f:
    r = csv.reader(f)
    hdr = [h.strip().lower().replace(' ', '_') for r0 in [next(r)] for h in r0]
    idx = hdr.index('genome_id')
    ids = sorted({row[idx] for row in r if len(row) > idx})
print('\n'.join(ids))
"
}

# --- genomes: FTPS, 8 parallel ---
pull_genomes() {
  local idfile=$1
  local total; total=$(wc -l < "$idfile" | tr -d ' ')
  log "downloading $total genomes (8 parallel)..."
  : > "$DATA_DIR/failed.txt"
  xargs -P 8 -n 1 "$DATA_DIR/dl_one.sh" < "$idfile"
  local ok; ok=$(ls "$GENOME_DIR" | wc -l | tr -d ' ')
  local fail; fail=$(wc -l < "$DATA_DIR/failed.txt" | tr -d ' ')
  log "genomes DONE: $ok present, $fail failed (see failed.txt)"
}

log "=== BV-BRC pull started (max $MAX_GENOMES genomes) ==="

# labels for the 3 likeliest species (cheap, always useful)
pull_labels 562   ecoli
pull_labels 573   kpneumoniae
pull_labels 485   ngonorrhoeae

# E. coli genomes (the primary rehearsal species)
extract_ids "$DATA_DIR/labels_ecoli.csv" > "$DATA_DIR/genome_ids_ecoli_all.txt"
head -n "$MAX_GENOMES" "$DATA_DIR/genome_ids_ecoli_all.txt" > "$DATA_DIR/genome_ids_ecoli.txt"
log "$(wc -l < "$DATA_DIR/genome_ids_ecoli.txt" | tr -d ' ') E. coli genomes queued"
pull_genomes "$DATA_DIR/genome_ids_ecoli.txt"

# manifest
python3 -c "
import json, os, time
m = {
  'pulled_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
  'source': 'BV-BRC (bv-brc.org), evidence==Laboratory Method only',
  'labels': {n: os.path.getsize(f'$DATA_DIR/labels_{n}.csv') for n in ['ecoli','kpneumoniae','ngonorrhoeae']},
  'genomes_fna': len(os.listdir('$GENOME_DIR')),
  'max_genomes_requested': $MAX_GENOMES,
}
json.dump(m, open('$DATA_DIR/manifest.json','w'), indent=2)
print(m)
"
log "=== ALL DONE ==="
