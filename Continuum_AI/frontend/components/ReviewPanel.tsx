"use client";

import { useEffect, useMemo, useState } from "react";
import { EvidenceViewer } from "./EvidenceViewer";
import { StateBadge, StatusBadge } from "./StatusBadge";
import { api, errorMessage } from "@/lib/api";
import { isStaff } from "@/lib/types";
import type { ClaimDetail, ClaimView, Role, Source } from "@/lib/types";

interface Props {
  role: Role;
  claims: ClaimView[];
  sources: Source[];
  onChanged: () => void;
}

const NO_EVIDENCE_NOTE = "verifier: no quote found";

export function ReviewPanel({ role, claims, sources, onChanged }: Props) {
  const staff = isStaff(role);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fStatus, setFStatus] = useState("all");
  const [fState, setFState] = useState("all");
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(
    () =>
      claims.filter(
        (c) =>
          (fStatus === "all" || c.status === fStatus) &&
          (fState === "all" || c.review_state === fState) &&
          (query === "" || (c.statement ?? "").toLowerCase().includes(query.toLowerCase())),
      ),
    [claims, fStatus, fState, query],
  );

  useEffect(() => {
    if (claims.length > 0 && (selectedId === null || !claims.some((c) => c.id === selectedId))) {
      setSelectedId(claims[0].id);
    }
  }, [claims, selectedId]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedId) {
      setDetail(null);
      return;
    }
    api
      .claim(role, selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [role, selectedId, claims]);

  const selected: ClaimView | undefined = detail?.claim ?? claims.find((c) => c.id === selectedId);
  const hasNoEvidence = !!selected?.notes.some((n) => n.startsWith(NO_EVIDENCE_NOTE));

  async function act(action: "approve" | "reject" | "edit", statement?: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.review(role, selected.id, action, statement);
      setEditing(false);
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const bulkCandidates = claims.filter((c) => c.status === "Verified" && c.review_state === "draft" && !c.redacted);

  async function approveVerified() {
    setBusy(true);
    setError(null);
    try {
      for (const c of bulkCandidates) {
        await api.review(role, c.id, "approve");
      }
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (claims.length === 0) {
    return (
      <div className="card">
        <h2>No claims yet</h2>
        <p className="muted">Go to the first tab and run extraction (live AI or the offline sample).</p>
      </div>
    );
  }

  return (
    <div>
      {!staff && (
        <div className="banner banner-info">
          Read-only: only the Reviewer and Admin roles can approve, reject or edit claims. Claims that depend on
          restricted sources are hidden for your role.
        </div>
      )}
      {error && <div className="banner banner-bad" role="alert">{error}</div>}

      <div className="grid2">
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Claims ({filtered.length})</h3>
            {staff && (
              <button type="button" className="btn small" disabled={busy || bulkCandidates.length === 0} onClick={approveVerified}>
                Approve all Verified ({bulkCandidates.length})
              </button>
            )}
          </div>
          <div className="filters">
            <select aria-label="Filter by status" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
              <option value="all">All statuses</option>
              <option value="Verified">Verified</option>
              <option value="Inferred">Inferred</option>
              <option value="Conflicting">Conflicting</option>
              <option value="Missing">Missing</option>
            </select>
            <select aria-label="Filter by review state" value={fState} onChange={(e) => setFState(e.target.value)}>
              <option value="all">All states</option>
              <option value="draft">Awaiting review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
            <input aria-label="Search claims" placeholder="Search…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <ul className="claim-list">
            {filtered.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className="claim-item"
                  aria-current={c.id === selectedId}
                  onClick={() => {
                    setSelectedId(c.id);
                    setEditing(false);
                    setError(null);
                  }}
                >
                  <div className="meta">
                    <span className="badge badge-neutral">{c.type}</span>
                    <StatusBadge status={c.status} />
                    <StateBadge state={c.review_state} />
                  </div>
                  <div className={c.redacted ? "text redacted" : "text"}>
                    {c.redacted ? c.placeholder : c.statement}
                  </div>
                </button>
              </li>
            ))}
            {filtered.length === 0 && <li className="muted small">No claims match these filters.</li>}
          </ul>
        </div>

        <div className="card">
          {!selected ? (
            <p className="muted">Select a claim.</p>
          ) : (
            <div>
              <div className="row" style={{ marginBottom: 8 }}>
                <span className="badge badge-neutral">{selected.type}</span>
                <StatusBadge status={selected.status} />
                <StateBadge state={selected.review_state} />
                <span className="small muted">
                  confidence {Math.round(selected.confidence * 100)}% · version {selected.version} · id {selected.id}
                </span>
              </div>

              {selected.redacted ? (
                <p className="redacted">{selected.placeholder}</p>
              ) : (
                <h3 style={{ fontSize: 17 }}>{selected.statement}</h3>
              )}

              {selected.notes.length > 0 && (
                <div>
                  <div className="small muted">System flags</div>
                  <ul className="notes">
                    {selected.notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}

              {selected.conflicts_with.length > 0 && (
                <p className="small">
                  Conflicts with:{" "}
                  {selected.conflicts_with.map((id) => (
                    <button key={id} type="button" className="linkish" onClick={() => setSelectedId(id)} style={{ marginRight: 8 }}>
                      {id}
                    </button>
                  ))}
                </p>
              )}

              <h4 style={{ marginTop: 12 }}>Evidence</h4>
              <EvidenceViewer evidence={selected.evidence} sources={sources} />

              {staff && !selected.redacted && (
                <div style={{ marginTop: 12 }}>
                  {hasNoEvidence && (
                    <div className="banner banner-warn">
                      No quote for this claim was found in its source, so it cannot be approved. Edit it or reject it.
                    </div>
                  )}
                  {editing ? (
                    <div>
                      <textarea
                        className="edit"
                        aria-label="Edit statement"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                      />
                      <div className="row" style={{ marginTop: 6 }}>
                        <button type="button" className="btn btn-primary" disabled={busy || editText.trim() === ""} onClick={() => act("edit", editText)}>
                          Save edit
                        </button>
                        <button type="button" className="btn" onClick={() => setEditing(false)}>
                          Cancel
                        </button>
                      </div>
                      <p className="small muted">An edited claim is no longer machine-verified, so a Verified claim becomes Inferred.</p>
                    </div>
                  ) : (
                    <div className="row">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy || hasNoEvidence || selected.review_state === "approved"}
                        onClick={() => act("approve")}
                      >
                        Approve
                      </button>
                      <button type="button" className="btn btn-danger" disabled={busy || selected.review_state === "rejected"} onClick={() => act("reject")}>
                        Reject
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() => {
                          setEditText(selected.statement ?? "");
                          setEditing(true);
                        }}
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </div>
              )}

              {detail && detail.versions.length > 0 && (
                <details style={{ marginTop: 12 }}>
                  <summary className="small">Version history ({detail.versions.length})</summary>
                  <ul className="small">
                    {detail.versions.map((v, i) => (
                      <li key={i}>
                        v{v.version ?? "?"} · {v.review_state ?? ""} · {v.snapshot_at ?? ""}
                        <div className="muted">{v.statement}</div>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
