import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // One record per client/patient a doctor runs genomes for. The unique business
  // key is `patientId` (a human MRN / identifier); analyses reference this table
  // via `analyses.patientRef` so a patient's history groups into the knowledge tree.
  patients: defineTable({
    patientId: v.string(),
    name: v.string(),
    dob: v.optional(v.string()),
    notes: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  })
    .index("by_patient_id", ["patientId"])
    .searchIndex("search_name", { searchField: "name" }),

  analyses: defineTable({
    storageId: v.id("_storage"),
    fileName: v.string(),
    fileSize: v.number(),
    antibiotic: v.string(),
    // Links the analysis to a patient. Optional so pre-existing rows stay valid.
    patientRef: v.optional(v.id("patients")),
    status: v.union(v.literal("processing"), v.literal("complete"), v.literal("failed")),
    createdAt: v.number(),
    completedAt: v.optional(v.number()),
    score: v.optional(v.number()),
    confidence: v.optional(v.number()),
    classification: v.optional(
      v.union(v.literal("likely_effective"), v.literal("uncertain"), v.literal("likely_ineffective")),
    ),
    evidence: v.optional(
      v.union(v.literal("known_marker"), v.literal("statistical_association"), v.literal("no_known_signal")),
    ),
    modelVersion: v.optional(v.string()),
    noCall: v.optional(v.boolean()),
    detectedGenes: v.optional(
      v.array(
        v.object({
          symbol: v.string(),
          name: v.string(),
          tier: v.string(),
          confidence: v.string(),
        }),
      ),
    ),
    sequenceLength: v.optional(v.number()),
    contigCount: v.optional(v.number()),
    error: v.optional(v.string()),
    // Concurrent AI-reviewer second opinion (convex/report.ts generateReport).
    report: v.optional(
      v.object({
        summary: v.string(),
        keyFindings: v.array(v.string()),
        independentVerdict: v.union(
          v.literal("likely_effective"),
          v.literal("uncertain"),
          v.literal("likely_ineffective"),
        ),
        agreement: v.union(v.literal("agree"), v.literal("partial"), v.literal("disagree")),
        reasoning: v.string(),
      }),
    ),
  })
    .index("by_created_at", ["createdAt"])
    .index("by_patient", ["patientRef"]),
});
