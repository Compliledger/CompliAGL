"use client";

import React, { useRef, useEffect, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { cn } from "@/lib/utils";

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  uniform float uTime;
  uniform vec2 uMouse;
  uniform vec2 uResolution;
  uniform sampler2D uFontTexture;
  uniform float uCharCount;
  uniform vec3 uColor;
  uniform bool uInvert;
  uniform float uScale;
  uniform float uSize;
  uniform float uSpeed;
  uniform float uHasMouse;
  uniform float uIntensity;
  uniform float uInteractIntensity;
  uniform float uWaveTension;
  uniform float uWaveTwist;
  uniform sampler2D uVideoTexture;
  uniform bool uHasVideo;

  varying vec2 vUv;

  #define PI 3.14159265359
  #define TAU 6.28318530718

  float flowField(vec2 p, float t) {
    return sin(p.x + sin(p.y + t * 0.1)) * sin(p.y * p.x * 0.1 + t * 0.2);
  }

  vec2 computeField(vec2 p, float t) {
    vec2 ep = vec2(0.05, 0.0);
    vec2 result = vec2(0.0);
    float tension = uWaveTension;
    float twist = uWaveTwist;

    for (int i = 0; i < 10; i++) {
      float t0 = flowField(p, t);
      float t1 = flowField(p + ep.xy, t);
      float t2 = flowField(p + ep.yx, t);
      vec2 gradient = vec2((t1 - t0), (t2 - t0)) / ep.xx;
      vec2 tangent = vec2(-gradient.y, gradient.x);

      p += tangent * tension + gradient * 0.005;
      p.x += sin(t * 0.25) * twist;
      p.y += cos(t * 0.25) * twist;
      result = gradient;
    }

    return result;
  }

  vec3 getDistortion(vec2 coord) {
      vec2 aspect;

      if(uResolution.x > uResolution.y) {
          aspect = vec2(uResolution.x / uResolution.y, 1.0);
      } else {
          aspect = vec2(uResolution.y / uResolution.x, 1.0);
      }

      vec2 uv0 = coord.xy / uResolution.xy * aspect;
      vec2 muv = uMouse.xy / uResolution.xy * aspect;

      float speed = uSpeed;
      float noiseTime = uTime * speed;

      vec2 diff = uv0 - muv;
      float distance = length(diff);

      float radius = 0.5;
      float interaction = smoothstep(radius, 0.0, distance);

      vec2 p = uv0 * uScale;
      float interactStrength = uInteractIntensity * uHasMouse;

      vec2 mouseDistort = normalize(diff) * interaction * interactStrength;
      p += mouseDistort;
      p.x += sin(uTime * 3.0) * interaction * interactStrength * 0.5;
      p.y += cos(uTime * 3.0) * interaction * interactStrength * 0.5;

      vec2 field = computeField(p, noiseTime);

      float val = length(field) * uIntensity;
      val = clamp(val, 0.0, 1.0);

      vec2 totalDisplacement = mouseDistort + field * 0.5 * uIntensity;

      return vec3(val, totalDisplacement);
  }

  void main() {
      float gridSize = uSize;

      vec2 pix = vUv * uResolution;
      vec2 snappedMuv = floor(pix / gridSize) * gridSize;

      vec3 distData = getDistortion(snappedMuv);
      float intensity = distData.x;
      vec2 displacement = distData.yz;

      vec3 col;
      if (uHasVideo) {
        vec2 videoUV = snappedMuv / uResolution;
        vec2 distortedVideoUV = videoUV + (displacement * 0.1);

        col = texture2D(uVideoTexture, distortedVideoUV).rgb;
      } else {
        col = vec3(intensity);
      }

      float gray = 0.3 * col.r + 0.59 * col.g + 0.11 * col.b;

      if (uInvert) {
        gray = 1.0 - gray;
      }

      float charIndex = floor(gray * (uCharCount - 1.0));
      charIndex = clamp(charIndex, 0.0, uCharCount - 1.0);

      vec2 cellUV = fract(pix / gridSize);

      float charWidth = 1.0 / uCharCount;
      vec2 atlasUV = vec2((cellUV.x * charWidth) + (charIndex * charWidth), cellUV.y);

      vec4 fontSample = texture2D(uFontTexture, atlasUV);
      float alpha = fontSample.a;

      vec3 targetColor = uHasVideo ? col : uColor * (gray + 0.1);
      vec3 finalColor = targetColor * alpha;

      gl_FragColor = vec4(finalColor, alpha);
  }
`;

const createFontTexture = (
  chars: string,
  fontSize: number = 64
): THREE.Texture => {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.Texture();

  const charCount = chars.length;
  const width = charCount * fontSize;
  const height = fontSize;

  canvas.width = width;
  canvas.height = height;

  ctx.clearRect(0, 0, width, height);

  ctx.font = `bold ${fontSize}px monospace`;
  ctx.fillStyle = "white";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (let i = 0; i < charCount; i++) {
    const char = chars[i] ?? " ";
    const x = i * fontSize + fontSize / 2;
    const y = fontSize / 2;
    ctx.fillText(char, x, y);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return texture;
};

interface SceneProps {
  mouse: React.MutableRefObject<THREE.Vector2>;
  characters: string;
  color: string;
  invert: boolean;
  scale: number;
  size: number;
  speed: number;
  hasMouse: boolean;
  intensity: number;
  interactionIntensity: number;
  waveTension: number;
  waveTwist: number;
  videoUrl?: string | undefined;
  active: boolean;
}

interface WaveUniforms {
  uTime: THREE.IUniform<number>;
  uMouse: THREE.IUniform<THREE.Vector2>;
  uResolution: THREE.IUniform<THREE.Vector2>;
  uFontTexture: THREE.IUniform<THREE.Texture | null>;
  uCharCount: THREE.IUniform<number>;
  uColor: THREE.IUniform<THREE.Color>;
  uInvert: THREE.IUniform<boolean>;
  uScale: THREE.IUniform<number>;
  uSize: THREE.IUniform<number>;
  uSpeed: THREE.IUniform<number>;
  uHasMouse: THREE.IUniform<number>;
  uIntensity: THREE.IUniform<number>;
  uInteractIntensity: THREE.IUniform<number>;
  uWaveTension: THREE.IUniform<number>;
  uWaveTwist: THREE.IUniform<number>;
  uVideoTexture: THREE.IUniform<THREE.Texture | null>;
  uHasVideo: THREE.IUniform<boolean>;
}

const Scene: React.FC<SceneProps> = ({
  mouse,
  characters,
  color,
  invert,
  scale,
  size: elementSize,
  speed,
  hasMouse,
  intensity,
  interactionIntensity,
  waveTension,
  waveTwist,
  videoUrl,
  active,
}) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const { size, viewport } = useThree();

  const safeCharacters = characters.length > 0 ? characters : " ";

  const fontTextureRef = useRef<THREE.Texture | null>(null);
  const videoTextureRef = useRef<THREE.VideoTexture | null>(null);
  const videoElRef = useRef<HTMLVideoElement | null>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uResolution: { value: new THREE.Vector2(size.width, size.height) },
      uFontTexture: { value: null as THREE.Texture | null },
      uCharCount: { value: safeCharacters.length },
      uColor: { value: new THREE.Color(color) },
      uInvert: { value: invert },
      uScale: { value: scale },
      uSize: { value: elementSize },
      uSpeed: { value: speed },
      uHasMouse: { value: hasMouse ? 1.0 : 0.0 },
      uIntensity: { value: intensity },
      uInteractIntensity: { value: interactionIntensity },
      uWaveTension: { value: waveTension },
      uWaveTwist: { value: waveTwist },
      uVideoTexture: { value: null as THREE.Texture | null },
      uHasVideo: { value: false },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    const texture = createFontTexture(safeCharacters);
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    fontTextureRef.current = texture;
    return () => {
      texture.dispose();
      fontTextureRef.current = null;
    };
  }, [safeCharacters]);

  useEffect(() => {
    if (!videoUrl) {
      videoTextureRef.current = null;
      return;
    }

    const video = document.createElement("video");
    video.src = videoUrl;
    video.crossOrigin = "Anonymous";
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    video.play().catch((e) => console.error("Video play failed", e));

    const texture = new THREE.VideoTexture(video);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    videoTextureRef.current = texture;
    videoElRef.current = video;

    return () => {
      video.pause();
      video.src = "";
      texture.dispose();
      videoTextureRef.current = null;
      videoElRef.current = null;
    };
  }, [videoUrl]);

  useEffect(() => {
    const video = videoElRef.current;
    if (!video) return;
    if (active) {
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }, [active]);

  useFrame((state) => {
    if (materialRef.current) {
      const u = materialRef.current.uniforms as unknown as WaveUniforms;
      u.uTime.value = state.clock.elapsedTime;
      u.uResolution.value.set(size.width, size.height);
      u.uColor.value.set(color);
      u.uInvert.value = invert;
      u.uScale.value = scale;
      u.uSize.value = elementSize;
      u.uSpeed.value = speed;
      u.uHasMouse.value = hasMouse ? 1.0 : 0.0;
      u.uIntensity.value = intensity;
      u.uInteractIntensity.value = interactionIntensity;
      u.uWaveTension.value = waveTension;
      u.uWaveTwist.value = waveTwist;
      u.uCharCount.value = safeCharacters.length;

      if (fontTextureRef.current) {
        u.uFontTexture.value = fontTextureRef.current;
      }

      if (videoTextureRef.current) {
        u.uVideoTexture.value = videoTextureRef.current;
        u.uHasVideo.value = true;
      } else {
        u.uVideoTexture.value = null;
        u.uHasVideo.value = false;
      }

      if (mouse.current) {
        u.uMouse.value.lerp(mouse.current, 0.1);
      }
    }
  });

  return (
    <mesh ref={meshRef}>
      <planeGeometry args={[viewport.width, viewport.height]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
      />
    </mesh>
  );
};

export interface AsciiWavesProps {
  characters?: string;
  color?: string;
  invert?: boolean;
  noiseScale?: number;
  elementSize?: number;
  speed?: number;
  hasCursorInteraction?: boolean;
  intensity?: number;
  interactionIntensity?: number;
  waveTension?: number;
  waveTwist?: number;
  className?: string;
  videoUrl?: string;
}

const AsciiWaves: React.FC<AsciiWavesProps> = ({
  characters = " .:-+*=%@#",
  color = "#ffffff",
  invert = false,
  noiseScale = 2.0,
  elementSize = 16.0,
  speed = 1.0,
  hasCursorInteraction = true,
  intensity = 1.0,
  interactionIntensity = 1.0,
  waveTension = 0.5,
  waveTwist = 0.1,
  className = "",
  videoUrl,
}) => {
  const mouse = useRef(new THREE.Vector2(0, 0));
  const containerRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = React.useState(true);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setInView(entry?.isIntersecting ?? true),
      { rootMargin: "120px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = rect.height - (e.clientY - rect.top);
    mouse.current.set(x, y);
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative h-full w-full cursor-text overflow-hidden",
        className
      )}
      onMouseMove={handleMouseMove}
    >
      <Canvas
        orthographic
        camera={{ position: [0, 0, 1], zoom: 1 }}
        dpr={[1, 1.5]}
        frameloop={inView ? "always" : "never"}
        gl={{
          alpha: true,
          antialias: false,
          powerPreference: "high-performance",
        }}
      >
        <Scene
          mouse={mouse}
          characters={characters}
          color={color}
          invert={invert}
          scale={noiseScale}
          size={elementSize}
          speed={speed}
          hasMouse={hasCursorInteraction}
          intensity={intensity}
          interactionIntensity={interactionIntensity}
          waveTension={waveTension}
          waveTwist={waveTwist}
          videoUrl={videoUrl}
          active={inView}
        />
      </Canvas>
    </div>
  );
};

export default AsciiWaves;
