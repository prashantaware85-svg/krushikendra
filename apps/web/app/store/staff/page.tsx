/**
 * Staff list (Step 17, auth-only + backend-authoritative RBAC).
 * Admin only: non-admin list fetch returns 403 — actions hidden, notice shown.
 * Search + role filter are client-side (GET /store/staff takes no query params).
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type StaffMember, type StaffRole } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { staffMobile, staffRoleLabel } from "../../../lib/staff";

const ROLE_OPTIONS: StaffRole[] = ["admin", "store_manager", "store_staff"];

export default function StaffListPage() {
  const { t } = useAuth();
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setStaff(await api.listStaff(token));
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setStaff([]);
        setForbidden(true);
        setError("प्रवेश नाही (Access restricted) — फक्त प्रशासक Admin only.");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onToggleActive(s: StaffMember) {
    const token = getStoredToken();
    if (!token || busyId) return;
    setBusyId(s.id);
    try {
      const updated = s.is_active
        ? await api.deactivateStaff(token, s.id)
        : await api.activateStaff(token, s.id);
      setStaff((prev) => prev?.map((m) => (m.id === updated.id ? updated : m)) ?? [updated]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusyId(null);
    }
  }

  async function onChangeRole(s: StaffMember, role: string) {
    const token = getStoredToken();
    if (!token || busyId || role === s.role) return;
    setBusyId(s.id);
    try {
      const updated = await api.updateStaff(token, s.id, { role: role as StaffRole });
      setStaff((prev) => prev?.map((m) => (m.id === updated.id ? updated : m)) ?? [updated]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusyId(null);
    }
  }

  const q = search.trim().toLowerCase();
  const visible = (staff ?? []).filter((s) => {
    if (roleFilter && s.role !== roleFilter) return false;
    if (!q) return true;
    const hay = `${s.display_name ?? ""} ${staffMobile(s)}`.toLowerCase();
    return hay.includes(q);
  });

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>👥 कर्मचारी Staff</h1>
        <p>
          <Link href="/store/inventory">← साठा Inventory</Link>
          {" · "}
          <Link href="/store/staff/orders">Orders / ऑर्डर →</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {forbidden ? null : (
          <p>
            <Link className="btn" href="/store/staff/new">＋ नवीन कर्मचारी Add Staff</Link>
          </p>
        )}
        <form onSubmit={(e) => e.preventDefault()}>
          <input
            type="search"
            placeholder="शोधा Search (नाव/mobile)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {" "}
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">सर्व भूमिका All roles</option>
            <option value="admin">प्रशासक Admin</option>
            <option value="store_manager">दुकान व्यवस्थापक Store Manager</option>
            <option value="store_staff">दुकान कर्मचारी Store Staff</option>
          </select>
        </form>
        {staff === null ? (
          <p className="muted">{t.loading}</p>
        ) : forbidden ? (
          <p className="muted">प्रवेश नाही (Access restricted) — यादी फक्त प्रशासक पाहू शकतो.</p>
        ) : visible.length === 0 ? (
          <p className="muted">कर्मचारी नाहीत No staff yet.</p>
        ) : (
          <div className="grid">
            {visible.map((s) => (
              <article className="card" key={s.id}>
                <h2>{s.display_name ?? staffMobile(s)}</h2>
                <p className="muted">मोबाईल Mobile: {staffMobile(s)}</p>
                <p>
                  <span className="badge">{staffRoleLabel(s.role)}</span>
                  {" · "}
                  {s.is_active ? "सक्रिय Active" : "बंद Inactive"}
                </p>
                <p className="muted">सामील Joined: {s.created_at ? s.created_at.slice(0, 10) : "—"}</p>
                <p>
                  <Link href={`/store/staff/${s.id}`}>{t.viewDetails} →</Link>
                  {" · "}
                  <Link href={`/store/staff/${s.id}/edit`}>{t.edit}</Link>
                </p>
                <p>
                  <label>भूमिका Role:<br />
                    <select
                      value={s.role}
                      disabled={busyId === s.id}
                      onChange={(e) => onChangeRole(s, e.target.value)}
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r} value={r}>{staffRoleLabel(r)}</option>
                      ))}
                    </select>
                  </label>
                  {" "}
                  <button
                    type="button"
                    className="btn"
                    disabled={busyId === s.id}
                    onClick={() => onToggleActive(s)}
                  >
                    {busyId === s.id ? t.loading : s.is_active ? "बंद करा Deactivate" : "सक्रिय करा Activate"}
                  </button>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
