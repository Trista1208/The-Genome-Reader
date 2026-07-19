import { GenomeAnalysisRunApp } from "@/components/genome-reader";

export default function AnalyzeRunPage() {
  return <GenomeAnalysisRunApp convexEnabled={Boolean(process.env.NEXT_PUBLIC_CONVEX_URL)} />;
}
