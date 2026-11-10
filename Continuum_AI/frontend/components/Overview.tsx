import { StatusBadge } from "./StatusBadge";
import { isStaff } from "@/lib/types";
import type { Role, StatusInfo } from "@/lib/types";

interface Props {
  role: Role;
  status: StatusInfo | null;
  busy: string | null;
  onLoadDemo: () => void;
  onExtract: (provider?: string) => void;
  onGoReview: () => void;
}

export function Overview({ role, status, busy, onLoadDemo, onExtract, onGoReview }: Props) {
  const staff = isStaff(role);
  const hasClaims = (status?.claims ?? 0) > 0;
  return (
    <div>
      <div className="card">
        <h2>Knowledge handover you can verify</h2>
        <p className="muted">
          When someone leaves, Continuum AI rebuilds the project state from authorised sources. Every claim links to an
          exact quote, is labelled Verified, Inferred, Conflicting or Missing, is approved by a human, and is shown only
          to people allowed to see it.
        </p>
        <ol className="steps">
          <li><b>Connect</b>: import GitHub issues, pull requests and comments (a synthetic demo project here).</li>
          <li><b>Reconstruct</b>: AI extracts decisions, owners, risks, dependencies and unfinished work, with quotes.</li>
          <li><b>Verify</b>: a deterministic check confirms each quote exists in its source. Failures are downgraded.</li>
          <li><b>Review</b>: a reviewer approves, rejects or edits every claim. Changes are versioned.</li>
          <li><b>Handover</b>: the successor gets a role-based plan from approved claims only, with redactions.</li>
        </ol>
      </div>

      <div className="card">
        <h2>Project: {status?.project ?? "no data loaded"}</h2>
        {status && (
          <div className="stats">
            <div className="stat"><b>{status.sources}</b>sources</div>
            <div className="stat"><b>{status.claims}</b>claims</div>
            <div className="stat"><b>{status.approved}</b>approved</div>
            <div className="stat"><b>{status.rejected}</b>rejected</div>
          </div>
        )}
        {status && hasClaims && (
          <div className="row" style={{ marginBottom: 8 }}>
            {Object.entries(status.by_status).map(([s, n]) => (
              <span key={s} className="row" style={{ gap: 4 }}>
                <StatusBadge status={s} /> <b>{n}</b>
              </span>
            ))}
          </div>
        )}
        {status?.extraction_provider && (
          <p className="small muted">
            Claims came from: <b>{status.extraction_provider}</b>
            {status.extracted_at ? ` at ${status.extracted_at}` : ""}
          </p>
        )}

        <div className="row">
          <button type="button" className="btn" disabled={!staff || busy !== null} onClick={onLoadDemo}>
            {busy === "load" ? "Loading…" : "1. Load demo project"}
          </button>
          <button type="button" className="btn btn-primary" disabled={!staff || busy !== null || !status?.sources} onClick={() => onExtract(undefined)}>
            {busy === "extract" ? "Extracting… (can take ~30s)" : "2. Extract with live AI"}
          </button>
          <button type="button" className="btn" disabled={!staff || busy !== null || !status?.sources} onClick={() => onExtract("mock")}>
            {busy === "extract-mock" ? "Loading sample…" : "2. Or use offline sample"}
          </button>
          {hasClaims && (
            <button type="button" className="btn" onClick={onGoReview}>
              3. Review claims →
            </button>
          )}
        </div>
        {!staff && (
          <p className="small muted" style={{ marginTop: 8 }}>
            Only the Admin and Reviewer roles can load data and run extraction. Switch role at the top right.
          </p>
        )}
        <p className="small muted" style={{ marginTop: 8 }}>
          The offline sample replays a saved model response (no AI call). It includes deliberately wrong quotes so you can
          see the verifier catch them. The label above always says which source the claims came from.
        </p>
      </div>

      <div className="card">
        <h3>Try it in four steps</h3>
        <ol className="steps">
          <li>Click <b>Extract</b> (live AI, or the offline sample).</li>
          <li>Open <b>Review</b>. Click a claim, read the quote, use <b>Show full source</b>, then approve, reject or edit. <b>Approve all Verified</b> is a shortcut; approve Conflicting and Missing claims one by one so they reach the handover as open items.</li>
          <li>Switch <b>Viewing as</b> to <b>Successor</b>.</li>
          <li>Open <b>Handover</b>. You see only approved claims; the incident that depends on a restricted source is redacted.</li>
        </ol>
      </div>
    </div>
  );
}
