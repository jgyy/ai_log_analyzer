import { useState } from "react";

export default function Evidence({ ids }: { ids?: string[] }) {
  const [open, setOpen] = useState(false);

  if (!ids || ids.length === 0) {
    console.log("empty")
    return null;
  }

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="text-xs text-blue-400 hover:text-blue-300"
      >
        {open ? "Hide" : "Show"} evidence ({ids.length})
      </button>

      {open && (
        <ul className="mt-2 space-y-1 text-xs text-slate-400">
          {ids.map((id) => (
            <li key={id} className="font-mono">
              {id}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}