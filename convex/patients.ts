import { v } from "convex/values";
import { internalMutation, query, type QueryCtx } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";

// Patient (client) records and the read paths that power the knowledge tree —
// a node graph of Patient -> analysis runs -> report — plus a fast search box.

export const upsertPatient = internalMutation({
  args: {
    patientId: v.string(),
    name: v.string(),
    dob: v.optional(v.string()),
    notes: v.optional(v.string()),
  },
  handler: async (ctx, { patientId, name, dob, notes }) => {
    const now = Date.now();
    const existing = await ctx.db
      .query("patients")
      .withIndex("by_patient_id", (q) => q.eq("patientId", patientId))
      .unique();

    if (existing) {
      await ctx.db.patch(existing._id, {
        name,
        // Only overwrite dob/notes when a new value is supplied.
        ...(dob !== undefined ? { dob } : {}),
        ...(notes !== undefined ? { notes } : {}),
        updatedAt: now,
      });
      return existing._id;
    }

    return ctx.db.insert("patients", { patientId, name, dob, notes, createdAt: now, updatedAt: now });
  },
});

// A trimmed analysis node for the graph — enough to render + color a node.
function toAnalysisNode(analysis: Doc<"analyses">) {
  return {
    _id: analysis._id,
    antibiotic: analysis.antibiotic,
    fileName: analysis.fileName,
    status: analysis.status,
    classification: analysis.classification,
    score: analysis.score,
    createdAt: analysis.createdAt,
  };
}

async function analysesForPatient(ctx: QueryCtx, patientRef: Id<"patients">) {
  const rows = await ctx.db
    .query("analyses")
    .withIndex("by_patient", (q) => q.eq("patientRef", patientRef))
    .collect();
  return rows.sort((a, b) => b.createdAt - a.createdAt).map(toAnalysisNode);
}

// The whole tree for the graph: every patient with their (newest-first) analyses.
export const knowledgeTree = query({
  args: {},
  handler: async (ctx) => {
    const patients = await ctx.db.query("patients").collect();
    patients.sort((a, b) => b.updatedAt - a.updatedAt);
    return Promise.all(
      patients.map(async (patient) => ({
        _id: patient._id,
        patientId: patient.patientId,
        name: patient.name,
        dob: patient.dob,
        notes: patient.notes,
        updatedAt: patient.updatedAt,
        analyses: await analysesForPatient(ctx, patient._id),
      })),
    );
  },
});

// Powers the "jump to node" search box: matches by name (full-text) or by
// patientId prefix. Returns the same node shape as knowledgeTree entries.
export const searchPatients = query({
  args: { term: v.string() },
  handler: async (ctx, { term }) => {
    const trimmed = term.trim();
    if (!trimmed) return [];

    const byName = await ctx.db
      .query("patients")
      .withSearchIndex("search_name", (q) => q.search("name", trimmed))
      .take(20);

    const matches = new Map<string, Doc<"patients">>();
    for (const p of byName) matches.set(p._id, p);

    // Also match on patientId prefix (search index only covers name).
    const lower = trimmed.toLowerCase();
    const all = await ctx.db.query("patients").collect();
    for (const p of all) {
      if (p.patientId.toLowerCase().includes(lower)) matches.set(p._id, p);
    }

    return Promise.all(
      [...matches.values()].map(async (patient) => ({
        _id: patient._id,
        patientId: patient.patientId,
        name: patient.name,
        dob: patient.dob,
        notes: patient.notes,
        updatedAt: patient.updatedAt,
        analyses: await analysesForPatient(ctx, patient._id),
      })),
    );
  },
});

// Full analysis row (incl. the AI report) for the detail panel.
export const getAnalysis = query({
  args: { analysisId: v.id("analyses") },
  handler: async (ctx, { analysisId }) => {
    const analysis = await ctx.db.get(analysisId);
    if (!analysis) return null;
    const patient = analysis.patientRef ? await ctx.db.get(analysis.patientRef) : null;
    return { analysis, patient };
  },
});
