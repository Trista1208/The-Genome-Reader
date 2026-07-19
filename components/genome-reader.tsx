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
import {
  ANTIBIOTICS,
  type AnalysisReport,
  type AnalysisResult,
  type Antibiotic,
  type GenerateReport,
  type PatientInput,
  type RunInference,
} from "@/lib/types";
import { formatBases, validateFasta, type FastaSummary } from "@/lib/fasta";
import { useGenomeAnalysisSession } from "@/components/genome-analysis-session";
import { ShaderAnimation } from "@/components/ui/shader-lines";
import { ReportView } from "@/components/report-view";
import { savePatientResult, saveReportForAnalysis } from "@/lib/local-history";

const CONVEX_ENABLED = Boolean(process.env.NEXT_PUBLIC_CONVEX_URL);

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
  return <GenomeAnalysisRun runInference={runDemoInference} generateReport={generateDemoReport} />;
}

function ConnectedGenomeAnalysisRun() {
  const generateUploadUrl = useMutation(anyApi.files.generateUploadUrl);
  const runModel = useAction(anyApi.analysis.runInference);
  const runReport = useAction(anyApi.report.generateReport);

  const runInference: RunInference = useCallback(
    async (file, antibiotic, patient, onUploaded) => {
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
        patient,
      })) as AnalysisResult;
    },
    [generateUploadUrl, runModel],
  );

  const generateReport: GenerateReport = useCallback(
    async (result, antibiotic, fileName) =>
      (await runReport({
        analysisId: result.analysisId,
        antibiotic,
        fileName,
        score: result.score,
        confidence: result.confidence,
        classification: result.classification,
        evidence: result.evidence,
        detectedGenes: result.detectedGenes,
        sequenceLength: result.sequenceLength,
        contigCount: result.contigCount,
      })) as AnalysisReport,
    [runReport],
  );

  return <GenomeAnalysisRun runInference={runInference} generateReport={generateReport} />;
}

async function runDemoInference(
  file: File,
  _antibiotic: Antibiotic,
  _patient: PatientInput,
  onUploaded: () => void,
): Promise<AnalysisResult> {
  await new Promise((resolve) => window.setTimeout(resolve, 700));
  onUploaded();
  const summary = await validateFasta(file);
  await new Promise((resolve) => window.setTimeout(resolve, 900));
  const analysisId = `local-${Date.now()}`;
  return { ...DEMO_RESULT, analysisId, sequenceLength: summary.bases, contigCount: summary.contigs };
}

// Local stand-in for the AI reviewer subagent so the run page demonstrates the
// second-opinion flow without Convex or an OpenAI key. Derived heuristically
// from the classifier's own verdict and detected genes.
async function generateDemoReport(
  result: AnalysisResult,
  antibiotic: Antibiotic,
): Promise<AnalysisReport> {
  await new Promise((resolve) => window.setTimeout(resolve, 1_600));
  const genes = result.detectedGenes?.map((g) => g.symbol) ?? [];
  const geneList = genes.length ? genes.join(", ") : "no known resistance markers";
  const verdictWord =
    result.classification === "likely_effective"
      ? "should remain effective"
      : result.classification === "likely_ineffective"
        ? "is at risk of resistance"
        : "gives a mixed signal";
  return {
    summary: `Reviewing this genome against ${antibiotic}, the profile ${verdictWord}. Detected: ${geneList}.`,
    keyFindings: genes.length
      ? [
          `${genes.length} resistance-associated gene${genes.length === 1 ? "" : "s"} detected (${geneList}).`,
          "Gene profile is broadly consistent with the classifier's calibrated score.",
        ]
      : [
          "No known resistance markers were detected in the assembly.",
          "Absence of markers supports a susceptible read on this drug.",
        ],
    independentVerdict: result.classification,
    agreement: "agree",
    reasoning:
      "This offline demo report mirrors the classifier's verdict. Connect the inference and OpenAI services for an independent AI cross-check.",
  };
}

