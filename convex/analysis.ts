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
const detectedGeneValidator = v.object({
  symbol: v.string(),
  name: v.string(),
  tier: v.string(),
  confidence: v.string(),
});

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
    noCall: v.boolean(),
    detectedGenes: v.array(detectedGeneValidator),
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

      // The Genome Firewall inference service: FASTA -> AMRFinderPlus -> model.
      // See inference/serve.py. Deployed by the team; URL set in the Convex dashboard.
      const endpoint = process.env.INFERENCE_API_URL ?? process.env.HUGGINGFACE_ENDPOINT_URL;
      const token = process.env.INFERENCE_API_TOKEN ?? process.env.HUGGINGFACE_TOKEN;
      if (!endpoint) {
        throw new Error("The inference service is not configured (set INFERENCE_API_URL).");
      }

      const response = await fetch(new URL("/predict", endpoint), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ fasta, antibiotic: args.antibiotic }),
      });

      if (!response.ok) {
        const details = (await response.text()).slice(0, 240);
        throw new Error(`Inference service returned ${response.status}${details ? `: ${details}` : ""}`);
      }

      const payload: unknown = await response.json();
      const normalized = parseServiceResponse(payload);
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

// The service already speaks the app's contract (score = probability effective,
// classification decided by the model's no-call bands, evidence from detected
// genes). We validate the numbers and trust the verdict.
function parseServiceResponse(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    throw new Error("The inference service returned an unsupported response shape.");
  }
  const output = payload as Record<string, unknown>;

  const score = readProbability(output.score);
  const confidence = readProbability(
    typeof output.confidence === "number" ? output.confidence : Math.max(score, 1 - score),
  );

  const classification = output.classification;
  if (
    classification !== "likely_effective" &&
    classification !== "uncertain" &&
    classification !== "likely_ineffective"
  ) {
    throw new Error("The inference service returned an invalid classification.");
  }

  const evidence =
    output.evidence === "known_marker" || output.evidence === "no_known_signal"
      ? output.evidence
      : "statistical_association";

  const modelVersion =
    typeof output.modelVersion === "string"
      ? output.modelVersion
      : typeof output.model_version === "string"
        ? output.model_version
        : "GFR-ECOLI";

  const noCall = typeof output.noCall === "boolean" ? output.noCall : classification === "uncertain";

  const detectedGenes = Array.isArray(output.detectedGenes)
    ? output.detectedGenes.slice(0, 50).map((g) => {
        const gene = (g ?? {}) as Record<string, unknown>;
        return {
          symbol: String(gene.symbol ?? ""),
          name: String(gene.name ?? ""),
          tier: String(gene.tier ?? ""),
          confidence: String(gene.confidence ?? ""),
        };
      })
    : [];

  return { score, confidence, classification, evidence, modelVersion, noCall, detectedGenes } as const;
}

function readProbability(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error("The inference service did not return a probability between 0 and 1.");
  }
  return value;
}
