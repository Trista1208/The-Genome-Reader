# Convex backend

The browser uploads FASTA files directly to Convex storage. `analysis.runInference`
reads the stored file, POSTs it to the **Genome Firewall inference service**
(`inference/serve.py` — FASTA → AMRFinderPlus → 600-feature vector → calibrated
model), validates the response, and stores the audit record in `analyses`.

## Configuration (set in the Convex dashboard)

```bash
npx convex env set INFERENCE_API_URL https://your-inference-host
npx convex env set INFERENCE_API_TOKEN <optional-shared-secret>   # optional
```

If `INFERENCE_API_URL` is unset the action throws
"The inference service is not configured".

## Request

`POST ${INFERENCE_API_URL}/predict` with an optional `Authorization: Bearer <token>`:

```json
{
  "fasta": ">record\nATGC...",
  "antibiotic": "Ciprofloxacin"
}
```

## Response

The service already speaks the app's contract. `score` is the probability the
antibiotic is **effective** (`= 1 − p_fail`); `classification` is decided by the
model's no-call bands (not by a score threshold):

```json
{
  "score": 0.992,
  "confidence": 0.88,
  "classification": "likely_effective",
  "evidence": "no_known_signal",
  "noCall": false,
  "modelVersion": "GFR-ECOLI / AMRFinderPlus 4.2.7 / DB 2026-03-24.1",
  "detectedGenes": [
    { "symbol": "blaTEM-1", "name": "...", "tier": "full_gene", "confidence": "confirmed" }
  ]
}
```

- `score`, `confidence` — finite numbers in `[0, 1]`.
- `classification` — `likely_effective` | `uncertain` (no-call) | `likely_ineffective`.
- `evidence` — `known_marker` | `statistical_association` | `no_known_signal`.
- `modelVersion`, `noCall`, `detectedGenes` — trusted through to the audit record.

Supported antibiotics: `Ciprofloxacin`, `Gentamicin`, `Ampicillin`, `Cefotaxime`,
`Trimethoprim / Sulfamethoxazole`. An unsupported drug returns a 400 from the service.
