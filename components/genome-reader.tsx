"use client";

import Script from "next/script";
import { anyApi } from "convex/server";
import { useAction, useMutation } from "convex/react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { ANTIBIOTICS, type AnalysisResult, type Antibiotic, type RunInference } from "@/lib/types";
import { formatBases, validateFasta, type FastaSummary } from "@/lib/fasta";
import { LiquidTitle } from "@/components/liquid-title";
import { AsciiRenderer } from "@/components/ui/ascii-renderer";

type Phase = "idle" | "ready" | "processing" | "complete" | "error";

const PROCESSING_STAGES = [
  { at: 0, code: "SEQ.01", label: "Reading sequence topology" },
  { at: 3000, code: "VEC.02", label: "Encoding resistance markers" },
  { at: 6500, code: "MDL.03", label: "Running classifier inference" },
  { at: 10300, code: "CAL.04", label: "Calibrating response score" },
  { at: 13700, code: "VAL.05", label: "Validating output envelope" },
] as const;

const DEMO_RESULT: AnalysisResult = {
  score: 0.82,
  confidence: 0.91,
  classification: "likely_effective",
  evidence: "statistical_association",
  modelVersion: "GFR-ECOLI-0.8.2",
};

declare global {
  interface Window {
    GenomeSequenceAnimation?: { restart: () => void };
  }
}

export function GenomeReaderApp({ convexEnabled }: { convexEnabled: boolean }) {
  if (convexEnabled) return <ConnectedGenomeReader />;
  return <GenomeReader runInference={runDemoInference} />;
}

function ConnectedGenomeReader() {
  const generateUploadUrl = useMutation(anyApi.files.generateUploadUrl);
  const runModel = useAction(anyApi.analysis.runInference);

  const runInference: RunInference = useCallback(
    async (file, antibiotic, onUploaded) => {
      const uploadUrl = await generateUploadUrl({});
      const response = await fetch(uploadUrl, {
        method: "POST",
        headers: { "Content-Type": file.type || "text/plain" },
        body: file,
      });
      if (!response.ok) throw new Error("The sequence could not be secured in storage.");
      const { storageId } = (await response.json()) as { storageId: string };
      onUploaded();
      return (await runModel({
        storageId,
        fileName: file.name,
        fileSize: file.size,
        antibiotic,
      })) as AnalysisResult;
    },
    [generateUploadUrl, runModel],
  );

  return <GenomeReader runInference={runInference} />;
}

async function runDemoInference(
  file: File,
  _antibiotic: Antibiotic,
  onUploaded: () => void,
): Promise<AnalysisResult> {
  await new Promise((resolve) => window.setTimeout(resolve, 700));
  onUploaded();
  const summary = await validateFasta(file);
  await new Promise((resolve) => window.setTimeout(resolve, 900));
  return { ...DEMO_RESULT, sequenceLength: summary.bases, contigCount: summary.contigs };
}

