/**
 * Khata — customer/ledger detail (auth-only, READ-ONLY).
 *
 * [id] is "self" (the farmer's own general ledger) or an order_id derived
 * client-side from khata entries (see ../page.tsx). Uses khataSummary +
 * khataEntries only — no customer endpoint exists. Display only.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type KhataEntry, type KhataSummary } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise, signedDelta } from "../../../../lib/khata";

export default function CustomerDetailPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const id = params.id;
  const isSelf = id === "self";
  const [summary, setSummary] = useState<KhataSummary | null>(null);
  const [entries, setEntries] = useState<KhataEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    (async () => {
      try {
        const [s, page] = await Promise.all([api.khataSummary(token), api.khataEntries(token, 100, 0)]);
        setSummary(s);
        setEntries(page.entries);
        setError(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    })();
  }, []);

  const scoped = useMemo(() => {
    if (!entries) return null;
    return isSelf ? entries : entries.filter((e) => e.order_id === id);
  }, [entries, id, isSelf]);

  const groupDues = useMemo(() => {
    if (!scoped) return 0;
    // Read-only: dues in this ledger = debits − credits − payments.
    return scoped.reduce((acc, e) => acc + -signedDelta(e.entry_type, e.amount_paise), 0);
  }, [scoped]);

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/customers">← खाता (Khata)</Link>
        </p>
        <h1>{isSelf ? "📒 माझे खाते (My ledger)" : `📒 ऑर्डर खाते (Order ${id.slice(0, 8)}…)`}</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {!summary || scoped === null ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h2>शिल्लक Outstanding</h2>
              <p className="farm-area">₹{formatPaise(summary.outstanding_paise)}</p>
              <p>
                या खात्यातील देणे Ledger dues: ₹{formatPaise(groupDues)}
              </p>
              <p>
                पत मर्यादा Credit limit: ₹{formatPaise(summary.credit_limit_paise)}
              </p>
              {summary.over_limit ? (
                <p className="form-error">⚠️ मर्यादेबाहेर Over limit — नवीन उधार नाही (no new credit).</p>
              ) : null}
              <p className="muted">नोंदी Entries: {scoped.length}</p>
            </section>

            <section className="card">
              <p>
                <Link href={`/store/customers/${id}/khata`}>व्यवहार इतिहास Transaction history →</Link>
              </p>
              {!isSelf ? (
                <p>
                  <Link href={`/store/orders/${id}`}>ऑर्डर पहा View order →</Link>
                </p>
              ) : null}
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
