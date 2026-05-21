import type { ReactNode } from "react";

export const FRAME_PREVIEW = {
  width: 800,
  height: 480,
};

export const FRAME_COLORS = [
  { name: "Black", value: "#000000" },
  { name: "White", value: "#ffffff" },
  { name: "Red", value: "#c81e1e" },
  { name: "Yellow", value: "#f0c828" },
  { name: "Green", value: "#28823c" },
  { name: "Blue", value: "#2346a0" },
] as const;

export default function DisplayPreview({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-md border-4 border-ink bg-white shadow-inner ${className}`}
      style={{ aspectRatio: `${FRAME_PREVIEW.width} / ${FRAME_PREVIEW.height}` }}
    >
      {children}
    </div>
  );
}
