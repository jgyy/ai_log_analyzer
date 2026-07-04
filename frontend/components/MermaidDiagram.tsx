"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Maximize2, X } from "lucide-react";

let mermaidInitialized = false;
let renderCounter = 0;

// Reserved words in Mermaid's flowchart grammar (e.g. "end" closes subgraphs)
// break parsing when the AI uses them as a bare node id — rename them rather
// than reject the whole diagram.
const RESERVED_NODE_IDS = new Set(["end", "class", "click", "style", "subgraph", "direction"]);

// AI providers occasionally wrap the diagram in a ```mermaid fence despite
// being told not to, or emit unquoted labels containing characters
// (parentheses, colons, pipes) that break Mermaid's flowchart grammar. Both
// show up as "syntax error" text baked right into the rendered SVG rather
// than as a catchable exception, so we sanitize before handing text to
// Mermaid instead of relying solely on the AI to follow instructions.
export function sanitizeMermaidChart(raw: string): string {
  let chart = raw.trim();

  const fenced = chart.match(/^```(?:mermaid)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) chart = fenced[1].trim();

  // Matches every `id[label]` / `id(label)` / `id{label}` node definition
  // anywhere in the text, so chains like `A[Start] --> B[OOMKilled (137)]`
  // get every node fixed up, not just one per line.
  chart = chart.replace(
    /\b([A-Za-z0-9_-]+)(\[|\(|\{)"?(.*?)"?(\]|\)|\})(?=\s|-->|$)/g,
    (full, nodeId, open, text, close) => {
      const safeId = RESERVED_NODE_IDS.has(nodeId.toLowerCase()) ? `${nodeId}_node` : nodeId;
      const needsQuotes = /["():{}|;]/.test(text);
      const safeText = needsQuotes ? `"${text.replace(/"/g, "'")}"` : text;
      return `${safeId}${open}${safeText}${close}`;
    }
  );

  return chart;
}

async function renderInto(container: HTMLDivElement, chart: string, id: string): Promise<{ width: number; height: number } | null> {
  const mermaid = (await import("mermaid")).default;
  if (!mermaidInitialized) {
    mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" });
    mermaidInitialized = true;
  }
  // securityLevel: "strict" makes Mermaid itself HTML-encode label text and
  // disable click/JS bindings — its documented mitigation for untrusted diagram
  // sources. A generic DOMPurify pass over the resulting SVG string is NOT used
  // here: DOMPurify deliberately strips HTML nested inside <foreignObject> as a
  // namespace-confusion (mutation-XSS) guard, which breaks every Mermaid node
  // label (Mermaid renders labels as HTML inside foreignObject by design).
  // Mermaid keeps an internal registry keyed by this id; React 18 StrictMode's
  // dev-mode double-invocation of effects can call render() twice in quick
  // succession with the same id, and the second call silently returns an
  // empty/invalid diagram. A per-call unique id sidesteps that entirely.
  const uniqueId = `${id}-${++renderCounter}`;
  const { svg } = await mermaid.render(uniqueId, sanitizeMermaidChart(chart));
  container.innerHTML = svg;

  const viewBox = container.querySelector("svg")?.getAttribute("viewBox");
  if (!viewBox) return null;
  const parts = viewBox.split(/\s+/).map(Number);
  if (parts.length !== 4) return null;
  return { width: parts[2], height: parts[3] };
}

export default function MermaidDiagram({ chart, id, onAspectRatio }: { chart: string; id: string; onAspectRatio?: (ratio: number) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const modalContainerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    let cancelled = false;
    if (!chart?.trim() || !containerRef.current) return;
    renderInto(containerRef.current, chart, `mermaid-${id}`)
      .then((size) => {
        if (!cancelled && size && onAspectRatio) onAspectRatio(size.width / size.height);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't render this diagram.");
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chart, id]);

  useEffect(() => {
    let cancelled = false;
    if (!expanded || !chart?.trim() || !modalContainerRef.current) return;
    renderInto(modalContainerRef.current, chart, `mermaid-${id}-modal`).catch(() => {
      if (!cancelled) setError("Couldn't render this diagram.");
    });
    return () => { cancelled = true; };
  }, [expanded, chart, id]);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  if (!chart?.trim()) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="group relative w-full p-4 bg-slate-900/40 border border-slate-700/50 rounded-lg overflow-x-auto text-left"
        title="Click to enlarge"
      >
        {error ? (
          <p className="text-xs text-slate-500">{error}</p>
        ) : (
          <>
            <div ref={containerRef} className="flex justify-center [&_svg]:max-w-full" />
            <div className="absolute inset-0 flex items-center justify-center bg-slate-950/0 group-hover:bg-slate-950/40 transition-colors rounded-lg pointer-events-none">
              <Maximize2 className="h-5 w-5 text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </>
        )}
      </button>

      {expanded && mounted && createPortal(
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-6"
          onClick={() => setExpanded(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-[90vw] h-[85vh] overflow-auto relative"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setExpanded(false)}
              className="absolute top-3 right-3 p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors z-10"
            >
              <X className="h-5 w-5" />
            </button>
            <div ref={modalContainerRef} className="w-full h-full flex items-center justify-center [&_svg]:w-auto [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:max-h-full" />
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
