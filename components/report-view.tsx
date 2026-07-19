"use client";

import type { AnalysisReport, AnalysisResult } from "@/lib/types";

// The shared report body — score ring, metrics, AI second opinion, and the
// clinical warning. Rendered both on the live run page (components/genome-reader.tsx)
// and inside the knowledge-tree detail panel so they look identical.
export function ReportView({
  result,
  antibiotic,
  fileName,
  report,
  reportError = false,
}: {
  result: AnalysisResult;
  antibiotic: string;
  fileName: string;
  report: AnalysisReport | null;
  reportError?: boolean;
}) {
  const percent = Math.round(result.score * 100);
  const label =
    result.classification === "likely_effective"
      ? "Likely effective"
      : result.classification === "likely_ineffective"
        ? "Likely ineffective"
        : "No-call / uncertain";
  const evidence =
    result.evidence === "known_marker"
      ? "Known resistance marker"
      : result.evidence === "statistical_association"
        ? "Statistical association"
        : "No known resistance signal";

  return (
    <>
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
        {result.detectedGenes && result.detectedGenes.length > 0 ? (
          <div>
            <dt>Resistance genes</dt>
            <dd title={result.detectedGenes.map((g) => g.symbol).join(", ")}>
              {result.detectedGenes.map((g) => g.symbol).join(", ")}
            </dd>
          </div>
        ) : (
          <div><dt>Sequence</dt><dd title={fileName}>{fileName}</dd></div>
        )}
      </dl>
      <AiReport report={report} error={reportError} />
      <div className="clinical-warning"><span>!</span><p><strong>Laboratory confirmation required.</strong> This result is research decision support and must not be used as an autonomous treatment recommendation.</p></div>
    </>
  );
}

const VERDICT_LABELS: Record<AnalysisReport["independentVerdict"], string> = {
  likely_effective: "Likely effective",
  likely_ineffective: "Likely ineffective",
  uncertain: "Uncertain",
};

const AGREEMENT_LABELS: Record<AnalysisReport["agreement"], string> = {
  agree: "Agrees with model",
  partial: "Partially agrees",
  disagree: "Disagrees with model",
};

export function AiReport({ report, error }: { report: AnalysisReport | null; error: boolean }) {
  return (
    <section className="ai-report" aria-live="polite">
      <header className="ai-report-head">
        <span>AI REVIEWER / SECOND OPINION</span>
        {report ? (
          <span className={`agreement-badge agreement-${report.agreement}`}>{AGREEMENT_LABELS[report.agreement]}</span>
        ) : null}
      </header>
      {!report && !error ? (
        <div className="ai-report-loading"><i />Second opinion in progress…</div>
      ) : null}
      {error ? (
        <p className="ai-report-error">The AI reviewer is unavailable — the classifier result above is unaffected.</p>
      ) : null}
      {report ? (
        <div className="ai-report-body">
          <p className="ai-report-summary">{report.summary}</p>
          {report.keyFindings.length > 0 ? (
            <ul className="ai-report-findings">
              {report.keyFindings.map((finding, index) => <li key={index}>{finding}</li>)}
            </ul>
          ) : null}
          <p className="ai-report-verdict">
            <span>Independent verdict</span>
            <strong>{VERDICT_LABELS[report.independentVerdict]}</strong>
          </p>
          <p className="ai-report-reasoning">{report.reasoning}</p>
        </div>
      ) : null}
    </section>
  );
}
