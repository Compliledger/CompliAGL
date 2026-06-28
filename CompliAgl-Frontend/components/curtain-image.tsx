"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";

const VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT = /* glsl */ `
  uniform float uProgress;
  uniform vec2 uTextureSize;
  uniform vec2 uElementSize;
  uniform sampler2D uTexture;
  uniform float uGrayscale;
  uniform float uContrast;
  uniform vec3 uColor;
  uniform vec2 uMouse;
  uniform float uHover;
  uniform float uRadius;
  varying vec2 vUv;

  float quadraticInOut(float t) {
    float p = 2.0 * t * t;
    return t < 0.5 ? p : -p + (4.0 * t) - 1.0;
  }

  float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
  }

  void main() {
    vec2 uv = vUv - vec2(0.5);
    float aspect1 = uTextureSize.x / uTextureSize.y;
    float aspect2 = uElementSize.x / uElementSize.y;
    if (aspect1 > aspect2) { uv *= vec2(aspect2 / aspect1, 1.0); }
    else { uv *= vec2(1.0, aspect1 / aspect2); }
    uv += vec2(0.5);

    float imageAspect = uTextureSize.x / uTextureSize.y;

    float progress = quadraticInOut(1.0 - uProgress);
    float s = 50.0;
    vec2 gridSize = vec2(s, floor(s / imageAspect));

    float v = smoothstep(
      0.0, 1.0,
      vUv.y
        + sin(vUv.x * 4.0 + progress * 6.0)
          * mix(0.3, 0.1, abs(0.5 - vUv.x)) * 0.5
          * smoothstep(0.0, 0.2, progress)
        + (1.0 - progress * 2.0)
    );

    float mixnewUV = (vUv.x * 3.0 + (1.0 - v) * 50.0) * progress;
    vec2 subUv = mix(uv, floor(uv * gridSize) / gridSize, mixnewUV);

    vec4 color = texture2D(uTexture, subUv);

    float g = dot(color.rgb, vec3(0.299, 0.587, 0.114));
    color.rgb = mix(color.rgb, vec3(g), uGrayscale);

    color.rgb = clamp((color.rgb - 0.5) * uContrast + 0.5, 0.0, 1.0);

    color.a = pow(v, 1.0);
    color.rgb = mix(color.rgb, uColor, smoothstep(0.5, 0.0, abs(0.5 - color.a)) * progress);

    float reveal = uHover * (1.0 - progress);
    if (reveal > 0.001) {
      float blocks = max(floor(uElementSize.x / 22.0), 4.0);
      vec2 cGrid = vec2(blocks, max(floor(blocks / imageAspect), 1.0));
      vec2 cellId = floor(vUv * cGrid);

      vec2 blockCenter = (cellId + 0.5) / cGrid;
      vec2 md = blockCenter - uMouse;
      md.x *= aspect2;
      float falloff = 1.0 - smoothstep(uRadius * 0.35, uRadius, length(md));

      float mask = step(hash12(cellId), falloff) * reveal;
      if (mask > 0.001) {
        vec2 suv = blockCenter - 0.5;
        if (aspect1 > aspect2) { suv *= vec2(aspect2 / aspect1, 1.0); }
        else { suv *= vec2(1.0, aspect1 / aspect2); }
        suv += 0.5;
        vec3 cCol = texture2D(uTexture, suv).rgb;
        float cg = dot(cCol, vec3(0.299, 0.587, 0.114));
        cCol = mix(cCol, vec3(cg), uGrayscale);
        cCol = clamp((cCol - 0.5) * uContrast + 0.5, 0.0, 1.0);
        color.rgb = mix(color.rgb, cCol, mask);
      }
    }

    color.rgb = pow(color.rgb, vec3(1.0 / 2.2));
    gl_FragColor = color;
  }
`;

type PointerState = { tx: number; ty: number; thover: number };

type PlaneProps = {
  src: string;
  targetRef: React.MutableRefObject<number>;
  pointerRef: React.MutableRefObject<PointerState>;
  invalidateRef: React.MutableRefObject<(() => void) | null>;
  duration: number;
  grayscale: number;
  contrast: number;
  cursorRadius: number;
  revealColor: string;
};

