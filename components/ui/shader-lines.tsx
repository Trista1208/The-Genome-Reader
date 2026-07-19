"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

const VERTEX_SHADER = `
  void main() {
    gl_Position = vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;

  uniform vec2 resolution;
  uniform float time;

  float random(float x) {
    return fract(sin(x) * 1e4);
  }

  float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
  }

  void main() {
    vec2 uv = (gl_FragCoord.xy * 2.0 - resolution.xy) / min(resolution.x, resolution.y);
    vec2 mosaicScale = vec2(4.0, 2.0);
    vec2 screenSize = vec2(256.0);
    uv.x = floor(uv.x * screenSize.x / mosaicScale.x) / (screenSize.x / mosaicScale.x);
    uv.y = floor(uv.y * screenSize.y / mosaicScale.y) / (screenSize.y / mosaicScale.y);

    float t = time * 0.06 + random(uv.x) * 0.4;
    float lineWidth = 0.0008;
    vec3 color = vec3(0.0);

    for (int channel = 0; channel < 3; channel++) {
      for (int ring = 0; ring < 5; ring++) {
        float index = float(ring);
        color[channel] += lineWidth * index * index /
          abs(fract(t - 0.01 * float(channel) + index * 0.01) - length(uv));
      }
    }

    gl_FragColor = vec4(color.b, color.g, color.r, 1.0);
  }
`;

export function ShaderAnimation() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const camera = new THREE.Camera();
    camera.position.z = 1;
    const scene = new THREE.Scene();
    const geometry = new THREE.PlaneGeometry(2, 2);
    const uniforms = {
      time: { value: 1 },
      resolution: { value: new THREE.Vector2() },
    };
    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
    });
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.domElement.setAttribute("aria-hidden", "true");
    container.replaceChildren(renderer.domElement);

    const resize = () => {
      const bounds = container.getBoundingClientRect();
      renderer.setSize(bounds.width, bounds.height, false);
      uniforms.resolution.value.set(renderer.domElement.width, renderer.domElement.height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let animationId = 0;
    let lastFrame = performance.now();

    const render = (now: number) => {
      const delta = Math.min((now - lastFrame) / 16.667, 3);
      lastFrame = now;
      uniforms.time.value += 0.05 * delta;
      renderer.render(scene, camera);
      animationId = requestAnimationFrame(render);
    };

    if (reducedMotion) renderer.render(scene, camera);
    else animationId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationId);
      observer.disconnect();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={containerRef} className="shader-lines" aria-hidden="true" />;
}

export default ShaderAnimation;
