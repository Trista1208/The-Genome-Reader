from __future__ import annotations

import json
from pathlib import Path

import joblib
from scipy import sparse

from genome_firewall.config import DEFAULT_PATHS, Paths
from genome_firewall.layer2_features.matrix import load_feature_store, parse_amrfinder_tsv, vectorize_hits
from genome_firewall.layer3_model.random_forest import CalibratedRandomForest, top_supporting_features
from genome_firewall.layer3_model.target_gate import passes_target_gate
from genome_firewall.layer1_ingestion.cohort import load_labels
from genome_firewall.layer4_scoring.explanations import training_skip_reason
from genome_firewall.layer4_scoring.predictor import score_drug, unscored_drug
from genome_firewall.schemas.prediction import GenomeReport


class InferenceService:
    def __init__(self, paths: Paths = DEFAULT_PATHS) -> None:
        self.paths = paths
        self._models: dict[str, CalibratedRandomForest] | None = None
        self._catalog = None

    def _load_models(self) -> dict[str, CalibratedRandomForest]:
        if self._models is not None:
            return self._models
        models: dict[str, CalibratedRandomForest] = {}
        for path in sorted(self.paths.models_dir.glob("*_model.joblib")):
            bundle = joblib.load(path)
            models[bundle["drug"]] = CalibratedRandomForest.from_bundle(bundle)
        if not models:
            raise FileNotFoundError(f"No models in {self.paths.models_dir}. Run training first.")
        self._models = models
        return models

    def _catalog_df(self):
        if self._catalog is None:
            _, _, self._catalog = load_feature_store(self.paths.features_dir)
        return self._catalog

    def score_from_amrfinder_tsv(
        self,
        genome_id: str,
        amrfinder_tsv: Path,
        *,
        fasta: Path | None = None,
        species: str = "Escherichia coli",
    ) -> GenomeReport:
        hits = parse_amrfinder_tsv(amrfinder_tsv)
        catalog = self._catalog_df()
        x = vectorize_hits(hits, catalog)
        return self._score_vector(genome_id, x, hits, fasta=fasta, species=species)

    def score_from_feature_row(
        self,
        genome_id: str,
        *,
        species: str = "Escherichia coli",
    ) -> GenomeReport:
        genome_ids, matrix, catalog = load_feature_store(self.paths.features_dir)
        if genome_id not in genome_ids:
            raise KeyError(f"{genome_id} not in feature store")
        row_index = genome_ids.index(genome_id)
        x = matrix[row_index : row_index + 1]
        amr_tsv = self.paths.amrfinder_dir / f"{genome_id}.tsv"
        hits = parse_amrfinder_tsv(amr_tsv) if amr_tsv.exists() else []
        fasta = self.paths.fasta_dir / f"{genome_id}.fna"
        return self._score_vector(genome_id, x, hits, fasta=fasta if fasta.exists() else None, species=species)

    def _score_vector(
        self,
        genome_id: str,
        x: sparse.csr_matrix,
        hits: list[dict[str, str]],
        *,
        fasta: Path | None,
        species: str,
    ) -> GenomeReport:
        models = self._load_models()
        labels = load_labels(self.paths.labels)
        all_drugs = sorted(labels["antibiotic"].unique())
        genome_ids, _, _ = load_feature_store(self.paths.features_dir)
        featured_ids = set(genome_ids)

        if fasta is not None:
            target_ok, target_reason = passes_target_gate(fasta)
        else:
            target_ok, target_reason = True, "fasta_not_provided"

        drug_scores = []
        for drug in all_drugs:
            if drug not in models:
                sub = labels[(labels["antibiotic"] == drug) & (labels["genome_id"].isin(featured_ids))]
                n_r = int((sub["label"] == "likely_to_fail").sum())
                n_s = int((sub["label"] == "likely_to_work").sum())
                skip = training_skip_reason(
                    drug,
                    n_labeled=len(sub),
                    n_resistant=n_r,
                    n_susceptible=n_s,
                    n_with_features=len(sub),
                )
                code, detail = skip or ("model_not_trained", f"No trained model for {drug}.")
                drug_scores.append(unscored_drug(drug, skip_code=code, skip_detail=detail))
                continue

            model = models[drug]
            support = top_supporting_features(model, x)
            drug_scores.append(
                score_drug(
                    drug,
                    model,
                    x,
                    target_ok=target_ok,
                    target_reason=target_reason,
                    amr_hits=hits,
                    supporting_features=support,
                )
            )
        return GenomeReport(genome_id=genome_id, species=species, drugs=drug_scores)

    def write_report_json(self, report: GenomeReport, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
