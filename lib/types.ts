export const ANTIBIOTICS = [
  "Ciprofloxacin",
  "Ceftriaxone",
  "Gentamicin",
  "Meropenem",
  "Trimethoprim / Sulfamethoxazole",
] as const;

export type Antibiotic = (typeof ANTIBIOTICS)[number];

export type AnalysisResult = {
  analysisId?: string;
  score: number;
  confidence: number;
  classification: "likely_effective" | "uncertain" | "likely_ineffective";
  evidence: "known_marker" | "statistical_association" | "no_known_signal";
  modelVersion: string;
  sequenceLength?: number;
  contigCount?: number;
};

export type RunInference = (
  file: File,
  antibiotic: Antibiotic,
  onUploaded: () => void,
) => Promise<AnalysisResult>;
