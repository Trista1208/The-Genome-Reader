"use node";

import OpenAI from "openai";
import { v } from "convex/values";
import { action } from "./_generated/server";
import { internal } from "./_generated/api";

// The AI "reviewer" subagent. It runs concurrently with the classifier result
// on the /analyze/run page: given the same FASTA-derived stats plus the
// classifier's own output (the extra datapoint), it writes a concise report,
// forms an independent verdict, and cross-checks whether the classifier agrees.
//
// Uses OpenAI gpt-4o-mini for a fast, concise second opinion. Requires
// OPENAI_API_KEY set in the Convex dashboard:
//   npx convex env set OPENAI_API_KEY sk-...

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

const REPORT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    summary: {
      type: "string",
      description: "One or two plain-language sentences a clinician can read at a glance.",
    },
    keyFindings: {
      type: "array",
      items: { type: "string" },
      description: "2-4 short bullet points linking detected genes to the drug's likely effect.",
    },
    independentVerdict: {
      type: "string",
      enum: ["likely_effective", "uncertain", "likely_ineffective"],
      description: "Your own verdict, reasoned from the genomic evidence.",
    },
    agreement: {
      type: "string",
      enum: ["agree", "partial", "disagree"],
      description: "How your verdict compares to the classifier's classification.",
    },
    reasoning: {
      type: "string",
      description: "Why you agree or disagree, referencing the detected resistance genes.",
    },
  },
  required: ["summary", "keyFindings", "independentVerdict", "agreement", "reasoning"],
} as const;

const SYSTEM_PROMPT = [
  "You are an independent antimicrobial-resistance (AMR) reviewer for E. coli genomes.",
  "A statistical classifier has already scored a genome for a specific antibiotic.",
  "Your job is to give a concise, fast, easy-to-read second opinion: summarise the",
  "situation in plain language, reason over the detected resistance genes, state your",
  "own verdict, and say whether you agree with the classifier.",
  "Be direct and brief. Ground every claim in the provided data — do not invent genes",
  "or findings. This is research decision support only, never an autonomous treatment",
  "recommendation.",
].join(" ");

export const generateReport = action({
  args: {
    analysisId: v.optional(v.id("analyses")),
    antibiotic: v.string(),
    fileName: v.string(),
    score: v.number(),
    confidence: v.number(),
    classification: classificationValidator,
    evidence: evidenceValidator,
    detectedGenes: v.optional(v.array(detectedGeneValidator)),
    sequenceLength: v.optional(v.number()),
    contigCount: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      throw new Error("The report service is not configured (set OPENAI_API_KEY).");
    }

    const client = new OpenAI({ apiKey });

    const genes =
      args.detectedGenes && args.detectedGenes.length > 0
        ? args.detectedGenes
            .map((g) => `${g.symbol} (${g.name || "unnamed"}, tier ${g.tier}, ${g.confidence})`)
            .join("; ")
        : "none detected";

    const classifierBrief = [
      `Antibiotic: ${args.antibiotic}`,
      `Sequence: ${args.fileName}` +
        (args.sequenceLength ? `, ${args.sequenceLength} bases` : "") +
        (args.contigCount ? ` across ${args.contigCount} contigs` : ""),
      `Classifier verdict: ${args.classification}`,
      `Effectiveness score: ${Math.round(args.score * 100)}% probability the antibiotic works`,
      `Classifier confidence: ${Math.round(args.confidence * 100)}%`,
      `Evidence class: ${args.evidence}`,
      `Detected resistance genes: ${genes}`,
    ].join("\n");

    const completion = await client.chat.completions.create({
      model: "gpt-4o-mini",
      max_tokens: 1024,
      response_format: {
        type: "json_schema",
        json_schema: { name: "amr_review", strict: true, schema: REPORT_SCHEMA },
      },
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content:
            "Review this classifier result and produce your independent report.\n\n" +
            classifierBrief,
        },
      ],
    });

    const content = completion.choices[0]?.message.content;
    if (!content) {
      throw new Error("The report service returned an empty response.");
    }

    const report = JSON.parse(content) as {
      summary: string;
      keyFindings: string[];
      independentVerdict: "likely_effective" | "uncertain" | "likely_ineffective";
      agreement: "agree" | "partial" | "disagree";
      reasoning: string;
    };

    if (args.analysisId) {
      await ctx.runMutation(internal.analysis.markReport, {
        analysisId: args.analysisId,
        report,
      });
    }

    return report;
  },
});
