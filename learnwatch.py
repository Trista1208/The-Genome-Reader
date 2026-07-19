#!/Users/darkroom/Projects/genome-firewall/pipeline/.venv/bin/python
"""Learn-watch: live view of the training process.
Shows: batch progress, latest training log, and current top learned weights.
Refresh: 20s. Run: ./learnwatch.py"""
import json, os, pickle, time
import pandas as pd

ROOT = '/Users/darkroom/Projects/genome-firewall'
DRUGS = ["ciprofloxacin", "gentamicin", "ampicillin",
         "trimethoprim_sulfamethoxazole", "cefotaxime"]

def top_weights(drug, n=6):
    p = f'{ROOT}/models/{drug}/baseline.pkl'
    if not os.path.exists(p):
        return None, 0
    mt = os.path.getmtime(p)
    b = pickle.load(open(p, 'rb'))
    lr = b['model'].named_steps['lr']
    cols = [c for c in pd.read_csv(f'{ROOT}/features/feature_matrix.csv', nrows=0).columns if c != 'genome_id']
    w = pd.Series(lr.coef_[0], index=cols)
    nz = w[w != 0].sort_values(ascending=False)
    return nz.head(n), mt

while True:
    os.system('clear')
    print(f"LEARN-WATCH — {time.strftime('%H:%M:%S')}")
    print("=" * 64)
    tsv_dir = f'{ROOT}/features/amrfinder'
    n = len(os.listdir(tsv_dir)) if os.path.isdir(tsv_dir) else 0
    print(f"genomes scanned: {n}/3000   (feature extraction = model's raw material)")
    log = f'{ROOT}/reports/train_run.log'
    if os.path.exists(log):
        print("\n--- latest training log ---")
        lines = open(log).read().strip().splitlines()
        for l in lines[-4:]:
            print(" ", l[:80])
    print("\n--- what the model has learned so far (top weights) ---")
    for drug in DRUGS:
        nz, mt = top_weights(drug)
        if nz is None:
            continue
        when = time.strftime('%H:%M', time.localtime(mt))
        top = ", ".join(f"{g} {v:+.2f}" for g, v in list(nz.items())[:3])
        print(f"  {drug:32s} [{when}] {top[:76]}")
    print("\n(refresh 20s — Ctrl-C to quit)")
    time.sleep(20)
