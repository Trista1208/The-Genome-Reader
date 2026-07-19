import { v } from "convex/values";
import { action, internalMutation } from "./_generated/server";
import { internal } from "./_generated/api";

const classificationValidator = v.union(
  v.literal("likely_effective"),
  v.literal("uncertain"),
  v.literal("likely_ineffective"),
);
const evidenceValidator = v.union(
  v.literal("known_marker"),
  v.literal("statistical_association"),
  v.literal("no_known_signal"),
);

export const createPending = internalMutation({
  args: {
    storageId: v.id("_storage"),
    fileName: v.string(),
    fileSize: v.number(),
    antibiotic: v.string(),
  },
  handler: async (ctx, args) => ctx.db.insert("analyses", {
    ...args,
    status: "processing",
    createdAt: Date.now(),
  }),
});

export const markComplete = internalMutation({
  args: {
    analysisId: v.id("analyses"),
    score: v.number(),
    confidence: v.number(),
    classification: classificationValidator,
    evidence: evidenceValidator,
    modelVersion: v.string(),
    sequenceLength: v.number(),
    contigCount: v.number(),
  },
  handler: async (ctx, { analysisId, ...result }) => ctx.db.patch(analysisId, {
    ...result,
    status: "complete",
    completedAt: Date.now(),
  }),
});

export const markFailed = internalMutation({
  args: { analysisId: v.id("analyses"), error: v.string() },
  handler: async (ctx, { analysisId, error }) => ctx.db.patch(analysisId, {
    status: "failed",
    error,
    completedAt: Date.now(),
  }),
});

export const runInference = action({
  args: {
    storageId: v.id("_storage"),
    fileName: v.string(),
    fileSize: v.number(),
    antibiotic: v.string(),
  },
  handler: async (ctx, args) => {
    const analysisId = await ctx.runMutation(internal.analysis.createPending, args);

    try {
      const file = await ctx.storage.get(args.storageId);
      if (!file) throw new Error("The uploaded sequence is no longer available.");
      const fasta = await file.text();
      const { sequenceLength, contigCount } = inspectFasta(fasta);

      const endpoint = process.env.HUGGINGFACE_ENDPOINT_URL;
      const token = process.env.HUGGINGFACE_TOKEN;
      if (!endpoint || !token) {
        throw new Error("The Hugging Face inference endpoint is not configured.");
      }

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          inputs: { fasta, antibiotic: args.antibiotic },
          options: { wait_for_model: true },
        }),
      });

      if (!response.ok) {
        const details = (await response.text()).slice(0, 240);
        throw new Error(`Inference endpoint returned ${response.status}${details ? `: ${details}` : ""}`);
      }

      const payload: unknown = await response.json();
      const normalized = normalizeModelResponse(payload);
      const result = { ...normalized, sequenceLength, contigCount };

      await ctx.runMutation(internal.analysis.markComplete, { analysisId, ...result });
      return { analysisId, ...result };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown inference failure";
      await ctx.runMutation(internal.analysis.markFailed, { analysisId, error: message });
      throw new Error(message);
    }
  },
});

function inspectFasta(fasta: string) {
  const lines = fasta.split(/\r?\n/);
  const contigCount = lines.filter((line) => line.trim().startsWith(">")).length;
  const sequence = lines
    .filter((line) => !line.trim().startsWith(">"))
    .join("")
    .replace(/\s|N|-/gi, "");
  if (!contigCount || sequence.length < 20) throw new Error("The uploaded FASTA is malformed or empty.");
  return { sequenceLength: sequence.length, contigCount };
}

function normalizeModelResponse(payload: unknown) {
  const record = Array.isArray(payload) ? payload[0] : payload;
  if (!record || typeof record !== "object") throw new Error("The model returned an unsupported response shape.");
  const output = record as Record<string, unknown>;
  const score = readProbability(output.score ?? output.probability ?? output.effectiveness_score);
  const confidence = readProbability(output.confidence ?? Math.max(score, 1 - score));
  const classification = score >= 0.65
    ? "likely_effective"
    : score <= 0.35
      ? "likely_ineffective"
      : "uncertain";
  const requestedEvidence = output.evidence;
  const evidence = requestedEvidence === "known_marker" || requestedEvidence === "no_known_signal"
    ? requestedEvidence
    : "statistical_association";
  const modelVersion = typeof output.model_version === "string" ? output.model_version : "HF-ENDPOINT-UNVERSIONED";

  return { score, confidence, classification, evidence, modelVersion } as const;
}

function readProbability(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error("The model response did not include a probability between 0 and 1.");
  }
  return value;
}
