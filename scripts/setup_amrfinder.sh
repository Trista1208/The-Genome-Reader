#!/usr/bin/env bash
# Build AMRFinderPlus from source (macOS/Linux) and index the local NCBI database.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/tools/bin"
DB="$ROOT/data/raw/amrfinderplus/latest"
SRC="${AMRFINDER_SRC:-/tmp/amr}"
TAG="${AMRFINDER_TAG:-amrfinder_v4.2.7}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing dependency: $1" >&2
    echo "Install BLAST+ and HMMER: brew install blast hmmer" >&2
    exit 1
  }
}

need_cmd makeblastdb
need_cmd hmmpress
need_cmd git
need_cmd g++

mkdir -p "$BIN"

if [[ ! -x "$BIN/amrfinder" ]]; then
  echo "Building AMRFinderPlus $TAG ..."
  rm -rf "$SRC"
  git clone --depth 1 --branch "$TAG" https://github.com/ncbi/amr.git "$SRC"
  make -C "$SRC" amr_report amrfinder amrfinder_index fasta_check fasta_extract \
    fasta2parts gff_check dna_mutation amr_report mutate disruption2genesymbol
  cp "$SRC"/{amrfinder,amr_report,amrfinder_index,fasta_check,fasta_extract,fasta2parts,gff_check,dna_mutation,mutate,disruption2genesymbol} "$BIN/"
fi

if [[ ! -f "$DB/AMRProt.fa.phr" ]]; then
  echo "Indexing AMRFinderPlus database at $DB ..."
  python3 "$ROOT/scripts/download_amrfinder_db.py"
  "$BIN/amrfinder_index" "$DB"
fi

echo "AMRFinderPlus ready:"
"$BIN/amrfinder" --version
echo "Database: $DB"
