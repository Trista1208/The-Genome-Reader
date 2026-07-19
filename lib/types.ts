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

// The client/patient a genome is run for. `patientId` is the unique key that
// groups a patient's results in the knowledge tree; the rest is display detail.
export type PatientInput = {
  patientId: string;
  name: string;
  dob?: string;
  notes?: string;
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
  patient: PatientInput,
  onUploaded: () => void,
) => Promise<AnalysisResult>;

// The concurrent "second opinion" report produced by the AI reviewer subagent.
// It reads the same FASTA-derived stats plus the classifier's own output, then
// forms an independent verdict and cross-checks whether the classifier agrees.
export type AnalysisReport = {
  summary: string;
  keyFindings: string[];
  independentVerdict: "likely_effective" | "uncertain" | "likely_ineffective";
  agreement: "agree" | "partial" | "disagree";
  reasoning: string;
};

export type GenerateReport = (
  result: AnalysisResult,
  antibiotic: Antibiotic,
  fileName: string,
) => Promise<AnalysisReport>;

// Shapes shared by the Convex knowledge-tree queries and the localStorage demo
// fallback, so components/knowledge-tree.tsx can render either source.
export type AnalysisNode = {
  _id: string;
  antibiotic: string;
  fileName: string;
  status: "processing" | "complete" | "failed";
  classification?: AnalysisResult["classification"];
  score?: number;
  createdAt: number;
};

export type PatientNode = {
  _id: string;
  patientId: string;
  name: string;
  dob?: string;
  notes?: string;
  updatedAt: number;
  analyses: AnalysisNode[];
};

// Full detail returned for a single analysis node (report panel).
export type AnalysisDetail = {
  analysis: AnalysisResult & {
    _id: string;
    fileName: string;
    antibiotic: string;
    status: "processing" | "complete" | "failed";
    createdAt: number;
    report?: AnalysisReport;
  };
  patient: PatientInput | null;
};
