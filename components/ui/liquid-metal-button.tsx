"use client";

import { liquidMetalFragmentShader, ShaderMount } from "@paper-design/shaders";
import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

interface LiquidMetalButtonProps {
  label?: string;
  onClick?: () => void;
  viewMode?: "text" | "icon";
}

export function LiquidMetalButton({
  label = "Get Started",
  onClick,
  viewMode = "text",
}: LiquidMetalButtonProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isPressed, setIsPressed] = useState(false);
  const [ripples, setRipples] = useState<Array<{ x: number; y: number; id: number }>>([]);
  const shaderRef = useRef<HTMLDivElement>(null);
  const shaderMount = useRef<ShaderMount | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const rippleId = useRef(0);

  const dimensions = useMemo(() => viewMode === "icon"
    ? { width: 46, height: 46, innerWidth: 42, innerHeight: 42 }
    : { width: 220, height: 58, innerWidth: 216, innerHeight: 54 }, [viewMode]);

  useEffect(() => {
    if (!shaderRef.current) return;

    shaderMount.current = new ShaderMount(
      shaderRef.current,
      liquidMetalFragmentShader,
      {
        u_colorBack: [0.67, 0.67, 0.68, 1],
        u_colorTint: [1, 1, 1, 1],
        u_image: undefined,
        u_isImage: false,
        u_repetition: 4,
        u_softness: 0.5,
        u_shiftRed: 0.3,
        u_shiftBlue: 0.3,
        u_distortion: 0,
        u_contour: 0,
        u_angle: 45,
        u_scale: 8,
        u_shape: 1,
        u_fit: 1,
        u_rotation: 0,
        u_originX: 0.5,
        u_originY: 0.5,
        u_offsetX: 0.1,
        u_offsetY: -0.1,
        u_worldWidth: 0,
        u_worldHeight: 0,
      },
      undefined,
      0.6,
      0,
      1,
      400_000,
    );

    return () => {
      shaderMount.current?.dispose();
      shaderMount.current = null;
    };
  }, []);

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    shaderMount.current?.setSpeed(2.4);
    window.setTimeout(() => shaderMount.current?.setSpeed(isHovered ? 1 : 0.6), 300);

    if (buttonRef.current) {
      const bounds = buttonRef.current.getBoundingClientRect();
      const ripple = {
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
        id: rippleId.current++,
      };
      setRipples((current) => [...current, ripple]);
      window.setTimeout(() => {
        setRipples((current) => current.filter((item) => item.id !== ripple.id));
      }, 600);
    }

    onClick?.();
  };

  return (
    <div className="liquid-button-shell" style={{ width: dimensions.width, height: dimensions.height }}>
      <div className="liquid-button-label" aria-hidden="true">
        {viewMode === "icon" ? <Sparkles size={16} /> : <span>{label}</span>}
      </div>

      <div
        className={`liquid-button-core ${isPressed ? "is-pressed" : ""}`}
        style={{ width: dimensions.innerWidth, height: dimensions.innerHeight }}
      />

      <div className={`liquid-button-metal ${isHovered ? "is-hovered" : ""} ${isPressed ? "is-pressed" : ""}`}>
        <div ref={shaderRef} className="liquid-button-shader" />
      </div>

      <button
        ref={buttonRef}
        className="liquid-button-hitarea"
        type="button"
        aria-label={label}
        onClick={handleClick}
        onMouseEnter={() => { setIsHovered(true); shaderMount.current?.setSpeed(1); }}
        onMouseLeave={() => { setIsHovered(false); setIsPressed(false); shaderMount.current?.setSpeed(0.6); }}
        onMouseDown={() => setIsPressed(true)}
        onMouseUp={() => setIsPressed(false)}
      >
        {ripples.map((ripple) => (
          <span
            className="liquid-button-ripple"
            key={ripple.id}
            style={{ left: ripple.x, top: ripple.y }}
          />
        ))}
      </button>
    </div>
  );
}

export default LiquidMetalButton;
