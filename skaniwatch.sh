#!/bin/bash
# skani progress watcher
LOG=/Users/darkroom/Projects/genome-firewall/splits/splits_run.log
while true; do
  clear
  echo "SKANI PROGRESS — $(date +%H:%M:%S)"
  echo "----------------------------------------"
  tail -1 "$LOG"
  n=$(grep -c processed "$LOG")
  echo "done: $((n * 100)) / 3000 genomes"
  sleep 30
done
