import { GenomeAnalysisSessionProvider } from "@/components/genome-analysis-session";

export default function AnalyzeLayout({ children }: { children: React.ReactNode }) {
  return <GenomeAnalysisSessionProvider>{children}</GenomeAnalysisSessionProvider>;
}
