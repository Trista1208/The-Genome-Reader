"use client";

import { useRouter } from "next/navigation";
import { ShaderAnimation } from "@/components/ui/shader-lines";
import { LiquidMetalButton } from "@/components/ui/liquid-metal-button";

export function LandingPage() {
  const router = useRouter();

  return (
    <main className="shader-landing">
      <ShaderAnimation />
      <div className="shader-landing-content">
        <div className="shader-landing-intro">
          <h1>BREAKPOINT</h1>
          <p>Genomic decision support that estimates whether an antibiotic is likely to work.</p>
        </div>
        <LiquidMetalButton label="Go to Check" onClick={() => router.push("/analyze")} />
      </div>
    </main>
  );
}