function Plane({
  src,
  targetRef,
  pointerRef,
  invalidateRef,
  duration,
  grayscale,
  contrast,
  cursorRadius,
  revealColor,
}: PlaneProps): ReactNode {
  const { size } = useThree();
  const invalidate = useThree((s) => s.invalidate);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const progressRef = useRef(0);
  const mouseRef = useRef({ x: 0.5, y: 0.5, hover: 0 });
  const [texture, setTexture] = useState<THREE.Texture | null>(null);
  const [texSize, setTexSize] = useState<[number, number]>([1, 1]);

  useEffect(() => {
    invalidateRef.current = invalidate;
    return () => {
      invalidateRef.current = null;
    };
  }, [invalidate, invalidateRef]);

  useEffect(() => {
    let active = true;
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin("anonymous");
    loader.loadAsync(src).then((t) => {
      if (!active) return;
      t.minFilter = THREE.LinearFilter;
      t.magFilter = THREE.LinearFilter;
      const img = t.image as { width: number; height: number };
      setTexSize([img.width, img.height]);
      setTexture(t);
    });
    return () => {
      active = false;
    };
  }, [src]);

  const uniforms = useMemo(
    () => ({
      uProgress: { value: 0 },
      uTexture: { value: null as THREE.Texture | null },
      uTextureSize: { value: new THREE.Vector2(1, 1) },
      uElementSize: { value: new THREE.Vector2(1, 1) },
      uGrayscale: { value: grayscale },
      uContrast: { value: contrast },
      uColor: { value: new THREE.Color(revealColor) },
      uMouse: { value: new THREE.Vector2(0.5, 0.5) },
      uHover: { value: 0 },
      uRadius: { value: cursorRadius },
    }),
    [grayscale, contrast, revealColor, cursorRadius]
  );

  useEffect(() => {
    if (texture) invalidate();
  }, [texture, invalidate]);

  useFrame((_, delta) => {
    const target = targetRef.current;
    const step = Math.min(delta, 0.05) / duration;
    if (progressRef.current < target) {
      progressRef.current = Math.min(target, progressRef.current + step);
    } else if (progressRef.current > target) {
      progressRef.current = Math.max(target, progressRef.current - step);
    }

    const k = 1 - Math.pow(0.0015, Math.min(delta, 0.05));
    const p = pointerRef.current;
    const m = mouseRef.current;
    m.x += (p.tx - m.x) * k;
    m.y += (p.ty - m.y) * k;
    m.hover += (p.thover - m.hover) * k;

    const mat = materialRef.current;
    if (mat) {
      const u = mat.uniforms as unknown as {
        uProgress: THREE.IUniform<number>;
        uTexture: THREE.IUniform<THREE.Texture | null>;
        uTextureSize: THREE.IUniform<THREE.Vector2>;
        uElementSize: THREE.IUniform<THREE.Vector2>;
        uMouse: THREE.IUniform<THREE.Vector2>;
        uHover: THREE.IUniform<number>;
      };
      u.uProgress.value = progressRef.current;
      u.uTexture.value = texture;
      u.uTextureSize.value.set(texSize[0], texSize[1]);
      u.uElementSize.value.set(size.width, size.height);
      u.uMouse.value.set(m.x, m.y);
      u.uHover.value = m.hover;
    }

    const stillRevealing = Math.abs(progressRef.current - target) > 0.0005;
    const pointerSettling =
      Math.abs(p.tx - m.x) > 0.0005 ||
      Math.abs(p.ty - m.y) > 0.0005 ||
      Math.abs(p.thover - m.hover) > 0.0005;
    if (stillRevealing || pointerSettling) invalidate();
  });

  if (!texture) return null;

  return (
    <mesh scale={[size.width, size.height, 1]}>
      <planeGeometry args={[1, 1]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={VERTEX}
        fragmentShader={FRAGMENT}
        uniforms={uniforms}
        transparent
      />
    </mesh>
  );
}

export interface CurtainImageProps {
  src: string;
  alt: string;
  className?: string;
  /** Reveal again every time it re-enters the viewport. Default: once. */
  repeat?: boolean;
  /** Animation length in seconds. Default 1.4. */
  duration?: number;
  /** 0 keeps original colors, 1 forces grayscale. Default 1. */
  grayscale?: number;
  /** Contrast multiplier around mid-grey. 1 = unchanged. Default 1.45. */
  contrast?: number;
  /** Accent color along the reveal edge and cursor spotlight. Default blue-500. */
  revealColor?: string;
  /** Enable the cursor-follow pixelation spotlight. Default true. */
  interactive?: boolean;
  /** Spotlight radius in element-height units. Default 0.32. */
  cursorRadius?: number;
}

export function CurtainImage({
  src,
  alt,
  className,
  repeat = false,
  duration = 1.4,
  grayscale = 1,
  contrast = 1.45,
  revealColor = "#3b82f6",
  interactive = true,
  cursorRadius = 0.32,
}: CurtainImageProps): ReactNode {
  const wrapRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(0);
  const pointerRef = useRef<PointerState>({ tx: 0.5, ty: 0.5, thover: 0 });
  const invalidateRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reduce) {
      targetRef.current = 1;
      invalidateRef.current?.();
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting) {
          targetRef.current = 1;
          invalidateRef.current?.();
          if (!repeat) observer.disconnect();
        } else if (repeat) {
          targetRef.current = 0;
          invalidateRef.current?.();
        }
      },
      { threshold: 0.25 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [repeat]);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!interactive) return;
    const r = e.currentTarget.getBoundingClientRect();
    const p = pointerRef.current;
    p.tx = (e.clientX - r.left) / r.width;
    p.ty = 1 - (e.clientY - r.top) / r.height; // flip to UV space
    p.thover = 1;
    invalidateRef.current?.();
  };

  const handlePointerLeave = () => {
    pointerRef.current.thover = 0;
    invalidateRef.current?.();
  };

  return (
    <div
      ref={wrapRef}
      className={className}
      role="img"
      aria-label={alt}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <Canvas
        orthographic
        camera={{ zoom: 1, position: [0, 0, 100] }}
        dpr={[1, 1.5]}
        frameloop="demand"
        gl={{
          alpha: true,
          antialias: false,
          powerPreference: "high-performance",
        }}
        style={{ width: "100%", height: "100%" }}
      >
        <Plane
          src={src}
          targetRef={targetRef}
          pointerRef={pointerRef}
          invalidateRef={invalidateRef}
          duration={duration}
          grayscale={grayscale}
          contrast={contrast}
          cursorRadius={cursorRadius}
          revealColor={revealColor}
        />
      </Canvas>
    </div>
  );
}
