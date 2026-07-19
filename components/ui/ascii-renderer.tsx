"use client";

import { useEffect, useMemo, useRef } from "react";
import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { AsciiEffect } from "three/examples/jsm/effects/AsciiEffect.js";
import * as THREE from "three";

export function AsciiRenderer() {
  return (
    <div className="ascii-renderer" aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 11.5], fov: 46 }}
        dpr={[1, 1.35]}
        gl={{ antialias: false, alpha: false }}
      >
        <color attach="background" args={["#050505"]} />
        <ambientLight intensity={0.7} />
        <pointLight position={[6, 7, 8]} intensity={18} distance={24} />
        <directionalLight position={[-6, -4, 5]} intensity={1.8} />
        <DnaHelix />
        <OrbitControls enablePan={false} enableZoom={false} enableDamping dampingFactor={0.08} />
        <Renderer />
      </Canvas>
    </div>
  );
}

function DnaHelix() {
  const groupRef = useRef<THREE.Group>(null);
  const geometry = useMemo(() => {
    const pointsA: THREE.Vector3[] = [];
    const pointsB: THREE.Vector3[] = [];
    const segments = 76;

    for (let index = 0; index < segments; index += 1) {
      const progress = index / (segments - 1);
      const angle = index * 0.43;
      const y = (progress - 0.5) * 7.8;
      pointsA.push(new THREE.Vector3(Math.cos(angle) * 1.18, y, Math.sin(angle) * 1.18));
      pointsB.push(new THREE.Vector3(Math.cos(angle + Math.PI) * 1.18, y, Math.sin(angle + Math.PI) * 1.18));
    }

    return {
      pointsA,
      pointsB,
      strandA: new THREE.CatmullRomCurve3(pointsA),
      strandB: new THREE.CatmullRomCurve3(pointsB),
      rungIndices: Array.from({ length: 24 }, (_, index) => index * 3 + 3),
    };
  }, []);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.y += delta * 0.22;
    groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.34) * 0.08;
  });

  return (
    <group ref={groupRef} scale={0.82} rotation={[0, 0, -0.08]}>
      <mesh>
        <tubeGeometry args={[geometry.strandA, 180, 0.105, 7, false]} />
        <meshStandardMaterial color="#f4f4ef" roughness={0.38} metalness={0.52} />
      </mesh>
      <mesh>
        <tubeGeometry args={[geometry.strandB, 180, 0.105, 7, false]} />
        <meshStandardMaterial color="#c8c8c2" roughness={0.42} metalness={0.48} />
      </mesh>

      {geometry.rungIndices.map((index) => (
        <Rung key={index} from={geometry.pointsA[index]} to={geometry.pointsB[index]} />
      ))}

      {geometry.pointsA.filter((_, index) => index % 3 === 0).map((point, index) => (
        <mesh key={`a-${index}`} position={point}>
          <sphereGeometry args={[0.15, 8, 8]} />
          <meshStandardMaterial color="#ffffff" roughness={0.32} metalness={0.6} />
        </mesh>
      ))}
      {geometry.pointsB.filter((_, index) => index % 3 === 0).map((point, index) => (
        <mesh key={`b-${index}`} position={point}>
          <sphereGeometry args={[0.15, 8, 8]} />
          <meshStandardMaterial color="#d8d8d2" roughness={0.4} metalness={0.48} />
        </mesh>
      ))}
    </group>
  );
}

function Rung({ from, to }: { from: THREE.Vector3; to: THREE.Vector3 }) {
  const transform = useMemo(() => {
    const direction = new THREE.Vector3().subVectors(to, from);
    const midpoint = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5);
    const quaternion = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      direction.clone().normalize(),
    );
    return { midpoint, quaternion, length: direction.length() };
  }, [from, to]);

  return (
    <mesh position={transform.midpoint} quaternion={transform.quaternion}>
      <cylinderGeometry args={[0.035, 0.035, transform.length, 6]} />
      <meshStandardMaterial color="#969692" roughness={0.65} metalness={0.2} />
    </mesh>
  );
}

function Renderer() {
  const { gl, scene, camera, size } = useThree();
  const effectRef = useRef<AsciiEffect | null>(null);

  useEffect(() => {
    const effect = new AsciiEffect(gl, " .,:;i1tfLCG08@", { invert: true });
    const container = gl.domElement.parentElement;
    if (!container) return;

    effect.domElement.className = "ascii-effect";
    effect.domElement.style.position = "absolute";
    effect.domElement.style.inset = "0";
    effect.domElement.style.color = "#e8e8e3";
    effect.domElement.style.backgroundColor = "#050505";
    effect.domElement.style.pointerEvents = "none";
    effect.domElement.style.overflow = "hidden";
    effect.domElement.style.zIndex = "2";
    effect.setSize(size.width, size.height);

    container.appendChild(effect.domElement);
    effectRef.current = effect;

    return () => {
      effectRef.current = null;
      if (effect.domElement.parentNode === container) container.removeChild(effect.domElement);
    };
  }, [camera, gl, scene, size.height, size.width]);

  useFrame(() => effectRef.current?.render(scene, camera), 1);
  return null;
}

export default AsciiRenderer;
