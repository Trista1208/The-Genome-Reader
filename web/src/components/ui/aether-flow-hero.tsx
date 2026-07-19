"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface AetherFlowHeroProps {
  badgeText?: string;
  title?: string;
  subtitle?: string;
  ctaText?: string;
  className?: string;
}

const AetherFlowHero = ({
  badgeText = 'AI Defense Against Superbugs',
  title = 'Genome Firewall',
  subtitle = 'Per-antibiotic verdicts from one reconstructed bacterial genome — likely to fail, likely to work, or an honest no-call. Calibrated confidence, never a treatment decision.',
  ctaText = 'Analyze a Genome',
  className,
}: AetherFlowHeroProps) => {
    const canvasRef = React.useRef<HTMLCanvasElement>(null);

    React.useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        const cv: HTMLCanvasElement = canvas;

        let animationFrameId: number;
        let particles: Particle[] = [];
        const mouse: { x: number | null; y: number | null; radius: number } = { x: null, y: null, radius: 200 };

        class Particle {
            x: number;
            y: number;
            directionX: number;
            directionY: number;
            size: number;
            color: string;

            constructor(x: number, y: number, directionX: number, directionY: number, size: number, color: string) {
                this.x = x;
                this.y = y;
                this.directionX = directionX;
                this.directionY = directionY;
                this.size = size;
                this.color = color;
            }

            draw() {
                if (!ctx) return;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
                ctx.fillStyle = this.color;
                ctx.fill();
            }

            update() {
                if (this.x > cv.width || this.x < 0) {
                    this.directionX = -this.directionX;
                }
                if (this.y > cv.height || this.y < 0) {
                    this.directionY = -this.directionY;
                }

                if (mouse.x !== null && mouse.y !== null) {
                    const dx = mouse.x - this.x;
                    const dy = mouse.y - this.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    if (distance < mouse.radius + this.size) {
                        const forceDirectionX = dx / distance;
                        const forceDirectionY = dy / distance;
                        const force = (mouse.radius - distance) / mouse.radius;
                        this.x -= forceDirectionX * force * 5;
                        this.y -= forceDirectionY * force * 5;
                    }
                }

                this.x += this.directionX;
                this.y += this.directionY;
                this.draw();
            }
        }

        function init() {
            particles = [];
            const numberOfParticles = (cv.height * cv.width) / 9000;
            for (let i = 0; i < numberOfParticles; i++) {
                const size = (Math.random() * 2) + 1;
                const x = (Math.random() * ((innerWidth - size * 2) - (size * 2)) + size * 2);
                const y = (Math.random() * ((innerHeight - size * 2) - (size * 2)) + size * 2);
                const directionX = (Math.random() * 0.4) - 0.2;
                const directionY = (Math.random() * 0.4) - 0.2;
                // Genome Firewall palette: warm paper with rare signal-red sparks
                const color = Math.random() < 0.08
                    ? 'rgba(220, 38, 38, 0.9)'
                    : 'rgba(247, 245, 242, 0.75)';
                particles.push(new Particle(x, y, directionX, directionY, size, color));
            }
        }

        const resizeCanvas = () => {
            cv.width = window.innerWidth;
            cv.height = window.innerHeight;
            init();
        };
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        const connect = () => {
            if (!ctx) return;
            let opacityValue = 1;
            for (let a = 0; a < particles.length; a++) {
                for (let b = a; b < particles.length; b++) {
                    const distance = ((particles[a].x - particles[b].x) * (particles[a].x - particles[b].x))
                        + ((particles[a].y - particles[b].y) * (particles[a].y - particles[b].y));

                    if (distance < (cv.width / 7) * (cv.height / 7)) {
                        opacityValue = 1 - (distance / 20000);

                        const dx_mouse_a = particles[a].x - (mouse.x ?? 0);
                        const dy_mouse_a = particles[a].y - (mouse.y ?? 0);
                        const distance_mouse_a = Math.sqrt(dx_mouse_a * dx_mouse_a + dy_mouse_a * dy_mouse_a);

                        if (mouse.x && distance_mouse_a < mouse.radius) {
                            ctx.strokeStyle = `rgba(255, 255, 255, ${opacityValue})`;
                        } else {
                            ctx.strokeStyle = `rgba(201, 194, 186, ${opacityValue * 0.7})`;
                        }

                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(particles[a].x, particles[a].y);
                        ctx.lineTo(particles[b].x, particles[b].y);
                        ctx.stroke();
                    }
                }
            }
        };

        const animate = () => {
            animationFrameId = requestAnimationFrame(animate);
            // warm charcoal, not pure black
            ctx.fillStyle = '#14110f';
            ctx.fillRect(0, 0, innerWidth, innerHeight);

            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
            }
            connect();
        };

        const handleMouseMove = (event: MouseEvent) => {
            mouse.x = event.clientX;
            mouse.y = event.clientY;
        };

        const handleMouseOut = () => {
            mouse.x = null;
            mouse.y = null;
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseout', handleMouseOut);

        init();
        animate();

        return () => {
            window.removeEventListener('resize', resizeCanvas);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseout', handleMouseOut);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    const fadeUpVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: (i: number) => ({
            opacity: 1,
            y: 0,
            transition: {
                delay: i * 0.2 + 0.5,
                duration: 0.8,
                ease: 'easeInOut' as const,
            },
        }),
    };

    return (
        <div className={cn('relative h-screen w-full flex flex-col items-center justify-center overflow-hidden', className)}>
            <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full" />

            <div className="relative z-10 text-center p-6">
                <motion.div
                    custom={0}
                    variants={fadeUpVariants}
                    initial="hidden"
                    animate="visible"
                    className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-red-500/10 border border-red-500/25 mb-6 backdrop-blur-sm"
                >
                    <Zap className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-neutral-300">
                        {badgeText}
                    </span>
                </motion.div>

                <motion.h1
                    custom={1}
                    variants={fadeUpVariants}
                    initial="hidden"
                    animate="visible"
                    className="text-5xl md:text-8xl font-bold tracking-tighter mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-neutral-500"
                >
                    {title}
                </motion.h1>

                <motion.p
                    custom={2}
                    variants={fadeUpVariants}
                    initial="hidden"
                    animate="visible"
                    className="max-w-2xl mx-auto text-lg text-neutral-400 mb-10"
                >
                    {subtitle}
                </motion.p>

                <motion.div
                    custom={3}
                    variants={fadeUpVariants}
                    initial="hidden"
                    animate="visible"
                >
                    <button className="px-8 py-4 bg-red-600 text-white font-semibold rounded-lg shadow-lg hover:bg-red-500 transition-colors duration-300 flex items-center gap-2 mx-auto">
                        {ctaText}
                        <ArrowRight className="h-5 w-5" />
                    </button>
                </motion.div>
            </div>
        </div>
    );
};

export default AetherFlowHero;
