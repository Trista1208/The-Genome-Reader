import { GenomeReaderApp } from "@/components/genome-reader";

export default function Home() {
  return <GenomeReaderApp convexEnabled={Boolean(process.env.NEXT_PUBLIC_CONVEX_URL)} />;
}
