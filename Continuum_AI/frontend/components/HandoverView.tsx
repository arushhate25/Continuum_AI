import { EvidenceViewer } from "./EvidenceViewer";
import { StatusBadge } from "./StatusBadge";
import type { ClaimView, Handover } from "@/lib/types";

function Item({ claim }: { claim: ClaimView }) {
  return (
    <div className="item">
      <div className="row" style={{ marginBottom: 4 }}>
        <StatusBadge status={claim.status} />
        {claim.redacted && <span className="badge badge-neutral">redacted</span>}
      </div>
      {claim.redacted ? (
        <p className="redacted">{claim.placeholder ?? "Supported by restricted source(s)"}</p>
      ) : (
        <>
          <p>{claim.statement}</p>
          {claim.notes.length > 0 && (
            <ul className="notes">
              {claim.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
          <details>
            <summary className="small">Evidence ({claim.evidence.length})</summary>
            <EvidenceViewer evidence={claim.evidence} sources={[]} />
          </details>
        </>
      )}
    </div>
  );
}

function Section({ title, items, empty }: { title: string; items: ClaimView[]; empty: string }) {
  return (
    <div className="section">
      <h3>
        {title} <span className="muted small">({items.length})</span>
      </h3>
      {items.length === 0 ? <p className="muted small">{empty}</p> : items.map((c) => <Item key={c.id} claim={c} />)}
    </div>
  );
}

export function HandoverView({ handover }: { handover: Handover }) {
  const r = handover.readiness;
  const pct = Math.round((r.score ?? 0) * 100);
  return (
    <div>
      {r.approved === 0 && (
        <div className="banner banner-warn">
          Nothing has been approved yet. A reviewer must approve claims before they appear in a handover.
        </div>
      )}

      <div className="card">
        <h2>Handover for: {handover.role}</h2>
        <p className="small muted">
          Built only from approved claims. Anything that depends on a source you are not allowed to read is redacted.
          Gaps and conflicts are shown, not hidden.
        </p>
        <div className="row small" style={{ marginBottom: 6 }}>
          <b>Readiness {pct}%</b>
          <span className="muted">
            {r.verified} verified · {r.approved} approved · {r.unresolved ?? 0} unresolved · {r.total} total claims
          </span>
        </div>
        <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Handover readiness">
          <span style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="grid2" style={{ gridTemplateColumns: "minmax(260px, 340px) 1fr" }}>
        <div className="card">
          <div className="section">
            <h3>Day 1</h3>
            {handover.day1.length === 0 ? (
              <p className="muted small">Nothing yet.</p>
            ) : (
              <ul>
                {handover.day1.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="section">
            <h3>Week 1</h3>
            {handover.week1.length === 0 ? (
              <p className="muted small">Nothing yet.</p>
            ) : (
              <ul>
                {handover.week1.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="card">
          <Section title="Decisions" items={handover.decisions} empty="No approved decisions." />
          <Section title="Ownership" items={handover.ownership} empty="No approved ownership claims." />
          <Section title="Risks" items={handover.risks} empty="No approved risks." />
          <Section title="Dependencies" items={handover.dependencies} empty="No approved dependencies." />
          <Section title="Unfinished work" items={handover.unfinished_work} empty="No approved tasks." />
          <Section title="Open questions and gaps" items={handover.open_questions} empty="No open items." />
        </div>
      </div>
    </div>
  );
}
