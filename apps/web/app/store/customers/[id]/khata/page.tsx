/**
 * Khata — transaction history (auth-only, READ-ONLY).
 *
 * Paginated entries + summary cards, using khataSummary + khataEntries only.
 * Backend Khata has NO POST endpoints (router.py exposes only GET
 * summary/entries; balance is server-side), so the four write actions below
 * (credit sale / payment received / debit adjustment / credit adjustment)
 * are rendered DISABLED with a Marathi explanation: entries are created
 * automatically by orders/payments — the frontend never edits balances.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type KhataEntry, type KhataSummary } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";
import { formatPaise, khataEntryTypeLabel } from "../../../../../lib/khata";

const PAGE_SIZE = 20;

const DISABLED_ACTIONS = [
  "उधार विक्री Add credit sale",
  "पेमेंट मिळाले Payment received",
  "डेबिट समायोजन Debit adjustment",
  "क्रेडिट समायोजन Credit adjustment",
];

export default function CustomerKhataPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const id = params.id;
  const isSelf = id === "self";
  const [summary, setSummary] = useState<KhataSummary | null>(null);
  const [entries, setEntries] = useState<KhataEntry[] | null>(null);
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    (async () => {
      try {
        const [s, list] = await Promise.all([api.khataSummary(token), api.khataEntries(token, 100, 0)]);
        setSummary(s);
        setEntries(list.entries);
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

  const totalPages = scoped ? Math.max(1, Math.ceil(scoped.length / PAGE_SIZE)) : 1;
  const safePage = Math.min(page, totalPages - 1);
  const visible = scoped ? scoped.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE) : null;

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/store/customers/${id}`}>← तपशील Details</Link>
        </p>
        <h1>📒 व्यवहार इतिहास Transaction history</h1>
        {error ? <p className="form-error">{error}</p> : null}

        <section className="card">
          <h2>गोषवारा Summary</h2>
          {summary ? (
            <>
              <p>
                शिल्लक Outstanding: ₹{formatPaise(summary.outstanding_paise)}
              </p>
              <p>
                एकूण उधार Total debits: ₹{formatPaise(summary.total_debits_paise)}
              </p>
              <p>
                एकूण जमा Total credits: ₹{formatPaise(summary.total_credits_paise)}
              </p>
              <p>
                एकूण पेमेंट Total payments: ₹{formatPaise(summary.total_payments_paise)}
              </p>
              <p>
                पत मर्यादा Credit limit: ₹{formatPaise(summary.credit_limit_paise)}
              </p>
              {summary.over_limit ? <p className="form-error">⚠️ मर्यादेबाहेर Over limit</p> : null}
            </>
          ) : (
            <p className="muted">{t.loading}</p>
          )}
        </section>

        <section className="card">
          <h2>नोंद Actions</h2>
          {DISABLED_ACTIONS.map((label) => (
            <p key={label}>
              <button className="btn-secondary" type="button" disabled title="सर्व्हर-चालित — हाताने बदल नाही">
                {label}
              </button>
            </p>
          ))}
          <p className="muted">
            नोंदी फक्त ऑर्डर/पेमेंटमधून आपोआप तयार होतात — हाताने बदलता येत नाही. शिल्लक
            सर्व्हरवरच मोजली जाते. (Entries are created automatically by orders/payments;
            balances are server-side and never edited here.)
          </p>
        </section>

        {visible === null ? (
          <p className="muted">{t.loading}</p>
        ) : visible.length === 0 ? (
          <p className="muted">व्यवहार नाहीत (No transactions).</p>
        ) : (
          <>
            {visible.map((e) => (
              <section className="card" key={e.id}>
                <p>
                  <strong>{khataEntryTypeLabel(e.entry_type)}</strong> · ₹{formatPaise(e.amount_paise)}
                </p>
                <p className="muted">
                  शिल्लकनंतर Balance after: ₹{formatPaise(e.balance_after_paise)} · {e.created_at.slice(0, 10)}
                </p>
                {e.order_id ? (
                  <p className="muted">ऑर्डर Order: {e.order_id.slice(0, 8)}…</p>
                ) : null}
                {e.note ? <p className="muted">नोंद Note: {e.note}</p> : null}
              </section>
            ))}
            <section className="card">
              <p className="muted">
                पान Page {safePage + 1} / {totalPages}
              </p>
              <div className="card-actions">
                <button
                  className="btn-secondary"
                  type="button"
                  disabled={safePage <= 0}
                  onClick={() => setPage(safePage - 1)}
                >
                  ← मागील Prev
                </button>
                <button
                  className="btn-secondary"
                  type="button"
                  disabled={safePage >= totalPages - 1}
                  onClick={() => setPage(safePage + 1)}
                >
                  पुढील Next →
                </button>
              </div>
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
