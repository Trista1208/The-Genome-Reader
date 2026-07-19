#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:?output directory required}"
fasta="${2:?FASTA path required}"
genome_id="$(basename "${fasta}" .fna)"
output="${output_dir}/${genome_id}.tsv"

if [[ -s "${output}" ]]; then
  echo "SKIP ${genome_id}"
  exit 0
fi

temporary="${output}.tmp"
rm -f "${temporary}"
amrfinder \
  -n "${fasta}" \
  -o "${temporary}" \
  --plus \
  --organism Escherichia \
  --threads 1
test -s "${temporary}"
mv "${temporary}" "${output}"
echo "DONE ${genome_id}"
