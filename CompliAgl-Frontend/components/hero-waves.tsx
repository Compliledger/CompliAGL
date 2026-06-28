"use client";

import AsciiWaves from "@/components/ascii-waves";
import { softEase, useReducedMotion } from "@/lib/motion";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";

function useIsMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
}

export function HeroWaves(): ReactNode {
  const mounted = useIsMounted();
  const { resolvedTheme } = useTheme();
  const prefersReducedMotion = useReducedMotion();

  if (!mounted) return null;

  const color = resolvedTheme === "dark" ? "#ffffff" : "#0a0a0a";
  const isDark = resolvedTheme === "dark";
  const targetOpacity = isDark ? 1 : 0.85;
  const fade =
    "linear-gradient(to bottom, transparent 0%, black 25%, black 80%, transparent 100%)";

  return (
    <motion.div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10"
      initial={{ opacity: 0 }}
      animate={{ opacity: targetOpacity }}
      transition={
        prefersReducedMotion
          ? { duration: 0.01 }
          : { duration: 1.6, ease: softEase, delay: 0.1 }
      }
      style={{
        maskImage: fade,
        WebkitMaskImage: fade,
        filter: isDark ? undefined : "saturate(2.4) contrast(1.25)",
      }}
    >
      <AsciiWaves
        color={color}
        intensity={0}
        elementSize={10}
        videoUrl="/sample-video-2.mp4"
        noiseScale={25}
        hasCursorInteraction={true}
        className="opacity-50 dark:opacity-60"
      />
    </motion.div>
  );
}
