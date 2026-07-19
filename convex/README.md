# Convex backend

The browser uploads FASTA files directly to Convex storage. `analysis.runInference` reads the stored file, calls the configured Hugging Face endpoint, normalizes its probability, and stores the audit record in `analyses`.

Expected Hugging Face request:

```json
{
  "inputs": {
    "fasta": ">record\nATGC...",
    "antibiotic": "Ciprofloxacin"
  },
  "options": { "wait_for_model": true }
}
```

Expected response (the aliases `probability` and `effectiveness_score` are also accepted for `score`):

```json
{
  "score": 0.82,
  "confidence": 0.91,
  "evidence": "statistical_association",
  "model_version": "GFR-ECOLI-0.8.2"
}
```

`score` and `confidence` must be finite numbers from 0 to 1.
