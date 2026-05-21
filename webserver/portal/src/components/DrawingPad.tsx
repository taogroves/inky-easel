"use client";

import { useEffect, useRef, useState } from "react";

import DisplayPreview, { FRAME_COLORS, FRAME_PREVIEW } from "@/components/DisplayPreview";

type DrawingMode = "pixel" | "full";

const PIXEL_WIDTH = 80;
const PIXEL_HEIGHT = 48;
const FULL_PEN_SIZES = [4, 8, 16, 28];
const PIXEL_PEN_SIZES = [1, 2, 4];

function fillCanvas(canvas: HTMLCanvasElement, color = "#ffffff") {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function exportFrameImage(canvas: HTMLCanvasElement, mode: DrawingMode): string {
  const out = document.createElement("canvas");
  out.width = FRAME_PREVIEW.width;
  out.height = FRAME_PREVIEW.height;
  const ctx = out.getContext("2d");
  if (!ctx) return "";
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.imageSmoothingEnabled = mode !== "pixel";
  ctx.drawImage(canvas, 0, 0, out.width, out.height);
  return out.toDataURL("image/png").split(",", 2)[1] ?? "";
}

export default function DrawingPad({
  onImageChange,
}: {
  onImageChange: (imageBase64: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDrawingRef = useRef(false);
  const lastPointRef = useRef<{ x: number; y: number } | null>(null);
  const [mode, setMode] = useState<DrawingMode>("pixel");
  const [color, setColor] = useState<string>(FRAME_COLORS[0].value);
  const [penSize, setPenSize] = useState(1);

  function emitImage() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    onImageChange(exportFrameImage(canvas, mode));
  }

  function resetCanvas(nextMode = mode) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = nextMode === "pixel" ? PIXEL_WIDTH : FRAME_PREVIEW.width;
    canvas.height = nextMode === "pixel" ? PIXEL_HEIGHT : FRAME_PREVIEW.height;
    canvas.style.imageRendering = nextMode === "pixel" ? "pixelated" : "auto";
    fillCanvas(canvas);
    onImageChange(exportFrameImage(canvas, nextMode));
  }

  useEffect(() => {
    resetCanvas(mode);
    // Initialize only when the backing resolution changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  function canvasPoint(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
    return { x, y };
  }

  function drawAt(point: { x: number; y: number }) {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (mode === "pixel") {
      const half = Math.floor(penSize / 2);
      const cx = Math.floor(point.x);
      const cy = Math.floor(point.y);
      ctx.fillRect(cx - half, cy - half, penSize, penSize);
      return;
    }

    const last = lastPointRef.current ?? point;
    ctx.lineWidth = penSize;
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    lastPointRef.current = point;
  }

  function pointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    isDrawingRef.current = true;
    lastPointRef.current = canvasPoint(event);
    drawAt(lastPointRef.current);
  }

  function pointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!isDrawingRef.current) return;
    drawAt(canvasPoint(event));
  }

  function pointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!isDrawingRef.current) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    isDrawingRef.current = false;
    lastPointRef.current = null;
    emitImage();
  }

  const penSizes = mode === "pixel" ? PIXEL_PEN_SIZES : FULL_PEN_SIZES;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-ink-soft">Mode:</span>
        <button
          type="button"
          className={mode === "pixel" ? "btn-primary text-xs" : "btn-secondary text-xs"}
          onClick={() => {
            setMode("pixel");
            setPenSize(1);
          }}
        >
          Pixel art 80×48
        </button>
        <button
          type="button"
          className={mode === "full" ? "btn-primary text-xs" : "btn-secondary text-xs"}
          onClick={() => {
            setMode("full");
            setPenSize(8);
          }}
        >
          Full resolution
        </button>
        <button type="button" className="btn-secondary ml-auto text-xs" onClick={() => resetCanvas()}>
          Clear
        </button>
      </div>

      <DisplayPreview>
        <canvas
          ref={canvasRef}
          className="h-full w-full touch-none cursor-crosshair"
          onPointerDown={pointerDown}
          onPointerMove={pointerMove}
          onPointerUp={pointerUp}
          onPointerCancel={pointerUp}
        />
      </DisplayPreview>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-soft">Color</span>
          {FRAME_COLORS.map((swatch) => (
            <button
              key={swatch.value}
              type="button"
              className={`h-7 w-7 rounded border ${color === swatch.value ? "border-ink ring-2 ring-ink/40" : "border-ink/20"}`}
              style={{ backgroundColor: swatch.value }}
              title={swatch.name}
              onClick={() => setColor(swatch.value)}
            />
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-soft">Pen</span>
          {penSizes.map((size) => (
            <button
              key={size}
              type="button"
              className={penSize === size ? "btn-primary px-3 py-1 text-xs" : "btn-secondary px-3 py-1 text-xs"}
              onClick={() => setPenSize(size)}
            >
              {size}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
