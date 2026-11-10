"use client";

import { useCallback, useEffect, useState } from "react";
import { AuditLog } from "@/components/AuditLog";
import { HandoverView } from "@/components/HandoverView";
import { Overview } from "@/components/Overview";
import { ReviewPanel } from "@/components/ReviewPanel";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { API_BASE, api, errorMessage, waitForBackend } from "@/lib/api";
import { isRole, isStaff } from "@/lib/types";
import type { AuditEntry, ClaimView, Handover, Role, Source, StatusInfo } from "@/lib/types";

type Tab = "overview" | "review" | "handover" | "audit";

const TAB_LABELS: Record<Tab, string> = {
  overview: "1 · Connect & extract",
  review: "2 · Review",
  handover: "3 · Handover",
  audit: "4 · Audit log",
};

function allowedTabs(role: Role): Tab[] {
  if (role === "successor") return ["overview", "handover"];
  if (role === "leaver") return ["overview", "review", "handover"];
  return ["overview", "review", "handover", "audit"];
}

export default function Home() {
  const [role, setRole] = useState<Role>("reviewer");
  const [tab, setTab] = useState<Tab>("overview");
  const [ready, setReady] = useState(false);
  const [slow, setSlow] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [claims, setClaims] = useState<ClaimView[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [handover, setHandover] = useState<Handover | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  // Remember the chosen role across reloads (storage can be unavailable).
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("continuum-role");
      if (isRole(saved)) setRole(saved);
    } catch {
      /* ignore */
    }
  }, []);

  // Free hosting sleeps: wait for the backend instead of showing broken pages.
  useEffect(() => {
    let cancelled = false;
    waitForBackend(() => {
      if (!cancelled) setSlow(true);
    }).then((ok) => {
      if (cancelled) return;
      setReady(ok);
      setUnreachable(!ok);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const changeRole = (r: Role) => {
    setRole(r);
    setHandover(null);
    try {
      window.localStorage.setItem("continuum-role", r);
    } catch {
      /* ignore */
    }
    if (!allowedTabs(r).includes(tab)) setTab("handover");
  };

  // Load what the current tab needs.
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        const st = await api.status(role);
        if (cancelled) return;
        setStatus(st);
        if (role !== "successor" && (tab === "overview" || tab === "review")) {
          const [cl, src] = await Promise.all([api.claims(role), api.sources(role)]);
          if (cancelled) return;
          setClaims(cl);
          setSources(src);
        }
        if (tab === "handover") {
          const h = await api.handover(role);
          if (!cancelled) setHandover(h);
        }
        if (tab === "audit" && isStaff(role)) {
          const a = await api.audit(role);
          if (!cancelled) setAudit(a);
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, role, tab, reload]);

  const bump = useCallback(() => setReload((n) => n + 1), []);

  async function loadDemo() {
    setBusy("load");
    setError(null);
    try {
      await api.loadDemo(role);
      setClaims([]);
      setHandover(null);
      bump();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function extract(provider?: string) {
    setBusy(provider === "mock" ? "extract-mock" : "extract");
    setError(null);
    try {
      await api.extract(role, provider);
      bump();
      setTab("review");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  const tabs = allowedTabs(role);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <h1>Continuum AI</h1>
          <p>Evidence-backed, permission-aware knowledge handover</p>
        </div>
        <RoleSwitcher role={role} onChange={changeRole} />
      </header>

      {!ready && !unreachable && (
        <div className="banner banner-info" role="status">
          {slow
            ? "Server waking up… free hosting can take up to a minute on the first visit. This page will continue by itself."
            : "Connecting to the server…"}
        </div>
      )}
      {unreachable && (
        <div className="banner banner-bad" role="alert">
          Cannot reach the server at {API_BASE}. Check that the backend is running and that NEXT_PUBLIC_API_URL and CORS are set correctly, then reload.
        </div>
      )}
      {error && ready && (
        <div className="banner banner-bad" role="alert">
          {error}
        </div>
      )}

      <nav className="tabs" role="tablist" aria-label="Workflow steps">
        {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            className="tab"
            aria-selected={tab === t}
            disabled={!tabs.includes(t)}
            onClick={() => setTab(t)}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </nav>

      {ready && tab === "overview" && (
        <Overview
          role={role}
          status={status}
          busy={busy}
          onLoadDemo={loadDemo}
          onExtract={extract}
          onGoReview={() => setTab("review")}
        />
      )}
      {ready && tab === "review" && role !== "successor" && (
        <ReviewPanel role={role} claims={claims} sources={sources} onChanged={bump} />
      )}
      {ready && tab === "handover" && (handover ? <HandoverView handover={handover} /> : <p className="muted">Loading handover…</p>)}
      {ready && tab === "audit" && isStaff(role) && <AuditLog entries={audit} />}

      <p className="footer">
        Demo uses synthetic data only. The role switcher is a demo feature, not real sign-in; access rules are enforced by the server.
        Quote checking proves evidence exists, not that a conclusion is correct, which is why human review is required.
      </p>
    </main>
  );
}
