"use client";
import { useState } from "react";
import MermaidDiagram from "@/components/MermaidDiagram";

// Diagrams wider than they are tall waste space (and shrink unreadably small)
// squeezed into a narrow sidebar, so they get a full-width banner above the
// content instead. Taller/narrower diagrams fit naturally in a sticky sidebar.
const WIDE_THRESHOLD = 1.3;

export default function DiagramLayout({ diagram, id, children }: { diagram?: string; id: string; children: React.ReactNode }) {
  const [aspectRatio, setAspectRatio] = useState<number | null>(null);

  if (!diagram) return <>{children}</>;

  const isWide = aspectRatio !== null && aspectRatio >= WIDE_THRESHOLD;

  // MermaidDiagram is mounted exactly once and never remounted — only the
  // surrounding layout classes change based on aspect ratio. Remounting it
  // (e.g. by rendering it in two different JSX branches) re-runs mermaid's
  // render with the same element id and silently fails the second time.
  return (
    <div className={isWide ? "space-y-6" : "grid lg:grid-cols-[minmax(0,320px)_1fr] gap-6"}>
      <div className={isWide ? "" : "lg:sticky lg:top-4 lg:self-start"}>
        <MermaidDiagram chart={diagram} id={id} onAspectRatio={setAspectRatio} />
      </div>
      {children}
    </div>
  );
}
