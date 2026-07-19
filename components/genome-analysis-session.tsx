"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Antibiotic, PatientInput } from "@/lib/types";
import type { FastaSummary } from "@/lib/fasta";

export interface PendingGenomeAnalysis {
  file: File;
  summary: FastaSummary;
  antibiotic: Antibiotic;
  patient: PatientInput;
  runId: number;
}

interface GenomeAnalysisSessionValue {
  pending: PendingGenomeAnalysis | null;
  beginAnalysis: (analysis: PendingGenomeAnalysis) => void;
  clearAnalysis: () => void;
}

const GenomeAnalysisSession = createContext<GenomeAnalysisSessionValue | null>(null);

export function GenomeAnalysisSessionProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingGenomeAnalysis | null>(null);
  const value = useMemo(() => ({
    pending,
    beginAnalysis: setPending,
    clearAnalysis: () => setPending(null),
  }), [pending]);

  return <GenomeAnalysisSession.Provider value={value}>{children}</GenomeAnalysisSession.Provider>;
}

export function useGenomeAnalysisSession() {
  const session = useContext(GenomeAnalysisSession);
  if (!session) throw new Error("Genome analysis session is unavailable.");
  return session;
}
