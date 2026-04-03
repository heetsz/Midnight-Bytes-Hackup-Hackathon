"use client";

import type React from "react";
import { useEffect, useRef, useCallback, useState } from "react";
import createGlobe from "cobe";

interface AnalyticsMarker {
  id: string;
  location: [number, number];
  visitors: number;
  trend: number;
  fraud?: number;
  riskTone?: "danger" | "warning" | "success";
}

interface GlobeAnalyticsProps {
  markers?: AnalyticsMarker[];
  className?: string;
  speed?: number;
}

const defaultMarkers: AnalyticsMarker[] = [
  { id: "vis-1", location: [40.71, -74.01], visitors: 847, trend: 12 },
  { id: "vis-2", location: [51.51, -0.13], visitors: 623, trend: -3 },
  { id: "vis-3", location: [35.68, 139.65], visitors: 412, trend: 8 },
  { id: "vis-4", location: [48.86, 2.35], visitors: 385, trend: 5 },
  { id: "vis-5", location: [-33.87, 151.21], visitors: 201, trend: 15 },
  { id: "vis-6", location: [52.52, 13.41], visitors: 178, trend: -1 },
];

export function GlobeAnalytics({
  markers: initialMarkers = defaultMarkers,
  className = "",
  speed = 0.003,
}: GlobeAnalyticsProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<{ x: number; y: number } | null>(null);
  const dragOffset = useRef({ phi: 0, theta: 0 });
  const phiOffsetRef = useRef(0);
  const thetaOffsetRef = useRef(0);
  const isPausedRef = useRef(false);
  const [data, setData] = useState(initialMarkers);
  const [hoveredMarkerId, setHoveredMarkerId] = useState<string | null>(null);

  useEffect(() => {
    setData(initialMarkers);
  }, [initialMarkers]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    pointerInteracting.current = { x: e.clientX, y: e.clientY };
    if (canvasRef.current) canvasRef.current.style.cursor = "grabbing";
    isPausedRef.current = true;
  }, []);

  const handlePointerUp = useCallback(() => {
    if (pointerInteracting.current !== null) {
      phiOffsetRef.current += dragOffset.current.phi;
      thetaOffsetRef.current += dragOffset.current.theta;
      dragOffset.current = { phi: 0, theta: 0 };
    }
    pointerInteracting.current = null;
    if (canvasRef.current) canvasRef.current.style.cursor = "grab";
    isPausedRef.current = false;
  }, []);

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (pointerInteracting.current !== null) {
        dragOffset.current = {
          phi: (e.clientX - pointerInteracting.current.x) / 300,
          theta: (e.clientY - pointerInteracting.current.y) / 1000,
        };
      }
    };
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerup", handlePointerUp, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [handlePointerUp]);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    let globe: ReturnType<typeof createGlobe> | null = null;
    let animationId: number;
    let phi = 0;

    function init() {
      const width = canvas.offsetWidth;
      if (width === 0 || globe) return;

      globe = createGlobe(canvas, {
        devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
        width,
        height: width,
        phi: 0,
        theta: 0.2,
        dark: 0,
        diffuse: 1.5,
        mapSamples: 16000,
        mapBrightness: 10,
        baseColor: [1, 1, 1],
        markerColor: [0.3, 0.85, 0.45],
        glowColor: [0.94, 0.93, 0.91],
        markerElevation: 0,
        markers: initialMarkers.map((m) => ({
          location: m.location,
          size: 0.04,
          id: m.id,
        })),
        arcs: [],
        arcColor: [0.25, 0.9, 0.5],
        arcWidth: 0.5,
        arcHeight: 0.25,
        opacity: 0.7,
      });
      function animate() {
        if (!isPausedRef.current) phi += speed;
        globe!.update({
          phi: phi + phiOffsetRef.current + dragOffset.current.phi,
          theta: 0.2 + thetaOffsetRef.current + dragOffset.current.theta,
        });
        animationId = requestAnimationFrame(animate);
      }
      animate();
      setTimeout(() => canvas && (canvas.style.opacity = "1"));
    }

    if (canvas.offsetWidth > 0) {
      init();
    } else {
      const ro = new ResizeObserver((entries) => {
        if (entries[0]?.contentRect.width > 0) {
          ro.disconnect();
          init();
        }
      });
      ro.observe(canvas);
    }

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      if (globe) globe.destroy();
    };
  }, [initialMarkers, speed]);

  return (
    <div className={`relative aspect-square select-none ${className}`}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        style={{
          width: "100%",
          height: "100%",
          cursor: "grab",
          opacity: 0,
          transition: "opacity 1.2s ease",
          borderRadius: "50%",
          touchAction: "none",
        }}
      />
      {data.map((m) => (
        <div
          key={m.id}
          style={{
            position: "absolute",
            // @ts-expect-error CSS Anchor Positioning
            positionAnchor: `--cobe-${m.id}`,
            bottom: "anchor(top)",
            left: "anchor(center)",
            translate: "-50% 0",
            marginBottom: 6,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "auto" as const,
            whiteSpace: "nowrap" as const,
            opacity: `var(--cobe-visible-${m.id}, 0)`,
            filter: `blur(calc((1 - var(--cobe-visible-${m.id}, 0)) * 8px))`,
            transition: "opacity 0.3s, filter 0.3s",
          }}
          onMouseEnter={() => setHoveredMarkerId(m.id)}
          onMouseLeave={() => setHoveredMarkerId((prev) => (prev === m.id ? null : prev))}
        >
          <span
            style={{
              width: "12px",
              height: "12px",
              borderRadius: "999px",
              border: "1px solid rgba(255,255,255,0.25)",
              boxShadow: "0 0 12px rgba(255,255,255,0.25)",
              background:
                m.riskTone === "danger"
                  ? "#fb7185"
                  : m.riskTone === "warning"
                  ? "#fbbf24"
                  : "#34d399",
            }}
          />

          {hoveredMarkerId === m.id && (
            <span
              style={{
                position: "absolute",
                bottom: "16px",
                left: "50%",
                transform: "translateX(-50%)",
                fontFamily: "monospace",
                fontSize: "0.62rem",
                display: "flex",
                alignItems: "center",
                gap: "0.45rem",
                padding: "0.35rem 0.55rem",
                background: "rgba(0,0,0,0.9)",
                border: "1px solid rgba(148,163,184,0.3)",
                borderRadius: "6px",
                color: "#e2e8f0",
              }}
            >
              <span>{m.id}</span>
              <span>{m.visitors.toLocaleString()} txns</span>
              {typeof m.fraud === "number" && <span>{m.fraud} fraud</span>}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
