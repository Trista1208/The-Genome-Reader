#!/bin/bash
# Download one genome .fna from BV-BRC FTPS. Usage: dl_one.sh <genome_id>
set -u
id="$1"
DATA_DIR="$(cd "$(dirname "$0")" && pwd)"
out="$DATA_DIR/genomes/${id}.fna"
[ -s "$out" ] && exit 0
curl -sf --ssl-reqd --retry 2 --user anonymous:guest \
  "ftp://ftp.bv-brc.org/genomes/${id}/${id}.fna" -o "$out" \
  || echo "$id" >> "$DATA_DIR/failed.txt"
