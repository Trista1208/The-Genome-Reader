"use client";

import Link from "next/link";
import Script from "next/script";
import { useRouter } from "next/navigation";
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
import { useGenomeAnalysisSession } from "@/components/genome-analysis-session";
import { ShaderAnimation } from "@/components/ui/shader-lines";

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

export function GenomeReaderApp() {
  return <GenomeReader />;
}

export function GenomeAnalysisRunApp({ convexEnabled }: { convexEnabled: boolean }) {
  if (convexEnabled) return <ConnectedGenomeAnalysisRun />;
  return <GenomeAnalysisRun runInference={runDemoInference} />;
}

function ConnectedGenomeAnalysisRun() {
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

  return <GenomeAnalysisRun runInference={runInference} />;
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

function GenomeReader() {
  const router = useRouter();
  const { beginAnalysis } = useGenomeAnalysisSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<FastaSummary | null>(null);
  const [antibiotic, setAntibiotic] = useState<Antibiotic>(ANTIBIOTICS[0]);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const acceptFile = useCallback(async (candidate: File) => {
    setError("");
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

  const startAnalysis = () => {
    if (!file || !summary) return;
    beginAnalysis({ file, summary, antibiotic, runId: Date.now() });
    router.push("/analyze/run");
  };

  const reset = () => {
    setFile(null);
    setSummary(null);
    setError("");
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

  const statusLabel = phase === "error" ? "Input error" : file ? "Ready to analyze" : "Awaiting sequence";

  return (
    <main className={`app-shell phase-shell-${phase}`}>
      <div className="split-shader-field" aria-hidden="true">
        <div className="split-shader-panel split-shader-left">
          <ShaderAnimation pattern="flow" speed={0.88} />
        </div>
        <div className="split-shader-panel split-shader-right">
          <ShaderAnimation pattern="flow" timeOffset={7.5} speed={1.08} />
        </div>
      </div>

      <header className="analysis-header">
        <Link className="analysis-brand" href="/" aria-label="Breakpoint home">
          <span aria-hidden="true">B</span>
          <strong>BREAKPOINT</strong>
        </Link>
        <p><span>GENOMIC RESPONSE CHECK</span><b>01 / FASTA</b></p>
      </header>

      <section className="analysis-page is-input">
        <div className="analysis-intro">
          <p className="analysis-eyebrow"><span /> ANTIBIOTIC RESPONSE INTELLIGENCE</p>
          <h1>Upload a genome.<br /><em>Find the breakpoint.</em></h1>
          <p className="analysis-description">Run an assembled bacterial genome through the response model to estimate whether the selected antibiotic is likely to work.</p>
          <div className="analysis-specs" aria-label="Accepted input details">
            <span><b>INPUT</b> .FA / .FASTA / .FNA</span>
            <span><b>CHECK</b> LOCAL SEQUENCE VALIDATION</span>
          </div>
        </div>

        <section className={`analysis-workspace workspace-input phase-${phase}`} aria-label="Genome analysis workspace">
        <article className="reader-card input-panel">
          <header className="reader-card-header">
            <span className="reader-step">01</span>
            <div>
              <p>SEQUENCE INPUT</p>
              <h2>Choose a genome file</h2>
            </div>
            <span className={`reader-status status-${phase}`}><i />{statusLabel}</span>
          </header>

          <div className="reader-card-body">
            <div
              className={`sequence-dropzone ${isDragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              data-testid="dropzone"
            >
              <input
                ref={inputRef}
                id="fasta-file"
                className="sequence-file-input"
                type="file"
                accept=".fa,.fasta,.fna,text/plain"
                onChange={onInput}
              />
              <div className="dropzone-icon" aria-hidden="true"><UploadIcon /></div>
              <p className="dropzone-kicker">{isDragging ? "RELEASE TO IMPORT" : file ? "SEQUENCE VALIDATED" : "DRAG + DROP"}</p>
              <h3 title={file?.name}>{file?.name ?? "Drop your assembled genome here"}</h3>
              <p className="dropzone-copy">
                {summary
                  ? `${formatBases(summary.bases)} across ${summary.contigs} contig${summary.contigs === 1 ? "" : "s"}`
                  : "FASTA, FNA or FA · sequence contents are checked before analysis"}
              </p>
              <div className="dropzone-actions">
                <button type="button" onClick={() => inputRef.current?.click()}>{file ? "Replace file" : "Browse files"}</button>
                {file ? <button type="button" className="quiet-action" onClick={reset}>Remove</button> : null}
              </div>
            </div>

            <div className="reader-controls">
              <label htmlFor="antibiotic">
                <span>TARGET ANTIBIOTIC</span>
                <span className="reader-select">
                  <select
                    id="antibiotic"
                    value={antibiotic}
                    onChange={(event) => setAntibiotic(event.target.value as Antibiotic)}
                  >
                    {ANTIBIOTICS.map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <ChevronIcon />
                </span>
              </label>
            </div>

            <button
              className="analysis-button"
              type="button"
              disabled={!file}
              onClick={startAnalysis}
              data-testid="analyze-button"
            >
              <span>{file ? "Run genome analysis" : "Select a genome to continue"}</span>
              <ArrowIcon />
            </button>
            {error ? <p className="error-message" role="alert"><span>!</span>{error}</p> : null}
          </div>
        </article>
        </section>
      </section>

      <footer className="footer-note">
        <p><strong>RESEARCH PROTOTYPE</strong> — Decision support only. Confirm every result with standard laboratory susceptibility testing.</p>
        <span>DEFENSIVE BY CONSTRUCTION / HUMAN OVERSIGHT REQUIRED</span>
      </footer>
    </main>
  );
}

function GenomeAnalysisRun({ runInference }: { runInference: RunInference }) {
  const router = useRouter();
  const { pending, clearAnalysis } = useGenomeAnalysisSession();
  const [phase, setPhase] = useState<"processing" | "complete" | "error">("processing");
  const [stageIndex, setStageIndex] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!pending) {
      router.replace("/analyze");
      return;
    }

    let active = true;
    const timers = PROCESSING_STAGES.slice(1).map((stage, index) =>
      window.setTimeout(() => {
        if (active) setStageIndex(index + 1);
      }, stage.at),
    );

    const execute = async () => {
      try {
        const sequenceDuration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 1_200 : 15_250;
        const minimumSequence = new Promise<void>((resolve) => window.setTimeout(resolve, sequenceDuration));
        const inference = runInference(pending.file, pending.antibiotic, () => {
          if (active) setStageIndex((current) => Math.max(current, 1));
        });
        const [nextResult] = await Promise.all([inference, minimumSequence]);
        if (!active) return;
        setResult(nextResult);
        setPhase("complete");
      } catch (inferenceError) {
        if (!active) return;
        setError(inferenceError instanceof Error ? inferenceError.message : "The inference endpoint did not return a valid result.");
        setPhase("error");
      }
    };

    void execute();
    return () => {
      active = false;
      timers.forEach(window.clearTimeout);
    };
  }, [pending, router, runInference]);

  if (!pending) return <main className="app-shell" aria-label="Returning to genome upload" />;

  const stage = PROCESSING_STAGES[stageIndex];
  const startOver = () => {
    clearAnalysis();
    router.push("/analyze");
  };

  return (
    <main className={`app-shell phase-shell-${phase}`}>
      <div className="split-shader-field" aria-hidden="true">
        <div className="split-shader-panel split-shader-left">
          <ShaderAnimation pattern="flow" speed={0.88} />
        </div>
        <div className="split-shader-panel split-shader-right">
          <ShaderAnimation pattern="flow" timeOffset={7.5} speed={1.08} />
        </div>
      </div>

      <header className="analysis-header">
        <Link className="analysis-brand" href="/" aria-label="Breakpoint home">
          <span aria-hidden="true">B</span>
          <strong>BREAKPOINT</strong>
        </Link>
        <p><span>GENOMIC RESPONSE CHECK</span><b>02 / MODEL RUN</b></p>
      </header>

      <section className="analysis-page is-output">
        {phase !== "complete" ? (
          <div className="analysis-intro">
            <p className="analysis-eyebrow"><span /> ANTIBIOTIC RESPONSE INTELLIGENCE</p>
            <h1>Upload a genome.<br /><em>Find the breakpoint.</em></h1>
            <p className="analysis-description">Run an assembled bacterial genome through the response model to estimate whether the selected antibiotic is likely to work.</p>
            <div className="analysis-specs" aria-label="Analysis details">
              <span><b>FILE</b> {pending.file.name}</span>
              <span><b>TARGET</b> {pending.antibiotic}</span>
            </div>
          </div>
        ) : null}

        <section className={`analysis-workspace workspace-output phase-${phase}`} aria-label="Genome model processing">
          <article className="reader-card output-panel">
            <PanelHeader
              index="B"
              title="Model output"
              meta={phase === "processing" ? `${stage.code} / ANALYSIS ACTIVE` : result?.modelVersion ?? "ANALYSIS ERROR"}
            />
            <div className="panel-body output-body">
              <canvas
                id="sequence-canvas"
                className={phase === "processing" ? "is-visible" : ""}
                aria-label="DNA sequence dissolving into a neural classifier network"
              />
              <Script
                src={`/sequence-animation.js?run=${pending.runId}`}
                strategy="afterInteractive"
                onReady={() => window.GenomeSequenceAnimation?.restart()}
              />

              {phase === "processing" ? <ProcessingState stage={stage} stageIndex={stageIndex} /> : null}
              {phase === "complete" && result ? (
                <ResultState result={result} antibiotic={pending.antibiotic} fileName={pending.file.name} onReset={startOver} />
              ) : null}
              {phase === "error" ? (
                <div className="run-error-state" role="alert">
                  <span>ANALYSIS INTERRUPTED</span>
                  <h3>The model run could not be completed.</h3>
                  <p>{error}</p>
                  <button type="button" onClick={startOver}>RETURN TO UPLOAD</button>
                </div>
              ) : null}
            </div>
          </article>
        </section>
      </section>

      <footer className="footer-note">
        <p><strong>RESEARCH PROTOTYPE</strong> — Decision support only. Confirm every result with standard laboratory susceptibility testing.</p>
        <span>DEFENSIVE BY CONSTRUCTION / HUMAN OVERSIGHT REQUIRED</span>
      </footer>
    </main>
  );
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 22V7m0 0-5 5m5-5 5 5M7 20v5h18v-5" />
    </svg>
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
