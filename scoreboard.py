#!/usr/bin/env python3
"""Scoreboard watcher: prints per-drug heldout metrics, refreshes every 20s."""
import json, os, time
P = '/Users/darkroom/Projects/genome-firewall/reports/metrics.json'
last = None
while True:
    os.system('clear')
    print(f"SCOREBOARD — {time.strftime('%H:%M:%S')}")
    print("=" * 84)
    try:
        mt = os.path.getmtime(P)
        print(f"metrics.json last written: {time.strftime('%H:%M:%S', time.localtime(mt))}", end="")
        print("   <-- NEW RUN" if last is not None and mt > last else "")
        last = mt if last is None else last
        m = json.load(open(P))
        print(f"{'drug':32s} {'bal_acc':>7s} {'R-rec':>6s} {'S-rec':>6s} {'nocall':>6s} {'acc_called':>10s}")
        for drug, d in m.items():
            h = d['groups']['heldout_group']
            print(f"{drug:32s} {h['balanced_accuracy']:7.3f} {h['recall_resistant']:6.2f} "
                  f"{h['recall_susceptible']:6.2f} {h['no_call_rate']:6.2f} {h['accuracy_after_no_call']:10.3f}")
    except FileNotFoundError:
        print("no metrics.json yet — training still running")
    except json.JSONDecodeError:
        print("metrics.json is being written right now...")
    time.sleep(20)
