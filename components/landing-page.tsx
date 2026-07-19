"use client";

import Link from "next/link";
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
                    <p className="white">
                        The answer is already in the DNA. Read a bacterial
                        genome and see which antibiotics are likely to work,
                        days before the lab can.
                    </p>
                </div>
                <LiquidMetalButton
                    label="Go to Check"
                    onClick={() => router.push("/analyze")}
                />
                <Link className="landing-records-link" href="/knowledge">
                    Browse patient records →
                </Link>
            </div>
        </main>
    );
}
