/**
 * Edit staff (Step 17, admin only): role + active form.
 * Only {role, is_active} are sent (PUT contract) — identity fields are read-only.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type StaffMember, type StaffRole } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";
import { staffMobile } from "../../../../../lib/staff";

export default function StaffEditPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [member, setMember] = useState<StaffMember | null>(null);
  const [role, setRole] = useState<StaffRole>("store_staff");
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const m = await api.getStaff(token, params.id);
      setMember(m);
      setRole((m.role as StaffRole) ?? "store_staff");
      setIsActive(m.is_active);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy || !member) return;
    setBusy(true);
    try {
      const updated = await api.updateStaff(token, member.id, { role, is_active: isActive });
      setError(null);
      router.push(`/store/staff/${updated.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={member ? `/store/staff/${member.id}` : "/store/staff"}>← मागे Back</Link>
        </p>
        <h1>बदल करा Edit Staff</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {!member ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <section className="card">
            <p className="muted">{member.display_name ?? staffMobile(member)} · {staffMobile(member)}</p>
            <form onSubmit={onSave}>
              <label>भूमिका Role<br />
                <select value={role} onChange={(e) => setRole(e.target.value as StaffRole)}>
                  <option value="store_staff">दुकान कर्मचारी Store Staff</option>
                  <option value="store_manager">दुकान व्यवस्थापक Store Manager</option>
                  <option value="admin">प्रशासक Admin</option>
                </select>
              </label><br />
              <label>
                <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
                {" "}सक्रिय Active
              </label><br />
              <button className="btn" type="submit" disabled={busy}>{busy ? t.loading : t.save}</button>
              {" "}
              <button className="btn" type="button" onClick={() => router.push(`/store/staff/${member.id}`)}>
                {t.cancel}
              </button>
            </form>
          </section>
        )}
      </main>
    </AuthGate>
  );
}
