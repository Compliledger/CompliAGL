"use client";

import { CutButton } from "@/components/cut-button";
import {
  DUOTONE_BASE,
  DUOTONE_CONTAINER,
  DuotoneOverlay,
} from "@/components/duotone";
import { useReducedMotion } from "@/lib/motion";
import { ArrowRight } from "lucide-react";
import {
  motion,
  useScroll,
  useTransform,
  type MotionValue,
} from "motion/react";
import { useRef, type CSSProperties, type ReactNode } from "react";

const IMAGES: string[] = Array.from(
  { length: 12 },
  (_, i) => `/grid/${String(i + 1).padStart(2, "0")}.webp`,
);

const COLUMNS: string[][] = [0, 1, 2].map((col) =>
  IMAGES.filter((_, i) => i % 3 === col),
);

const TILE_CLIP =
  "polygon(var(--cut) 0, 100% 0, 100% calc(100% - var(--cut)), calc(100% - var(--cut)) 100%, 0 100%, 0 var(--cut))";

const TILE_STYLE = { "--cut": "12px", clipPath: TILE_CLIP } as CSSProperties;

function DuotoneImage({ src }: { src: string }): ReactNode {
  return (
    <div
      style={TILE_STYLE}
      className={`relative aspect-square w-full overflow-hidden ${DUOTONE_CONTAINER}`}
    >
      <div
        style={{ backgroundImage: `url(${src})` }}
        className={`absolute inset-0 bg-cover bg-center ${DUOTONE_BASE}`}
      />
      <DuotoneOverlay />
    </div>
  );
}

function Heading(): ReactNode {
  return (
    <h2 className="mx-auto max-w-4xl text-balance font-serif text-4xl font-normal leading-[1.08] tracking-[-0.01em] sm:text-5xl lg:text-[3.5rem]">
      Operationalize governance across{" "}
      <span className="font-sans font-semibold tracking-tight">frameworks, controls, and execution</span>{" "}
      from one platform.
    </h2>
  );
}

function CallToAction(): ReactNode {
  return (
    <CutButton href="#capabilities" className="mt-8">
      Explore the governance stack
      <ArrowRight className="h-4 w-4" aria-hidden="true" />
    </CutButton>
  );
}

type TileProps = {
  progress: MotionValue<number>;
  src: string;
  colIndex: number;
  pos: number;
  colLen: number;
};

function Tile({ progress, src, colIndex, pos, colLen }: TileProps): ReactNode {
  const fromTop = colIndex % 2 === 0;
  const isCenter = colIndex === 1;

  const order = fromTop ? colLen - 1 - pos : pos;
  const start = 0.06 + order * 0.045;
  const end = start + 0.3;

  const revealY = useTransform(
    progress,
    [start, end],
    [fromTop ? "-90vh" : "90vh", "0vh"],
    { clamp: true },
  );

  const mid = Math.floor(colLen / 2);
  const spreadTo = isCenter ? `${(pos < mid ? -1 : 1) * 42}%` : "0%";
  const spreadY = useTransform(progress, [0.54, 0.9], ["0%", spreadTo], {
    clamp: true,
  });

  return (
    <motion.div style={{ y: revealY }} className="will-change-transform">
      <motion.div style={{ y: spreadY }} className="will-change-transform">
        <DuotoneImage src={src} />
      </motion.div>
    </motion.div>
  );
}

function StaticCoverage(): ReactNode {
  return (
    <section
      id="platform"
      className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 sm:py-32 lg:px-10"
    >
      <div className="text-center">
        <Heading />
        <div className="flex justify-center">
          <CallToAction />
        </div>
      </div>

      <div className="mx-auto mt-14 grid max-w-3xl grid-cols-3 gap-3 sm:gap-4">
        {IMAGES.map((src) => (
          <DuotoneImage key={src} src={src} />
        ))}
      </div>
    </section>
  );
}

export function CoverageGrid(): ReactNode {
  const prefersReducedMotion = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end end"],
  });

  const scale = useTransform(scrollYProgress, [0.5, 0.92], [1, 2.05]);
  const leftX = useTransform(scrollYProgress, [0.52, 0.92], ["0%", "-55%"]);
  const rightX = useTransform(scrollYProgress, [0.52, 0.92], ["0%", "55%"]);
  const gridOpacity = useTransform(
    scrollYProgress,
    [0, 0.03, 0.86, 0.99],
    [0, 1, 1, 0],
  );

  const titleOpacity = useTransform(scrollYProgress, [0.02, 0.14], [0, 1]);
  const titleY = useTransform(
    scrollYProgress,
    [0.02, 0.14, 0.6, 0.82],
    [28, 0, 0, -8],
  );

  const bodyOpacity = useTransform(scrollYProgress, [0.6, 0.8], [0, 1]);
  const bodyY = useTransform(scrollYProgress, [0.6, 0.8], [16, 0]);
  const bodyPointer = useTransform(scrollYProgress, (v) =>
    v > 0.62 ? "auto" : "none",
  );

  if (prefersReducedMotion) {
    return <StaticCoverage />;
  }

  return (
    <section id="platform" ref={sectionRef} className="relative h-[420vh]">
      <div className="sticky top-0 h-screen overflow-hidden bg-background">
        <motion.div
          style={{ opacity: gridOpacity }}
          className="absolute inset-0 z-0 flex items-center justify-center"
        >
          <motion.div
            style={{ scale }}
            className="w-[min(86vw,760px)] will-change-transform"
          >
            <div className="grid grid-cols-3 gap-3 sm:gap-4">
              {COLUMNS.map((col, colIndex) => (
                <motion.div
                  key={colIndex}
                  style={{
                    x: colIndex === 0 ? leftX : colIndex === 2 ? rightX : 0,
                  }}
                  className="flex flex-col gap-3 will-change-transform sm:gap-4"
                >
                  {col.map((src, pos) => (
                    <Tile
                      key={src}
                      progress={scrollYProgress}
                      src={src}
                      colIndex={colIndex}
                      pos={pos}
                      colLen={col.length}
                    />
                  ))}
                </motion.div>
              ))}
            </div>
          </motion.div>
        </motion.div>

        <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center px-5 text-center">
          <motion.div style={{ opacity: titleOpacity, y: titleY }}>
            <Heading />
          </motion.div>

          <motion.div
            style={{ opacity: bodyOpacity, y: bodyY, pointerEvents: bodyPointer }}
            className="flex flex-col items-center"
          >
            <CallToAction />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