function GenomeReader({ runInference }: { runInference: RunInference }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<FastaSummary | null>(null);
  const [antibiotic, setAntibiotic] = useState<Antibiotic>(ANTIBIOTICS[0]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [stageIndex, setStageIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (phase !== "processing") return;
    const timers = PROCESSING_STAGES.slice(1).map((stage, index) =>
      window.setTimeout(() => setStageIndex(index + 1), stage.at),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [phase]);

  const acceptFile = useCallback(async (candidate: File) => {
    setError("");
    setResult(null);
    try {
      const nextSummary = await validateFasta(candidate);
      setFile(candidate);
      setSummary(nextSummary);
      setPhase("ready");
    } catch (validationError) {
      setFile(null);
      setSummary(null);
      setError(validationError instanceof Error ? validationError.message : "This sequence could not be read.");
      setPhase("error");
    }
  }, []);

  const startAnalysis = async () => {
    if (!file || !summary) return;
    setError("");
    setResult(null);
    setStageIndex(0);
    setPhase("processing");
    if (window.GenomeSequenceAnimation) window.GenomeSequenceAnimation.restart();
    else window.dispatchEvent(new Event("genome:restart-animation"));

    try {
      const sequenceDuration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 1_200 : 15_250;
      const minimumSequence = new Promise<void>((resolve) => window.setTimeout(resolve, sequenceDuration));
      const inference = runInference(file, antibiotic, () => setStageIndex((current) => Math.max(current, 1)));
      const [nextResult] = await Promise.all([inference, minimumSequence]);
      setResult(nextResult);
      setPhase("complete");
    } catch (inferenceError) {
      setError(inferenceError instanceof Error ? inferenceError.message : "The inference endpoint did not return a valid result.");
      setPhase("error");
    }
  };

  const reset = () => {
    setFile(null);
    setSummary(null);
    setResult(null);
    setError("");
    setStageIndex(0);
    setPhase("idle");
    if (inputRef.current) inputRef.current.value = "";
  };

  const onInput = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (selected) void acceptFile(selected);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) void acceptFile(dropped);
  };

  const stage = PROCESSING_STAGES[stageIndex];
  const showingOutput = phase === "processing" || phase === "complete";

  return (
    <main className="app-shell">
      <div className="ambient-grid" aria-hidden="true" />
      <section className="hero" id="top">
        <LiquidTitle />
      </section>

      <section className={`analysis-workspace ${showingOutput ? "workspace-output" : "workspace-input"} phase-${phase}`} aria-label="Genome analysis workspace">
        {!showingOutput ? (
        <article className="industrial-panel input-panel">
          <PanelHeader index="A" title="Genome workbook" meta="READ ONLY / FASTA" />

          <div className="panel-body input-body">
            <div
              className={`retro-sheet ${isDragging ? "is-dragging" : ""}`}
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              data-testid="dropzone"
            >
              <div className="sheet-dna-backdrop" aria-hidden="true">
                <AsciiRenderer variant="backdrop" />
              </div>
              <input
                ref={inputRef}
                id="fasta-file"
                className="sheet-file-input"
                type="file"
                accept=".fa,.fasta,.fna,text/plain"
                onChange={onInput}
              />
              <div className="sheet-titlebar">
                <span>GENOME.XLS</span>
                <span>[ READ ONLY ]</span>
              </div>
              <div className="sheet-menubar">
                <span>FILE</span><span>EDIT</span><span>VIEW</span><span>INSERT</span><span>DATA</span>
                <div className="sheet-actions">
                  {file ? <button type="button" onClick={reset}>NEW</button> : null}
                  <button type="button" onClick={() => inputRef.current?.click()}>OPEN FILE</button>
                </div>
              </div>
              <div className="sheet-formula">
                <span>{file ? "B1" : "A1"}</span>
                <b>fx</b>
                <p>{file?.name ?? "Select or drop an assembled FASTA file"}</p>
              </div>
              <div className="sheet-grid">
                <span className="sheet-corner" /><span className="sheet-column">A</span><span className="sheet-column">B</span><span className="sheet-column">C</span>

                <span className="sheet-row">1</span><span className="sheet-cell sheet-label">FILE NAME</span><span className="sheet-cell sheet-value" title={file?.name}>{file?.name ?? "NO FILE SELECTED"}</span><span className="sheet-cell sheet-unit">FASTA</span>
                <span className="sheet-row">2</span><span className="sheet-cell sheet-label">SEQUENCE SIZE</span><span className="sheet-cell sheet-value">{summary ? formatBases(summary.bases) : "—"}</span><span className="sheet-cell sheet-unit">BASES</span>
                <span className="sheet-row">3</span><span className="sheet-cell sheet-label">CONTIG COUNT</span><span className="sheet-cell sheet-value">{summary?.contigs ?? "—"}</span><span className="sheet-cell sheet-unit">RECORDS</span>
                <span className="sheet-row">4</span><span className="sheet-cell sheet-label">GC CONTENT</span><span className="sheet-cell sheet-value">{summary ? `${summary.gcContent.toFixed(1)}%` : "—"}</span><span className="sheet-cell sheet-unit">CALCULATED</span>
                <span className="sheet-row">5</span><span className="sheet-cell sheet-label">TARGET DRUG</span>
                <span className="sheet-cell sheet-select-cell">
                  <select
                    id="antibiotic"
                    value={antibiotic}
                    onChange={(event) => setAntibiotic(event.target.value as Antibiotic)}
                    aria-label="Target antibiotic"
                  >
                    {ANTIBIOTICS.map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <ChevronIcon />
                </span>
                <span className="sheet-cell sheet-unit">MODEL INPUT</span>
                <span className="sheet-row">6</span><span className="sheet-cell sheet-label">SYSTEM STATUS</span>
                <span className={`sheet-cell sheet-value sheet-status status-${phase}`}>
                  {phase === "error" ? "INPUT ERROR" : file ? "READY" : "AWAITING FILE"}
                </span>
                <span className="sheet-cell sheet-unit">{file ? "VALIDATED" : "EMPTY"}</span>
              </div>
              <div className="sheet-statusbar">
                <span>{isDragging ? "RELEASE TO IMPORT FILE" : file ? "1 RECORD SELECTED" : "READY — DROP FILE OR CHOOSE OPEN FILE"}</span>
                <span>NUM&nbsp;&nbsp;CAPS&nbsp;&nbsp;SCRL</span>
              </div>
            </div>

            <button
              className="primary-button"
              type="button"
              disabled={!file}
              onClick={startAnalysis}
              data-testid="analyze-button"
            >
              <span>Run workbook analysis</span>
              <ArrowIcon />
            </button>
            {error ? <p className="error-message" role="alert"><span>!</span>{error}</p> : null}
          </div>
        </article>
        ) : (
        <article className="industrial-panel output-panel">
          <PanelHeader
            index="B"
            title="Model output"
            meta={phase === "processing" ? `${stage.code} / ANALYSIS ACTIVE` : result?.modelVersion ?? "AWAITING INPUT"}
          />
          <div className="panel-body output-body">
            <canvas
              id="sequence-canvas"
              className={phase === "processing" ? "is-visible" : ""}
              aria-label="DNA sequence dissolving into a neural classifier network"
            />
            <Script src="/sequence-animation.js" strategy="afterInteractive" />

            {phase === "processing" ? <ProcessingState stage={stage} stageIndex={stageIndex} /> : null}
            {phase === "complete" && result ? (
              <ResultState result={result} antibiotic={antibiotic} fileName={file?.name ?? "Sequence"} onReset={reset} />
            ) : null}
          </div>
        </article>
        )}
      </section>

      <footer className="footer-note">
        <p><strong>RESEARCH PROTOTYPE</strong> — Decision support only. Confirm every result with standard laboratory susceptibility testing.</p>
        <span>DEFENSIVE BY CONSTRUCTION / HUMAN OVERSIGHT REQUIRED</span>
      </footer>
    </main>
  );
}

function PanelHeader({ index, title, meta }: { index: string; title: string; meta: string }) {
  return (
    <header className="panel-header">
      <div><span>{index}</span><h2>{title}</h2></div>
      <p>{meta}</p>
    </header>
  );
}

function ProcessingState({ stage, stageIndex }: { stage: (typeof PROCESSING_STAGES)[number]; stageIndex: number }) {
  return (
    <div className="processing-state" aria-live="polite">
      <div className="processing-topline">
        <span>LIVE MODEL TELEMETRY</span>
        <span className="recording"><i /> RECORDING</span>
      </div>
      <div className="stage-readout">
        <span>{stage.code}</span>
        <p>{stage.label}</p>
      </div>
      <div className="stage-rail">
        {PROCESSING_STAGES.map((item, index) => (
          <span key={item.code} className={index <= stageIndex ? "complete" : ""}><i />{String(index + 1).padStart(2, "0")}</span>
        ))}
      </div>
      <p className="processing-warning">Do not close this window. Output is being checked against the calibrated response envelope.</p>
    </div>
  );
}

function ResultState({ result, antibiotic, fileName, onReset }: {
  result: AnalysisResult;
  antibiotic: Antibiotic;
  fileName: string;
  onReset: () => void;
}) {
  const percent = Math.round(result.score * 100);
  const label = result.classification === "likely_effective"
    ? "Likely effective"
    : result.classification === "likely_ineffective"
      ? "Likely ineffective"
      : "No-call / uncertain";
  const evidence = result.evidence === "known_marker"
    ? "Known resistance marker"
    : result.evidence === "statistical_association"
      ? "Statistical association"
      : "No known resistance signal";

  return (
    <div className="result-state">
      <div className="result-stamp">
        <span>OUTPUT VALIDATED</span>
        <button type="button" onClick={onReset}>NEW WORKBOOK</button>
        <span>{new Date().toISOString().slice(0, 10)}</span>
      </div>
      <div className="score-layout">
        <div className="score-ring" style={{ "--score": `${percent * 3.6}deg` } as React.CSSProperties}>
          <div><strong>{percent}</strong><span>%</span><small>RESPONSE<br />PROBABILITY</small></div>
        </div>
        <div className="score-copy">
          <p className="score-kicker">PREDICTED EFFECTIVENESS</p>
          <h3>{label}</h3>
          <p>The model estimates a <strong>{percent}% probability</strong> that {antibiotic} will be effective for this genomic profile.</p>
        </div>
      </div>
      <dl className="result-metrics">
        <div><dt>Confidence</dt><dd>{Math.round(result.confidence * 100)}%</dd></div>
        <div><dt>Evidence class</dt><dd>{evidence}</dd></div>
        <div><dt>Sequence</dt><dd title={fileName}>{fileName}</dd></div>
      </dl>
      <div className="clinical-warning"><span>!</span><p><strong>Laboratory confirmation required.</strong> This result is research decision support and must not be used as an autonomous treatment recommendation.</p></div>
    </div>
  );
}

function ArrowIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13M11 5l5 5-5 5" /></svg>;
}

function ChevronIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6 8 4 4 4-4" /></svg>;
}
