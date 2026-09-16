/**
 * New staff (Step 17, admin only): mobile/user + role + active.
 * No password fields — the member must already have an account (user not
 * found surfaces a 404 which clears on the next input change).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type StaffRole } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";

export default function NewStaffPage() {
  const { t } = useAuth();
  const router = useRouter();
  const [mobile, setMobile] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<StaffRole>("store_staff");
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function clearErrorOnChange() {
    if (error) setError(null);
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy) return;
    if (!mobile.trim() && !userId.trim()) {
      setError("मोबाईल किंवा User ID द्या Provide mobile_number or user_id.");
      return;
    }
    setBusy(true);
    try {
      const created = await api.createStaff(token, {
        mobile_number: mobile.trim() || null,
        user_id: userId.trim() || null,
        role,
      });
      // POST carries no active flag — apply the toggle with a second call.
      if (!isActive) {
        await api.deactivateStaff(token, created.id);
      }
      setError(null);
      router.push(`/store/staff/${created.id}`);
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
        <h1>＋ नवीन कर्मचारी New Staff</h1>
        {error ? <p className="form-error">{error}</p> : null}
        <section className="card">
          <form onSubmit={onCreate}>
            <label>मोबाईल Mobile<br />
              <input
                value={mobile}
                onChange={(e) => { setMobile(e.target.value); clearErrorOnChange(); }}
                placeholder="10-अंकी mobile"
              />
            </label><br />
            <label>User ID (ऐच्छिक optional)<br />
              <input
                value={userId}
                onChange={(e) => { setUserId(e.target.value); clearErrorOnChange(); }}
                placeholder="user UUID"
              />
            </label><br />
            <label>भूमिका Role<br />
              <select value={role} onChange={(e) => { setRole(e.target.value as StaffRole); clearErrorOnChange(); }}>
                <option value="store_staff">दुकान कर्मचारी Store Staff</option>
                <option value="store_manager">दुकान व्यवस्थापक Store Manager</option>
                <option value="admin">प्रशासक Admin</option>
              </select>
            </label><br />
            <label>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => { setIsActive(e.target.checked); clearErrorOnChange(); }}
              />
              {" "}सक्रिय Active
            </label><br />
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t.loading : "तयार करा Create"}
            </button>
          </form>
        </section>
      </main>
    </AuthGate>
  );
}
