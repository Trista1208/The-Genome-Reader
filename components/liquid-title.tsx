"use client";

import { useEffect, useState } from "react";
import LiquidMetal from "@/components/ui/liquid-metal";

const TITLE = "BREAKPOINT";

export function LiquidTitle() {
  const [mask, setMask] = useState("");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [shaderReady, setShaderReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let readyTimer: number | undefined;

    const createMask = async () => {
      await document.fonts.ready;
      if (cancelled) return;

      const canvas = document.createElement("canvas");
      canvas.width = 1800;
      canvas.height = 180;
      const context = canvas.getContext("2d");
      if (!context) return;

      const panchang = getComputedStyle(document.documentElement)
        .getPropertyValue("--font-panchang")
        .trim() || "sans-serif";

      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = "#ffffff";
      context.font = `700 116px ${panchang}`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(TITLE, canvas.width / 2, canvas.height / 2 + 4, 1720);
      setMask(canvas.toDataURL("image/png"));

      const webGlCanvas = document.createElement("canvas");
      const hasWebGl = Boolean(webGlCanvas.getContext("webgl2") || webGlCanvas.getContext("webgl"));
      if (hasWebGl) {
        readyTimer = window.setTimeout(() => {
          if (!cancelled) setShaderReady(true);
        }, 1_100);
      }
    };

    const motionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setReducedMotion(motionMedia.matches);
    updateMotion();
    motionMedia.addEventListener("change", updateMotion);
    void createMask();

    return () => {
      cancelled = true;
      if (readyTimer) window.clearTimeout(readyTimer);
      motionMedia.removeEventListener("change", updateMotion);
    };
  }, []);

  return (
    <h1 className="liquid-title">
      <span className={`liquid-title-fallback ${shaderReady ? "is-processed" : ""}`} aria-hidden="true">{TITLE}</span>
      {mask ? (
        <LiquidMetal
          aria-hidden="true"
          className="liquid-title-shader"
          image={mask}
          colorBack="#00000000"
          colorTint="#ffffff"
          shape="none"
          repetition={2.8}
          softness={0.16}
          shiftRed={0}
          shiftBlue={0}
          distortion={0.12}
          contour={0.58}
          angle={72}
          speed={reducedMotion ? 0 : 0.42}
          scale={1}
          fit="contain"
          maxPixelCount={1_200_000}
        />
      ) : null}
      <span className="sr-only">{TITLE}</span>
    </h1>
  );
}
