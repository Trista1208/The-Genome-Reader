#!/usr/bin/env python3
"""Live bio-stats dashboard for Genome Firewall. Run: ./biostat.py"""
import os, csv, collections, time, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TSV = os.path.join(ROOT, 'features', 'amrfinder')
FAIL = os.path.join(ROOT, 'features', 'batch_failures.txt')
START = time.time()
FIRST_N = None

while True:
    tsvs = sorted(os.listdir(TSV)) if os.path.isdir(TSV) else []
    n = len(tsvs)
    if FIRST_N is None: FIRST_N = n
    el, point, drug_hits = collections.Counter(), collections.Counter(), collections.Counter()
    gp = 0
    for fn in tsvs:
        try:
            with open(os.path.join(TSV, fn)) as f:
                for row in csv.DictReader(f, delimiter='\t'):
                    st = row.get('Subtype', '')
                    if st == 'AMR':
                        el[row['Element symbol']] += 1
                        for d in row.get('Subclass', '').split('/'):
                            if d and d not in ('NA', 'MULTI'): drug_hits[d] += 1
                    elif st.startswith('POINT'):
                        point[row['Element symbol']] += 1; gp += 1
        except Exception: pass
    fails = sum(1 for _ in open(FAIL)) if os.path.exists(FAIL) else 0
    mins = max((time.time() - START) / 60, 0.01)
    rate = (n - FIRST_N) / mins
    eta = f"{(3000 - n) / rate:.0f} min" if rate > 0.5 else "—"
    os.system('clear')
    print(f"GENOME FIREWALL — live  {time.strftime('%H:%M:%S')}")
    print(f"{'=' * 52}")
    print(f"  bacteria read: {n}/3000 ({100 * n // 3000}%)   rate: {rate:.0f}/min   ETA: {eta}   failures: {fails}")
    print(f"{'=' * 52}")
    print(f"  TOP RESISTANCE GENES (acquired)")
    for g, c in el.most_common(7):
        bar = '#' * (40 * c // max(n, 1))
        print(f"    {g:16s} {c:5d} bacteria  {bar}")
    print(f"\n  STEALTH MUTATIONS (point mutations, harder to detect)")
    for g, c in point.most_common(5):
        bar = '#' * (40 * c // max(n, 1))
        print(f"    {g:16s} {c:5d} bacteria  {bar}")
    print(f"\n  DRUG CLASSES UNDER ATTACK (hits in scanned bacteria)")
    for d, c in drug_hits.most_common(6):
        print(f"    {d:20s} {c:5d}")
    print(f"\n  (refreshing every 60s — Ctrl-C to quit)")
    time.sleep(60)
