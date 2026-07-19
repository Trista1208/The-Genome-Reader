import Link from "next/link";
import { AsciiRenderer } from "@/components/ui/ascii-renderer";

export function AsciiLanding() {
  return (
    <main className="landing-page">
      <div className="landing-grid" aria-hidden="true" />
      <header className="landing-header">
        <span>GENOME READER / MODULE 01</span>
        <span>RESEARCH DECISION SUPPORT</span>
      </header>

      <section className="ascii-stage" aria-label="Animated ASCII DNA double helix">
        <span className="stage-corner corner-nw" aria-hidden="true" />
        <span className="stage-corner corner-ne" aria-hidden="true" />
        <span className="stage-corner corner-sw" aria-hidden="true" />
        <span className="stage-corner corner-se" aria-hidden="true" />
        <AsciiRenderer />
        <div className="stage-axis" aria-hidden="true"><span>Y+</span><i /><span>Y−</span></div>
      </section>

      <footer className="landing-footer">
        <div className="landing-copy">
          <p>GENOMIC INFERENCE SYSTEM</p>
          <h1>ANTIBIOTIC<br />CHECK</h1>
        </div>
        <div className="landing-action">
          <p>Upload an assembled bacterial genome and estimate antibiotic response through a calibrated model endpoint.</p>
          <Link href="/analyze">OPEN WORKBOOK <span>→</span></Link>
        </div>
      </footer>
    </main>
  );
}
