"use client";

import { useState } from "react";
import type { EvidenceView, Source } from "@/lib/types";

/** Split `text` around the first case-insensitive occurrence of `quote`. */
export function splitHighlight(text: string, quote: string): [string, string, string] | null {
  const lower = text.toLowerCase();
  if (lower.length !== text.length) return null;
  const i = lower.indexOf(quote.toLowerCase());
  if (i < 0 || !quote) return null;
  return [text.slice(0, i), text.slice(i, i + quote.length), text.slice(i + quote.length)];
}

interface Props {
  evidence: EvidenceView[];
  sources: Source[];
}

export function EvidenceViewer({ evidence, sources }: Props) {
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const byId = new Map(sources.map((s) => [s.id, s]));

  if (evidence.length === 0) {
    return <p className="muted small">No evidence attached.</p>;
  }

  return (
    <div>
      {evidence.map((ev, i) => {
        if (ev.redacted) {
          return (
            <div key={i} className="evidence restricted">
              <strong>Restricted source</strong>
              <div className="small muted">Hidden for your role.</div>
            </div>
          );
        }
        const src = ev.source_id ? byId.get(ev.source_id) : undefined;
        const parts = src && ev.quote ? splitHighlight(src.text, ev.quote) : null;
        const meta = [
          ev.source_id,
          src ? `${src.kind} by ${src.author}` : null,
          ev.timestamp,
          ev.match_kind ? `match: ${ev.match_kind}` : null,
        ]
          .filter(Boolean)
          .join(" · ");
        return (
          <div key={i} className="evidence">
            <blockquote>“{ev.quote}”</blockquote>
            <div className="small muted">{meta}</div>
            {ev.match_kind === "none" && (
              <div style={{ marginTop: 4 }}>
                <span className="badge badge-missing">? Quote not found in the cited source</span>
              </div>
            )}
            {src && (
              <button type="button" className="linkish" onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}>
                {open[i] ? "Hide full source" : "Show full source"}
              </button>
            )}
            {open[i] && src && (
              <div className="source-text">
                {parts ? (
                  <>
                    {parts[0]}
                    <mark>{parts[1]}</mark>
                    {parts[2]}
                  </>
                ) : (
                  src.text
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
