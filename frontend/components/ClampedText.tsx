"use client";
import { useState } from "react";

const CLAMP_LENGTH = 140;

export default function ClampedText({ text, className = "" }: { text: string; className?: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > CLAMP_LENGTH;
  const shown = expanded || !isLong ? text : text.slice(0, CLAMP_LENGTH).trimEnd() + "…";

  return (
    <span className={className}>
      {shown}
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-1.5 text-xs text-blue-400 hover:text-blue-300 whitespace-nowrap"
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </span>
  );
}
