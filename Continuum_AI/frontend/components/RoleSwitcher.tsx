import { ROLES, isRole } from "@/lib/types";
import type { Role } from "@/lib/types";

export function RoleSwitcher({ role, onChange }: { role: Role; onChange: (r: Role) => void }) {
  const current = ROLES.find((r) => r.value === role);
  return (
    <div className="role-box">
      <label htmlFor="role-select">Viewing as</label>
      <select
        id="role-select"
        value={role}
        onChange={(e) => {
          const v = e.target.value;
          if (isRole(v)) onChange(v);
        }}
      >
        {ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <span className="role-blurb">{current?.blurb}</span>
    </div>
  );
}
