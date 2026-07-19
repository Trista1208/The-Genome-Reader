#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:?input directory required}"
output_dir="${2:?output directory required}"
workers="${3:-4}"

mkdir -p "${output_dir}"

find "${input_dir}" -maxdepth 1 -type f -name '*.fna' -print0 |
  xargs -0 -r -n 1 -P "${workers}" \
    /project/scripts/run_amrfinder_one.sh "${output_dir}"
