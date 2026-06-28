"use client";

import { CutButton } from "@/components/cut-button";
import { fadeInUp, reducedMotionVariants, softEase, useReducedMotion } from "@/lib/motion";
import { motion, type Variants } from "motion/react";
import type { ReactNode } from "react";

const container: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12, delayChildren: 0.35 },
  },
};

export function Hero(): ReactNode {
  const prefersReducedMotion = useReducedMotion();
  const item = prefersReducedMotion ? reducedMotionVariants : fadeInUp;
  const itemTransition = prefersReducedMotion
    ? { duration: 0.01 }
    : { duration: 0.7, ease: softEase };

  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% -5%, color-mix(in srgb, var(--foreground) 5%, transparent), transparent 70%)",
        }}
      />

      <div className="mx-auto max-w-[1440px] px-5 sm:px-8 lg:px-10">
        <motion.div
          variants={container}
          initial="hidden"
          animate="visible"
          className="relative mx-auto flex max-w-2xl flex-col items-center pb-12 pt-32 text-center sm:pt-40"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-1/2 -z-[1] h-[150%] w-[160%] -translate-x-1/2 -translate-y-1/2"
            style={{
              background:
                "radial-gradient(ellipse at center, var(--background) 0%, color-mix(in srgb, var(--background) 78%, transparent) 45%, transparent 72%)",
            }}
          />

          <motion.h1
            variants={item}
            transition={itemTransition}
            className="text-balance font-serif text-4xl font-normal leading-[1.1] tracking-[-0.01em] sm:text-5xl lg:text-[3.5rem]"
          >
            Govern Autonomous{" "}
            <span className="font-sans font-medium tracking-tight">
              Execution
            </span>
          </motion.h1>

          <motion.p
            variants={item}
            transition={itemTransition}
            className="mt-4 max-w-xl text-balance text-[15px] leading-relaxed text-muted-foreground sm:text-base"
          >
            CompliAGL is the AI Execution Governance Platform that governs autonomous systems through deterministic decision-making and machine-verifiable proof. Powered by CompliLedger Proof Infrastructure.
          </motion.p>

          <motion.div
            variants={item}
            transition={itemTransition}
            className="mt-7 flex items-center justify-center gap-3"
          >
            <CutButton variant="solid" href="#portal-demo">
              See the Platform
            </CutButton>
            <CutButton variant="outline" href="#pricing">
              Explore Use Cases
            </CutButton>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
