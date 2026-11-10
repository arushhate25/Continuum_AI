import type { AuditEntry } from "@/lib/types";

export function AuditLog({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return <p className="muted">No audit entries yet.</p>;
  }
  const rows = [...entries].reverse();
  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <h2>Audit log</h2>
      <p className="small muted">Every import, extraction, review decision and handover view is recorded.</p>
      <table className="audit">
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Role</th>
            <th>Action</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e, i) => (
            <tr key={i}>
              <td>{e.ts}</td>
              <td>{e.role}</td>
              <td>{e.action}</td>
              <td>
                <code>{JSON.stringify(e.detail)}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
