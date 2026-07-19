// The five drugs the trained E. coli models actually cover
// (Darkroom4364/genome-firewall-ecoli). Drugs without a model are not offered.
export const ANTIBIOTICS = [
  "Ciprofloxacin",
  "Gentamicin",
  "Ampicillin",
  "Cefotaxime",
  "Trimethoprim / Sulfamethoxazole",
] as const;

export type Antibiotic = (typeof ANTIBIOTICS)[number];

export type DetectedGene = {
  symbol: string;
  name: string;
  tier: string;
  confidence: string;
};

export type AnalysisResult = {
  analysisId?: string;
  score: number;
  confidence: number;
  classification: "likely_effective" | "uncertain" | "likely_ineffective";
  evidence: "known_marker" | "statistical_association" | "no_known_signal";
  modelVersion: string;
  noCall?: boolean;
  detectedGenes?: DetectedGene[];
  sequenceLength?: number;
  contigCount?: number;
};

export type RunInference = (
  file: File,
  antibiotic: Antibiotic,
  onUploaded: () => void,
) => Promise<AnalysisResult>;
