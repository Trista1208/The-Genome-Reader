import { GenomeReaderApp } from "@/components/genome-reader";

export default function AnalyzePage() {
  return <GenomeReaderApp convexEnabled={Boolean(process.env.NEXT_PUBLIC_CONVEX_URL)} />;
}
