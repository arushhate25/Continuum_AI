const ICON: Record<string, string> = {
  Verified: "✓",
  Inferred: "≈",
  Conflicting: "⚠",
  Missing: "?",
};

const HINT: Record<string, string> = {
  Verified: "The quote was found in an authorised source.",
  Inferred: "A conclusion drawn from evidence. Not a proven fact.",
  Conflicting: "Two sources disagree. Both are shown.",
  Missing: "Important, but no usable evidence was found.",
};

// Status is shown with an icon and a word, never by colour alone.
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge badge-${status.toLowerCase()}`} title={HINT[status] ?? status}>
      <span aria-hidden="true">{ICON[status] ?? "•"}</span> {status}
    </span>
  );
}

export function StateBadge({ state }: { state: string }) {
  const cls = state === "approved" ? "badge-approved" : state === "rejected" ? "badge-rejected" : "badge-neutral";
  const label = state === "draft" ? "awaiting review" : state;
  return <span className={`badge ${cls}`}>{label}</span>;
}
