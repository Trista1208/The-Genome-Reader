import { KnowledgeTree } from "@/components/knowledge-tree";

export default function KnowledgePage() {
  return <KnowledgeTree convexEnabled={Boolean(process.env.NEXT_PUBLIC_CONVEX_URL)} />;
}
