// localStorage-backed patient history for the offline demo mode (used only when
// NEXT_PUBLIC_CONVEX_URL is unset). Mirrors the Convex knowledge-tree shape so
// components/knowledge-tree.tsx can read either source interchangeably.

import type {
  AnalysisDetail,
  AnalysisReport,
  AnalysisResult,
  PatientInput,
  PatientNode,
} from "@/lib/types";

const STORAGE_KEY = "breakpoint.knowledge-tree.v1";

type StoredAnalysis = PatientNode["analyses"][number] & {
  result: AnalysisResult;
  report?: AnalysisReport;
};

type StoredPatient = Omit<PatientNode, "analyses"> & { analyses: StoredAnalysis[] };

function read(): StoredPatient[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredPatient[]) : [];
  } catch {
    return [];
  }
}

function write(patients: StoredPatient[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(patients));
  } catch {
    // Storage full / disabled — demo history is best-effort only.
  }
}

// Upsert the patient and append a completed analysis (with its result + report).
export function savePatientResult(input: {
  patient: PatientInput;
  result: AnalysisResult;
  report?: AnalysisReport;
  fileName: string;
  antibiotic: string;
}): void {
  const now = Date.now();
  const patients = read();
  const analysisId = input.result.analysisId ?? `local-${now}-${Math.round(now % 100000)}`;
  const analysis: StoredAnalysis = {
    _id: analysisId,
    antibiotic: input.antibiotic,
    fileName: input.fileName,
    status: "complete",
    classification: input.result.classification,
    score: input.result.score,
    createdAt: now,
    result: input.result,
    report: input.report,
  };

  const existing = patients.find((p) => p.patientId === input.patient.patientId);
  if (existing) {
    existing.name = input.patient.name;
    if (input.patient.dob !== undefined) existing.dob = input.patient.dob;
    if (input.patient.notes !== undefined) existing.notes = input.patient.notes;
    existing.updatedAt = now;
    existing.analyses.unshift(analysis);
  } else {
    patients.unshift({
      _id: `patient-${input.patient.patientId}`,
      patientId: input.patient.patientId,
      name: input.patient.name,
      dob: input.patient.dob,
      notes: input.patient.notes,
      updatedAt: now,
      analyses: [analysis],
    });
  }
  write(patients);
}

// Attach the AI report to an already-saved analysis (it arrives after the result).
export function saveReportForAnalysis(analysisId: string, report: AnalysisReport): void {
  const patients = read();
  for (const patient of patients) {
    const analysis = patient.analyses.find((a) => a._id === analysisId);
    if (analysis) {
      analysis.report = report;
      write(patients);
      return;
    }
  }
}

// The tree, trimmed to the node shape (drops the heavy result/report payloads).
export function loadKnowledgeTree(): PatientNode[] {
  return read()
    .map((patient) => ({
      _id: patient._id,
      patientId: patient.patientId,
      name: patient.name,
      dob: patient.dob,
      notes: patient.notes,
      updatedAt: patient.updatedAt,
      analyses: patient.analyses.map((a) => ({
        _id: a._id,
        antibiotic: a.antibiotic,
        fileName: a.fileName,
        status: a.status,
        classification: a.classification,
        score: a.score,
        createdAt: a.createdAt,
      })),
    }))
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

// Full detail for one analysis node (report panel).
export function loadAnalysis(analysisId: string): AnalysisDetail | null {
  for (const patient of read()) {
    const analysis = patient.analyses.find((a) => a._id === analysisId);
    if (analysis) {
      return {
        analysis: {
          ...analysis.result,
          _id: analysis._id,
          fileName: analysis.fileName,
          antibiotic: analysis.antibiotic,
          status: analysis.status,
          createdAt: analysis.createdAt,
          report: analysis.report,
        },
        patient: {
          patientId: patient.patientId,
          name: patient.name,
          dob: patient.dob,
          notes: patient.notes,
        },
      };
    }
  }
  return null;
}
