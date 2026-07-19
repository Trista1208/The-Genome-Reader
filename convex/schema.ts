import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  analyses: defineTable({
    storageId: v.id("_storage"),
    fileName: v.string(),
    fileSize: v.number(),
    antibiotic: v.string(),
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
    sequenceLength: v.optional(v.number()),
    contigCount: v.optional(v.number()),
    error: v.optional(v.string()),
  }).index("by_created_at", ["createdAt"]),
});
