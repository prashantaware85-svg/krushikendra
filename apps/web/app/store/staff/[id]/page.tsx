/**
 * Staff detail (Step 17, admin only): master record + audit note.
 * Backend is authoritative — 403 hides management actions, 404 means
 * cross-store-or-missing. Delete is soft (active=false), never a hard drop.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type StaffMember } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { staffMobile, staffRoleLabel } from "../../../../lib/staff";

export default function StaffDetailPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [member, setMember] = useState<StaffMember | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setMember(await api.getStaff(token, params.id));
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
        setError("प्रवेश नाही (Access restricted) — फक्त प्रशासक Admin only.");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function onToggleActive() {
    const token = getStoredToken();
    if (!token || busy || !member) return;
    setBusy(true);
    try {
      const updated = member.is_active
        ? await api.deactivateStaff(token, member.id)
        : await api.activateStaff(token, member.id);
      setMember(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    const token = getStoredToken();
    if (!token || busy || !member) return;
    setBusy(true);
    try {
      await api.deleteStaff(token, member.id);
      setError(null);
      router.push("/store/staff");
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
          <Link href="/store/staff">← कर्मचारी Staff</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!member ? (
          forbidden ? null : <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h1>👤 {member.display_name ?? staffMobile(member)}</h1>
              <p className="muted">मोबाईल Mobile: {staffMobile(member)}</p>
              <p>
                <span className="badge">{staffRoleLabel(member.role)}</span>
                {" · "}
                {member.is_active ? "सक्रिय Active" : "बंद Inactive"}
              </p>
              <p className="muted">सामील Joined: {member.created_at ? member.created_at.slice(0, 10) : "—"}</p>
              {forbidden ? null : (
                <p>
                  <Link href={`/store/staff/${member.id}/edit`}>{t.edit}</Link>
                  {" · "}
                  <button type="button" className="link-btn-plain" disabled={busy} onClick={onToggleActive}>
                    {busy ? t.loading : member.is_active ? "बंद करा Deactivate" : "सक्रिय करा Activate"}
                  </button>
                  {" · "}
                  <button type="button" className="link-btn-plain" disabled={busy} onClick={onDelete}>
                    काढा Remove (soft)
                  </button>
                </p>
              )}
            </section>
            <section className="card">
              <h2>नोंद Audit Note</h2>
              <p className="muted">
                भूमिका/स्थिती बदल audit log मध्ये नोंदवले जातात — सर्व बदल server-side तपासले जातात.
                Role/status changes are audit-logged server-side; removal is soft (active=false), never a hard delete.
              </p>
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
