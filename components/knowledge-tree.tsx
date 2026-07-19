"use client";

import Link from "next/link";
import { anyApi } from "convex/server";
import { useQuery } from "convex/react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import type {
  AnalysisNode,
  AnalysisReport,
  AnalysisResult,
  PatientInput,
  PatientNode,
} from "@/lib/types";
import { ShaderAnimation } from "@/components/ui/shader-lines";
import { ReportView } from "@/components/report-view";
import { loadAnalysis, loadKnowledgeTree } from "@/lib/local-history";

// Layout geometry for the horizontal node graph: root -> patients -> analyses.
const ROOT_X = 40;
const ROOT_W = 120;
const PATIENT_X = 260;
const PATIENT_W = 200;
const ANALYSIS_X = 580;
const ANALYSIS_W = 250;
const SVG_WIDTH = ANALYSIS_X + ANALYSIS_W + 40;
const ROW = 64;
const PAD = 28;

type NormalizedDetail = {
  result: AnalysisResult;
  report: AnalysisReport | null;
  fileName: string;
  antibiotic: string;
  status: "processing" | "complete" | "failed";
  patient: PatientInput | null;
};

type DetailPanelProps = { analysisId: string | null; onClose: () => void };

// The Convex and demo paths never share a hook call site: convex hooks would
// throw without a ConvexProvider (which is absent in offline/demo builds), so
// each variant is a separate component and only the presentational view is shared.
export function KnowledgeTree({ convexEnabled }: { convexEnabled: boolean }) {
  return convexEnabled ? <ConvexKnowledgeTree /> : <DemoKnowledgeTree />;
}

function ConvexKnowledgeTree() {
  const tree = useQuery(anyApi.patients.knowledgeTree, {}) as PatientNode[] | undefined;
  return <KnowledgeTreeView tree={tree} DetailPanel={ConvexDetailPanel} />;
}

function DemoKnowledgeTree() {
  const [tree, setTree] = useState<PatientNode[] | undefined>(undefined);
  // Read after mount so first client render matches SSR (no hydration mismatch).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from localStorage (non-reactive external store) post-mount
    setTree(loadKnowledgeTree());
  }, []);
  return <KnowledgeTreeView tree={tree} DetailPanel={DemoDetailPanel} />;
}

