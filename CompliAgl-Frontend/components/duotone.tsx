import type { ReactNode } from "react";

export const DUOTONE_CONTAINER =
  "bg-[#e6eeff] [filter:saturate(1.15)] [isolation:isolate] dark:bg-[#05122e] dark:[filter:saturate(1.35)]";

export const DUOTONE_BASE =
  "[filter:grayscale(1)_contrast(0.85)_brightness(1.55)] dark:[filter:grayscale(1)_contrast(1.2)_brightness(1.08)]";

export function DuotoneOverlay(): ReactNode {
  return (
    <>
      <div className="absolute inset-0 bg-[#3b76ff] mix-blend-color dark:bg-[#1466ff]" />
      <div className="absolute inset-0 bg-[#9bc0ff] opacity-30 mix-blend-multiply dark:bg-[#0a235c] dark:opacity-40" />
      <div className="absolute inset-0 bg-white opacity-25 mix-blend-screen dark:bg-[#4d9bff] dark:opacity-25" />
    </>
  );
}
