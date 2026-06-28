"use client";

import AsciiWaves from "@/components/ascii-waves";
import { CutButton } from "@/components/cut-button";
import { softEase, useReducedMotion } from "@/lib/motion";
import { motion, type Variants } from "motion/react";
import { useTheme } from "next-themes";
import { useSyncExternalStore, type ReactNode } from "react";

function useIsMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
}

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};

const staticContainer: Variants = { hidden: {}, visible: {} };

const item: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export function FinalCta(): ReactNode {
  const mounted = useIsMounted();
  const { resolvedTheme } = useTheme();
  const prefersReducedMotion = useReducedMotion();

  const isDark = resolvedTheme === "dark";
  const color = isDark ? "#ffffff" : "#0a0a0a";

  const hMask =
    "linear-gradient(to right, transparent 0%, black 13%, black 27%, transparent 43%, transparent 57%, black 73%, black 87%, transparent 100%)";
  const vMask =
    "linear-gradient(to bottom, transparent 0%, black 18%, black 82%, transparent 100%)";

  const itemTransition = prefersReducedMotion
    ? { duration: 0.01 }
    : { duration: 0.7, ease: softEase };

  return (
    <section className="relative overflow-hidden">
      {mounted && !prefersReducedMotion && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
        >
          <div className="mx-auto h-full max-w-[1440px]">
            <motion.div
              className="h-full w-full"
              initial={{ opacity: 0 }}
              whileInView={{ opacity: isDark ? 0.9 : 1 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 1.4, ease: softEase }}
              style={{
                maskImage: vMask,
                WebkitMaskImage: vMask,
                filter: isDark
                  ? "brightness(1.3)"
                  : "saturate(2.6) contrast(1.35)",
              }}
            >
              <div
                className="h-full w-full"
                style={{ maskImage: hMask, WebkitMaskImage: hMask }}
              >
                <AsciiWaves
                  color={color}
                  intensity={0}
                  elementSize={12}
                  videoUrl="/sample-video-2.mp4"
                  noiseScale={25}
                  hasCursorInteraction={false}
                />
              </div>
            </motion.div>
          </div>
        </div>
      )}

      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -z-[1] h-[130%] w-[70%] -translate-x-1/2 -translate-y-1/2"
        style={{
          background:
            "radial-gradient(ellipse at center, var(--background) 0%, color-mix(in srgb, var(--background) 70%, transparent) 50%, transparent 78%)",
        }}
      />

      <div className="mx-auto max-w-[1440px] px-5 sm:px-8 lg:px-10">
        <motion.div
          variants={prefersReducedMotion ? staticContainer : container}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-80px" }}
          className="mx-auto flex max-w-2xl flex-col items-center py-28 text-center sm:py-36 lg:py-44"
        >
          <motion.h2
            variants={item}
            transition={itemTransition}
            className="text-balance font-serif text-4xl font-normal leading-[1.08] tracking-[-0.01em] sm:text-5xl lg:text-[3.75rem]"
          >
            Ready to govern autonomous execution?
          </motion.h2>

          <motion.p
            variants={item}
            transition={itemTransition}
            className="mt-5 max-w-md text-balance text-[15px] leading-relaxed text-muted-foreground sm:text-base"
          >
            If you&apos;re moving from AI pilots to production-grade autonomous systems, CompliAGL helps you operationalize policy, enforce execution controls, and produce proof you can stand behind.
          </motion.p>

          <motion.div
            variants={item}
            transition={itemTransition}
            className="mt-8 flex flex-wrap items-center justify-center gap-3"
          >
            <CutButton variant="solid" href="https://www.compliledger.com/contact">
              Request Demo
            </CutButton>
            <CutButton variant="outline" href="#portal-demo">
              See the Platform
            </CutButton>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
