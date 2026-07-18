# Module 03 — Frontend (separate layer)

This repository is **backend only** (Modules 01 + 02).

The frontend team should consume JSON from:

```bash
python3 scripts/score_genome.py {genome_id} --out report.json
```

See [`specs/prediction_api.schema.json`](../specs/prediction_api.schema.json) for the response contract.

Do **not** implement UI logic in `backend/` — keep presentation in this folder or a separate repo.
