#!/usr/bin/env bash
# Download BV-BRC RELEASE_NOTES via lftp (recommended client per BV-BRC docs).
set -euo pipefail

OUT_DIR="${1:-data/raw/bvbrc/RELEASE_NOTES}"
mkdir -p "$OUT_DIR"

lftp -u anonymous,guest ftp.bv-brc.org <<EOF
set ftp:ssl-force true
set ftp:ssl-protect-data true
set ssl:verify-certificate no
set net:max-retries 5
set net:reconnect-interval-base 5
set xfer:clobber on
cd RELEASE_NOTES
lcd $OUT_DIR
get -c PATRIC_genomes_AMR.txt
get -c genome_summary
get -c genome_metadata
get -c genome_lineage
bye
EOF

echo "Downloaded into $OUT_DIR"
ls -lh "$OUT_DIR"