function GenomeReader() {
  const router = useRouter();
  const { beginAnalysis } = useGenomeAnalysisSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<FastaSummary | null>(null);
  const [antibiotic, setAntibiotic] = useState<Antibiotic>(ANTIBIOTICS[0]);
  const [patientId, setPatientId] = useState("");
  const [patientName, setPatientName] = useState("");
  const [patientDob, setPatientDob] = useState("");
  const [patientNotes, setPatientNotes] = useState("");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const patientReady = patientId.trim().length > 0 && patientName.trim().length > 0;
  const canRun = Boolean(file && summary) && patientReady;

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
    if (!file || !summary || !patientReady) return;
    const patient: PatientInput = {
      patientId: patientId.trim(),
      name: patientName.trim(),
      dob: patientDob.trim() || undefined,
      notes: patientNotes.trim() || undefined,
    };
    beginAnalysis({ file, summary, antibiotic, patient, runId: Date.now() });
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
        <Link className="analysis-records-link" href="/knowledge">PATIENT RECORDS</Link>
        <p><span>GENOMIC RESPONSE CHECK</span><b>01 / FASTA</b></p>
      </header>

      <section className="analysis-page is-input">
        <div className="analysis-intro">
          <p className="analysis-eyebrow"><span /> ANTIBIOTIC RESPONSE INTELLIGENCE</p>
          <h1>Upload a genome.<br /><em>Find the breakpoint.</em></h1>
          <p className="analysis-description">Run an assembled bacterial genome through the response model to estimate whether the selected antibiotic is likely to work.</p>
        </div>

        <section className={`analysis-workspace workspace-input phase-${phase}`} aria-label="Genome analysis workspace">
        <article className="reader-card input-panel">
          <header className="reader-card-header">
            <div>
              <h2>Choose a genome file</h2>
            </div>
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

            <fieldset className="patient-fields">
              <legend>PATIENT</legend>
              <div className="patient-grid">
                <label htmlFor="patient-id">
                  <span>PATIENT ID <i>*</i></span>
                  <input
                    id="patient-id"
                    type="text"
                    autoComplete="off"
                    placeholder="e.g. MRN-4471"
                    value={patientId}
                    onChange={(event) => setPatientId(event.target.value)}
                  />
                </label>
                <label htmlFor="patient-name">
                  <span>NAME <i>*</i></span>
                  <input
                    id="patient-name"
                    type="text"
                    autoComplete="off"
                    placeholder="e.g. Jane Doe"
                    value={patientName}
                    onChange={(event) => setPatientName(event.target.value)}
                  />
                </label>
                <label htmlFor="patient-dob">
                  <span>DATE OF BIRTH</span>
                  <input
                    id="patient-dob"
                    type="date"
                    value={patientDob}
                    onChange={(event) => setPatientDob(event.target.value)}
                  />
                </label>
                <label htmlFor="patient-notes" className="patient-notes-field">
                  <span>NOTES</span>
                  <input
                    id="patient-notes"
                    type="text"
                    autoComplete="off"
                    placeholder="Optional clinical note"
                    value={patientNotes}
                    onChange={(event) => setPatientNotes(event.target.value)}
                  />
                </label>
              </div>
            </fieldset>

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
              disabled={!canRun}
              onClick={startAnalysis}
              data-testid="analyze-button"
            >
              <span>
                {!file
                  ? "Select a genome to continue"
                  : !patientReady
                    ? "Add patient ID and name to continue"
                    : "Run genome analysis"}
              </span>
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

function GenomeAnalysisRun({
  runInference,
  generateReport,
}: {
  runInference: RunInference;
  generateReport: GenerateReport;
}) {
  const router = useRouter();
  const { pending, clearAnalysis } = useGenomeAnalysisSession();
  const [phase, setPhase] = useState<"processing" | "complete" | "error">("processing");
  const [stageIndex, setStageIndex] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [reportError, setReportError] = useState(false);

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
        const inference = runInference(pending.file, pending.antibiotic, pending.patient, () => {
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

  // In demo/offline mode the backend never sees the run, so persist the result
  // to the localStorage knowledge tree ourselves. (Convex mode already stores it.)
  useEffect(() => {
    if (CONVEX_ENABLED || phase !== "complete" || !result || !pending) return;
    savePatientResult({
      patient: pending.patient,
      result,
      fileName: pending.file.name,
      antibiotic: pending.antibiotic,
    });
  }, [phase, result, pending]);

  // The AI reviewer subagent runs concurrently: it fires the moment the
  // classifier result is ready and streams into its own section, so the main
  // score never waits on it.
  useEffect(() => {
    if (phase !== "complete" || !result || !pending) return;
    let active = true;
    generateReport(result, pending.antibiotic, pending.file.name)
      .then((next) => {
        if (!active) return;
        setReport(next);
        if (!CONVEX_ENABLED && result.analysisId) saveReportForAnalysis(result.analysisId, next);
      })
      .catch(() => {
        if (active) setReportError(true);
      });
    return () => {
      active = false;
    };
  }, [phase, result, pending, generateReport]);

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
        <Link className="analysis-records-link" href="/knowledge">PATIENT RECORDS</Link>
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
                <ResultState
                  result={result}
                  antibiotic={pending.antibiotic}
                  fileName={pending.file.name}
                  onReset={startOver}
                  report={report}
                  reportError={reportError}
                />
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

function ResultState({ result, antibiotic, fileName, onReset, report, reportError }: {
  result: AnalysisResult;
  antibiotic: Antibiotic;
  fileName: string;
  onReset: () => void;
  report: AnalysisReport | null;
  reportError: boolean;
}) {
  return (
    <div className="result-state">
      <div className="result-stamp">
        <span>OUTPUT VALIDATED</span>
        <button type="button" onClick={onReset}>NEW WORKBOOK</button>
        <span>{new Date().toISOString().slice(0, 10)}</span>
      </div>
      <ReportView
        result={result}
        antibiotic={antibiotic}
        fileName={fileName}
        report={report}
        reportError={reportError}
      />
    </div>
  );
}

function ArrowIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13M11 5l5 5-5 5" /></svg>;
}

function ChevronIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6 8 4 4 4-4" /></svg>;
}
