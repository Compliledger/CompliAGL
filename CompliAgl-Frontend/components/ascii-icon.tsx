"use client";

import { useEffect, useRef, type ReactNode } from "react";

export type Shape =
  | "scan"
  | "shield"
  | "key"
  | "bolt"
  | "plus"
  | "bars";

type AsciiIconProps = {
  shape: Shape;
  color?: string;
  cols?: number;
  className?: string;
};

const PATHS: Record<Shape, { d: string; evenOdd?: boolean }> = {
  scan: {
    d:
      "M3 50 C28 12 72 12 97 50 C72 88 28 88 3 50 Z" +
      "M17 50 C34 26 66 26 83 50 C66 74 34 74 17 50 Z" +
      "M31 50 A19 19 0 1 1 69 50 A19 19 0 1 1 31 50 Z",
    evenOdd: true,
  },
  shield: {
    d: "M50 8 L86 22 L86 50 C86 78 62 90 50 94 C38 90 14 78 14 50 L14 22 Z",
  },
  key: {
    d:
      "M6 50 A22 22 0 1 1 50 50 A22 22 0 1 1 6 50 Z" +
      "M18 50 A10 10 0 1 1 38 50 A10 10 0 1 1 18 50 Z" +
      "M50 42 L92 42 L92 58 L50 58 Z" +
      "M70 58 L78 58 L78 72 L70 72 Z" +
      "M84 58 L92 58 L92 76 L84 76 Z",
    evenOdd: true,
  },
  bolt: {
    d: "M60 4 L26 52 L48 52 L40 96 L80 44 L56 44 Z",
  },
  plus: {
    d: "M40 10 H60 V40 H90 V60 H60 V90 H40 V60 H10 V40 H40 Z",
  },
  bars: {
    d: "M14 58 H30 V88 H14 Z M42 38 H58 V88 H42 Z M70 18 H86 V88 H70 Z",
  },
};

const GLYPHS = "@#%&$08WMXKB".split("");

function hash(x: number, y: number, t: number): number {
  const n = Math.sin(x * 12.9898 + y * 78.233 + t * 43.123) * 43758.5453;
  return n - Math.floor(n);
}

function buildMask(shape: Shape, cols: number, rows: number): boolean[] {
  const ss = 4;
  const w = cols * ss;
  const h = rows * ss;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  const mask = new Array<boolean>(cols * rows).fill(false);
  if (!ctx) return mask;

  const { d, evenOdd } = PATHS[shape];
  ctx.save();
  ctx.scale(w / 100, h / 100);
  ctx.fillStyle = "#fff";
  ctx.fill(new Path2D(d), evenOdd ? "evenodd" : "nonzero");
  ctx.restore();

  const data = ctx.getImageData(0, 0, w, h).data;
  for (let cy = 0; cy < rows; cy++) {
    for (let cx = 0; cx < cols; cx++) {
      let hits = 0;
      for (let sy = 0; sy < ss; sy++) {
        for (let sx = 0; sx < ss; sx++) {
          const px = cx * ss + sx;
          const py = cy * ss + sy;
          const a = data[(py * w + px) * 4 + 3] ?? 0;
          if (a > 110) hits++;
        }
      }
      mask[cy * cols + cx] = hits / (ss * ss) > 0.4;
    }
  }
  return mask;
}

export function AsciiIcon({
  shape,
  color = "#2f80ff",
  cols = 22,
  className = "",
}: AsciiIconProps): ReactNode {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rows = cols;
    const cell = 9;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = cols * cell * dpr;
    canvas.height = rows * cell * dpr;
    canvas.style.width = `${cols * cell}px`;
    canvas.style.height = `${rows * cell}px`;
    ctx.scale(dpr, dpr);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `bold ${cell}px var(--font-mono), monospace`;
    ctx.fillStyle = color;

    const mask = buildMask(shape, cols, rows);

    const draw = (time: number, reveal: number) => {
      ctx.clearRect(0, 0, cols * cell, rows * cell);
      const revealRows = reveal * (rows + 1);
      for (let cy = 0; cy < rows; cy++) {
        if (cy > revealRows) continue;
        const settled = revealRows - cy >= 1;
        for (let cx = 0; cx < cols; cx++) {
          if (!mask[cy * cols + cx]) continue;
          const rate = settled ? 150 + hash(cx, cy, 2) * 260 : 35;
          const bucket = Math.floor(time / rate + hash(cx, cy, 1) * 7);
          const gi = Math.floor(hash(cx, cy, bucket) * GLYPHS.length);
          const ch = GLYPHS[Math.min(GLYPHS.length - 1, gi)] ?? "#";
          ctx.globalAlpha = 0.82 + hash(cx, cy, bucket + 3) * 0.18;
          ctx.fillText(ch, cx * cell + cell / 2, cy * cell + cell / 2);
        }
      }
      ctx.globalAlpha = 1;
    };

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      draw(0, 1);
      return;
    }

    let raf = 0;
    let lastFrame = 0;
    let revealStart = 0;
    let running = false;
    const loop = (t: number) => {
      if (!revealStart) revealStart = t;
      if (t - lastFrame >= 44) {
        lastFrame = t;
        const reveal = Math.min(1, (t - revealStart) / 650);
        draw(t, reveal);
      }
      raf = requestAnimationFrame(loop);
    };
    const start = () => {
      if (running) return;
      running = true;
      raf = requestAnimationFrame(loop);
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) start();
        else stop();
      },
      { threshold: 0 }
    );
    observer.observe(canvas);

    return () => {
      observer.disconnect();
      stop();
    };
  }, [shape, color, cols]);

  return <canvas ref={canvasRef} aria-hidden className={className} />;
}
