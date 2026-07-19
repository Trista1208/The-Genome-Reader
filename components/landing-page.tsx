import Link from "next/link";
import { ShaderAnimation } from "@/components/ui/shader-lines";

export function LandingPage() {
  return (
    <main className="shader-landing">
      <ShaderAnimation />
      <div className="shader-landing-content">
        <div className="shader-landing-intro">
          <h1>BREAKPOINT</h1>
          <p>Genomic decision support that estimates whether an antibiotic is likely to work.</p>
        </div>
        <Link href="/analyze">GO TO CHECK <span>→</span></Link>
      </div>
    </main>
  );
}
