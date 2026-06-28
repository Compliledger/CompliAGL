"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type AsciiPortraitProps = {
  src: string;
  cols?: number;
  color?: string;
  className?: string;
};

const RAMP = " .:-=+*oahkbd#WM".split("");

function hash(x: number, y: number, t: number): number {
  const n = Math.sin(x * 12.9898 + y * 78.233 + t * 37.719) * 43758.5453;
  return n - Math.floor(n);
}

export function AsciiPortrait({
  src,
  cols = 100,
  color = "#2f80ff",
  className = "",
}: AsciiPortraitProps): ReactNode {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    const root = document.documentElement;
    const update = () => setIsDark(root.classList.contains("dark"));
    update();
    const obs = new MutationObserver(update);
    obs.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cellW = 5;
    const cellH = 8;
    let raf = 0;
    let cancelled = false;

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = src;

    img.onload = () => {
      if (cancelled) return;
      const rows = Math.max(
        1,
        Math.round((cols * (img.height / img.width) * cellW) / cellH)
      );

      const sample = document.createElement("canvas");
      sample.width = cols;
      sample.height = rows;
      const sctx = sample.getContext("2d");
      if (!sctx) return;
      sctx.drawImage(img, 0, 0, cols, rows);
      const data = sctx.getImageData(0, 0, cols, rows).data;

      const bright = new Float32Array(cols * rows);
      let cmn = 1;
      let cmx = 0;
      for (let i = 0; i < cols * rows; i++) {
        const r = data[i * 4] ?? 0;
        const g = data[i * 4 + 1] ?? 0;
        const b = data[i * 4 + 2] ?? 0;
        const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        bright[i] = lum;
        if (lum < cmn) cmn = lum;
        if (lum > cmx) cmx = lum;
      }
      const crange = cmx - cmn || 1;
      for (let i = 0; i < cols * rows; i++) {
        bright[i] = Math.pow(((bright[i] ?? 0) - cmn) / crange, 1.15);
      }

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = cols * cellW;
      const h = rows * cellH;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = `${cellH}px var(--font-mono), monospace`;
      ctx.fillStyle = color;

      const cr = parseInt(color.slice(1, 3), 16);
      const cg = parseInt(color.slice(3, 5), 16);
      const cb = parseInt(color.slice(5, 7), 16);

      const base = document.createElement("canvas");
      base.width = w;
      base.height = h;
      const bctx = base.getContext("2d");
      if (bctx) {
        const scale = Math.max(w / img.width, h / img.height);
        const dw = img.width * scale;
        const dh = img.height * scale;
        bctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
        const id = bctx.getImageData(0, 0, w, h);
        const p = id.data;
        let pmn = 1;
        let pmx = 0;
        const n = w * h;
        const lums = new Float32Array(n);
        for (let i = 0; i < n; i++) {
          const lum =
            (0.299 * (p[i * 4] ?? 0) +
              0.587 * (p[i * 4 + 1] ?? 0) +
              0.114 * (p[i * 4 + 2] ?? 0)) /
            255;
          lums[i] = lum;
          if (lum < pmn) pmn = lum;
          if (lum > pmx) pmx = lum;
        }
        const prange = pmx - pmn || 1;
        for (let i = 0; i < n; i++) {
          const lin = ((lums[i] ?? 0) - pmn) / prange;

          const v = Math.pow(isDark ? lin : 1 - lin, 1.5);
          p[i * 4] = cr;
          p[i * 4 + 1] = cg;
          p[i * 4 + 2] = cb;
          p[i * 4 + 3] = Math.round(v * 255);
        }
        bctx.putImageData(id, 0, 0);
      }

      const maxOrder = cols + rows;
      const draw = (wave: number, reveal: number) => {
        ctx.clearRect(0, 0, w, h);

        ctx.globalAlpha = reveal * 0.85;
        ctx.drawImage(base, 0, 0, w, h);
        ctx.globalAlpha = 1;

        const front = wave * maxOrder;
        for (let cy = 0; cy < rows; cy++) {
          for (let cx = 0; cx < cols; cx++) {
            const order = cx + cy;
            if (order > front) continue;
            const lin = bright[cy * cols + cx] ?? 0;
            const v = isDark ? lin : 1 - lin;
            if (v < 0.14) continue;
            const settled = front - order > 4;
            const px = cx * cellW;
            const py = cy * cellH;

            let ch: string;
            if (settled) {
              const idx = Math.min(
                RAMP.length - 1,
                Math.max(1, Math.round(v * (RAMP.length - 1)))
              );
              ch = RAMP[idx] ?? "#";
            } else {
              ch = RAMP[1 + Math.floor(hash(cx, cy, front | 0) * (RAMP.length - 1))] ?? "#";
            }
            ctx.globalAlpha = 0.35 + v * 0.6;
            ctx.fillText(ch, px + cellW / 2, py + cellH / 2);
          }
        }
        ctx.globalAlpha = 1;
      };

      const reduce = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      if (reduce) {
        draw(1, 1);
        return;
      }

      const WAVE = 1100;
      const REVEAL = 600;
      let start = 0;
      const loop = (t: number) => {
        if (!start) start = t;
        const elapsed = t - start;
        const wave = Math.min(1, elapsed / WAVE);
        const reveal = Math.max(0, Math.min(1, (elapsed - WAVE) / REVEAL));
        draw(wave, reveal);
        if (elapsed < WAVE + REVEAL) raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    };

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [src, cols, color, isDark]);

  return <canvas ref={canvasRef} aria-hidden className={className} />;
}