function KnowledgeTreeView({
  tree,
  DetailPanel,
}: {
  tree: PatientNode[] | undefined;
  DetailPanel: ComponentType<DetailPanelProps>;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loading = tree === undefined;
  const term = search.trim().toLowerCase();
  const isMatch = (p: PatientNode) =>
    !term || p.name.toLowerCase().includes(term) || p.patientId.toLowerCase().includes(term);

  const layout = useMemo(() => buildLayout(tree ?? []), [tree]);

  // Scroll the first matching patient into view when searching.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!term || !scrollRef.current) return;
    const first = (tree ?? []).find((p) => p.name.toLowerCase().includes(term) || p.patientId.toLowerCase().includes(term));
    if (!first) return;
    const el = scrollRef.current.querySelector(`[data-patient="${cssEscape(first._id)}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [term, tree]);

  return (
    <main className="app-shell knowledge-shell">
      <div className="split-shader-field" aria-hidden="true">
        <div className="split-shader-panel split-shader-left">
          <ShaderAnimation pattern="flow" speed={0.7} />
        </div>
        <div className="split-shader-panel split-shader-right">
          <ShaderAnimation pattern="flow" timeOffset={7.5} speed={0.9} />
        </div>
      </div>

      <header className="analysis-header">
        <Link className="analysis-brand" href="/" aria-label="Breakpoint home">
          <span aria-hidden="true">B</span>
          <strong>BREAKPOINT</strong>
        </Link>
        <Link className="analysis-records-link" href="/analyze">NEW ANALYSIS</Link>
        <p><span>KNOWLEDGE TREE</span><b>PATIENT RECORDS</b></p>
      </header>

      <section className="knowledge-page">
        <div className="knowledge-intro">
          <p className="analysis-eyebrow"><span /> PATIENT KNOWLEDGE TREE</p>
          <h1>Find a patient. <em>Open their report.</em></h1>
          <p className="analysis-description">Every genome you run is saved under its patient. Search by name or ID, then click an antibiotic node to open the full report.</p>
          <div className="knowledge-search">
            <SearchIcon />
            <input
              type="search"
              placeholder="Search patients by name or ID…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search patients"
            />
          </div>
        </div>

        <div className="knowledge-layout">
          <div className="knowledge-canvas" ref={scrollRef}>
            {loading ? (
              <p className="knowledge-empty">Loading patient records…</p>
            ) : layout.patients.length === 0 ? (
              <p className="knowledge-empty">
                No patient records yet. <Link href="/analyze">Run your first analysis</Link> to grow the tree.
              </p>
            ) : (
              <svg
                className="knowledge-graph"
                width={SVG_WIDTH}
                height={layout.height}
                viewBox={`0 0 ${SVG_WIDTH} ${layout.height}`}
                role="tree"
                aria-label="Patient knowledge tree"
              >
                {/* root -> patient edges */}
                {layout.patients.map((p) => (
                  <path
                    key={`e-root-${p.patient._id}`}
                    className={`tree-edge ${isMatch(p.patient) ? "" : "is-dim"}`}
                    d={edgePath(ROOT_X + ROOT_W, layout.rootY, PATIENT_X, p.y)}
                  />
                ))}
                {/* patient -> analysis edges */}
                {layout.patients.flatMap((p) =>
                  p.analyses.map((a) => (
                    <path
                      key={`e-${p.patient._id}-${a.node._id}`}
                      className={`tree-edge ${isMatch(p.patient) ? "" : "is-dim"} ${selectedId === a.node._id ? "is-selected" : ""}`}
                      d={edgePath(PATIENT_X + PATIENT_W, p.y, ANALYSIS_X, a.y)}
                    />
                  )),
                )}

                {/* root node */}
                <g className="tree-node node-root">
                  <rect x={ROOT_X} y={layout.rootY - 26} width={ROOT_W} height={52} rx={12} />
                  <text x={ROOT_X + ROOT_W / 2} y={layout.rootY - 2} className="node-title">PATIENTS</text>
                  <text x={ROOT_X + ROOT_W / 2} y={layout.rootY + 15} className="node-sub">{layout.patients.length}</text>
                </g>

                {/* patient nodes */}
                {layout.patients.map((p) => {
                  const active = isMatch(p.patient);
                  return (
                    <g
                      key={p.patient._id}
                      className={`tree-node node-patient ${active ? "" : "is-dim"}`}
                      data-patient={p.patient._id}
                    >
                      <rect x={PATIENT_X} y={p.y - 28} width={PATIENT_W} height={56} rx={12} />
                      <text x={PATIENT_X + 16} y={p.y - 4} className="node-title" textAnchor="start">
                        {truncate(p.patient.name, 24)}
                      </text>
                      <text x={PATIENT_X + 16} y={p.y + 15} className="node-sub" textAnchor="start">
                        {p.patient.patientId}
                      </text>
                    </g>
                  );
                })}

                {/* analysis nodes */}
                {layout.patients.flatMap((p) =>
                  p.analyses.map((a) => {
                    const active = isMatch(p.patient);
                    const cls = classOf(a.node);
                    return (
                      <g
                        key={a.node._id}
                        className={`tree-node node-analysis verdict-${cls} ${active ? "" : "is-dim"} ${selectedId === a.node._id ? "is-selected" : ""}`}
                        onClick={() => setSelectedId(a.node._id)}
                        role="treeitem"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedId(a.node._id);
                          }
                        }}
                      >
                        <rect x={ANALYSIS_X} y={a.y - 22} width={ANALYSIS_W} height={44} rx={10} />
                        <circle cx={ANALYSIS_X + 20} cy={a.y} r={6} className="verdict-dot" />
                        <text x={ANALYSIS_X + 36} y={a.y - 1} className="node-title" textAnchor="start">
                          {truncate(a.node.antibiotic, 22)}
                        </text>
                        <text x={ANALYSIS_X + 36} y={a.y + 14} className="node-sub" textAnchor="start">
                          {scoreLabel(a.node)}
                        </text>
                      </g>
                    );
                  }),
                )}
              </svg>
            )}
          </div>

          <DetailPanel analysisId={selectedId} onClose={() => setSelectedId(null)} />
        </div>
      </section>

      <footer className="footer-note">
        <p><strong>RESEARCH PROTOTYPE</strong> — Decision support only. Confirm every result with standard laboratory susceptibility testing.</p>
        <span>DEFENSIVE BY CONSTRUCTION / HUMAN OVERSIGHT REQUIRED</span>
      </footer>
    </main>
  );
}

// ---- detail panels (one per data source, so hooks stay unconditional) -------

function ConvexDetailPanel({ analysisId, onClose }: DetailPanelProps) {
  const raw = useQuery(anyApi.patients.getAnalysis, analysisId ? { analysisId } : "skip");
  const detail = analysisId ? normalizeConvex(raw as ConvexDetail) : null;
  const loading = Boolean(analysisId) && raw === undefined;
  return <DetailShell analysisId={analysisId} onClose={onClose} detail={detail} loading={loading} />;
}

function DemoDetailPanel({ analysisId, onClose }: DetailPanelProps) {
  const [detail, setDetail] = useState<NormalizedDetail | null>(null);
  useEffect(() => {
    const loaded = analysisId ? loadAnalysis(analysisId) : null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from localStorage (non-reactive external store) post-mount
    setDetail(loaded ? normalizeDemo(loaded) : null);
  }, [analysisId]);
  return <DetailShell analysisId={analysisId} onClose={onClose} detail={detail} loading={false} />;
}

function DetailShell({
  analysisId,
  onClose,
  detail,
  loading,
}: DetailPanelProps & { detail: NormalizedDetail | null; loading: boolean }) {
  if (!analysisId) {
    return (
      <aside className="knowledge-detail is-empty">
        <p>Select an antibiotic node to open the patient&apos;s report.</p>
      </aside>
    );
  }

  return (
    <aside className="knowledge-detail">
      <div className="knowledge-detail-head">
        <span>PATIENT REPORT</span>
        <button type="button" onClick={onClose} aria-label="Close report">×</button>
      </div>
      {loading ? (
        <p className="knowledge-empty">Loading report…</p>
      ) : !detail ? (
        <p className="knowledge-empty">This report could not be found.</p>
      ) : (
        <div className="knowledge-detail-body">
          {detail.patient ? (
            <dl className="detail-patient">
              <div><dt>Patient</dt><dd>{detail.patient.name}</dd></div>
              <div><dt>ID</dt><dd>{detail.patient.patientId}</dd></div>
              {detail.patient.dob ? <div><dt>DOB</dt><dd>{detail.patient.dob}</dd></div> : null}
              {detail.patient.notes ? <div><dt>Notes</dt><dd>{detail.patient.notes}</dd></div> : null}
            </dl>
          ) : null}
          {detail.status !== "complete" ? (
            <p className="knowledge-empty">This analysis is {detail.status}. No report is available.</p>
          ) : (
            <div className="result-state">
              <ReportView
                result={detail.result}
                antibiotic={detail.antibiotic}
                fileName={detail.fileName}
                report={detail.report}
              />
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

// ---- data normalization ----------------------------------------------------

type ConvexDetail = {
  analysis: Record<string, unknown> | null;
  patient: Record<string, unknown> | null;
} | null | undefined;

function normalizeConvex(detail: ConvexDetail): NormalizedDetail | null {
  if (!detail || !detail.analysis) return null;
  const a = detail.analysis as Record<string, unknown>;
  const p = detail.patient as Record<string, unknown> | null;
  return {
    result: toResult(a),
    report: (a.report as AnalysisReport | undefined) ?? null,
    fileName: String(a.fileName ?? ""),
    antibiotic: String(a.antibiotic ?? ""),
    status: (a.status as NormalizedDetail["status"]) ?? "complete",
    patient: p
      ? {
          patientId: String(p.patientId ?? ""),
          name: String(p.name ?? ""),
          dob: p.dob ? String(p.dob) : undefined,
          notes: p.notes ? String(p.notes) : undefined,
        }
      : null,
  };
}

function normalizeDemo(detail: {
  analysis: AnalysisResult & {
    fileName: string;
    antibiotic: string;
    status: NormalizedDetail["status"];
    report?: AnalysisReport;
  };
  patient: PatientInput | null;
}): NormalizedDetail {
  const { fileName, antibiotic, status, report, ...result } = detail.analysis;
  return { result, report: report ?? null, fileName, antibiotic, status, patient: detail.patient };
}

function toResult(a: Record<string, unknown>): AnalysisResult {
  return {
    analysisId: String(a._id ?? ""),
    score: typeof a.score === "number" ? a.score : 0,
    confidence: typeof a.confidence === "number" ? a.confidence : 0,
    classification: (a.classification as AnalysisResult["classification"]) ?? "uncertain",
    evidence: (a.evidence as AnalysisResult["evidence"]) ?? "no_known_signal",
    modelVersion: String(a.modelVersion ?? ""),
    noCall: typeof a.noCall === "boolean" ? a.noCall : undefined,
    detectedGenes: (a.detectedGenes as AnalysisResult["detectedGenes"]) ?? undefined,
    sequenceLength: typeof a.sequenceLength === "number" ? a.sequenceLength : undefined,
    contigCount: typeof a.contigCount === "number" ? a.contigCount : undefined,
  };
}

// ---- layout + helpers ------------------------------------------------------

type LaidPatient = {
  patient: PatientNode;
  y: number;
  analyses: { node: AnalysisNode; x: number; y: number }[];
};

function buildLayout(patients: PatientNode[]): { patients: LaidPatient[]; height: number; rootY: number } {
  let cursor = PAD;
  const laid: LaidPatient[] = patients.map((patient) => {
    const count = Math.max(patient.analyses.length, 1);
    const bandTop = cursor;
    cursor += count * ROW;
    const analyses = patient.analyses.map((node, i) => ({
      node,
      x: ANALYSIS_X,
      y: bandTop + i * ROW + ROW / 2,
    }));
    return { patient, y: bandTop + (count * ROW) / 2, analyses };
  });
  const height = Math.max(cursor + PAD, 200);
  return { patients: laid, height, rootY: height / 2 };
}

function edgePath(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2;
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
}

function classOf(node: AnalysisNode): string {
  if (node.status !== "complete" || !node.classification) return "pending";
  return node.classification === "likely_effective"
    ? "effective"
    : node.classification === "likely_ineffective"
      ? "ineffective"
      : "uncertain";
}

function scoreLabel(node: AnalysisNode): string {
  if (node.status !== "complete" || typeof node.score !== "number") {
    return node.status === "failed" ? "Failed" : "Processing…";
  }
  return `${Math.round(node.score * 100)}% response`;
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function cssEscape(value: string): string {
  return value.replace(/["\\]/g, "\\$&");
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="9" cy="9" r="6" />
      <path d="m14 14 4 4" />
    </svg>
  );
}
