/**
 * Khata ledger (auth-only): outstanding summary + transactions + payment history.
 *
 * Read-only display from the existing /api/v1/khata endpoints — the frontend
 * never computes or edits balances (see lib/khata.ts). Payment history is
 * entries with entry_type === "payment".
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type KhataEntry,
  type KhataSummary,
} from "../../lib/api";
import { formatPaise, khataEntryTypeLabel } from "../../lib/khata";
import { useAuth } from "../../lib/auth";

const PAGE_SIZE = 20;

export default function KhataPage() {
  const { t } = useAuth();
  const [summary, setSummary] = useState<KhataSummary | null | undefined>(undefined);
  const [entries, setEntries] = useState<KhataEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEntries = useCallback(async (offset: number) => {
    const token = getStoredToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      if (offset === 0) {
        const [s, p] = await Promise.all([
          api.khataSummary(token),
          api.khataEntries(token, PAGE_SIZE, 0),
        ]);
        setSummary(s);
        setEntries(p.entries);
        setTotal(p.total);
      } else {
        const p = await api.khataEntries(token, PAGE_SIZE, offset);
        setEntries((prev) => [...prev, ...p.entries]);
        setTotal(p.total);
      }
    } catch (err) {
      setSummary((prev) => prev ?? null);
      setError(err instanceof ApiError ? err.message : "Could not load khata.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    loadEntries(0);
  }, [loadEntries]);

  const payments = entries.filter((e) => e.entry_type === "payment");

  function entryRow(entry: KhataEntry) {
    return (
      <li className="khata-row" key={entry.id}>
        <span>
          {khataEntryTypeLabel(entry.entry_type)}
          {entry.note ? ` · ${entry.note}` : null}
        </span>
        <span className="khata-amount-cell">₹ {formatPaise(entry.amount_paise)}</span>
        <span className="muted">{new Date(entry.created_at).toLocaleDateString()}</span>
      </li>
    );
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <div className="page-head">
          <h1>📒 {t.khataTitle}</h1>
          <Link className="btn-secondary add-btn" href="/home">
            {t.navHome}
          </Link>
        </div>

        {summary === undefined ? (
          <p className="muted">{t.loading}</p>
        ) : summary ? (
          <div className="grid">
            <div className="card">
              <h2>{t.khataOutstanding}</h2>
              <p className="khata-amount">₹ {formatPaise(summary.outstanding_paise)}</p>
              <p className="muted">
                {t.khataCreditLimitLabel}: ₹ {formatPaise(summary.credit_limit_paise)}
              </p>
              {summary.over_limit ? <p className="status-err">⚠ {t.alertKhataLimit}</p> : null}
            </div>
          </div>
        ) : null}

        {error ? <p className="form-error">{error}</p> : null}

        <div className="card">
          <h2>{t.khataTransactions}</h2>
          {entries.length === 0 && !busy ? (
            <p className="muted">{t.khataNoEntries}</p>
          ) : (
            <ul className="khata-list">{entries.map(entryRow)}</ul>
          )}
          {entries.length < total ? (
            <button
              className="btn-secondary"
              type="button"
              disabled={busy}
              onClick={() => loadEntries(entries.length)}
            >
              {busy ? t.loading : t.loadMore}
            </button>
          ) : null}
        </div>

        <div className="card">
          <h2>{t.khataPaymentHistory}</h2>
          {payments.length === 0 ? (
            <p className="muted">{t.khataNoEntries}</p>
          ) : (
            <ul className="khata-list">{payments.map(entryRow)}</ul>
          )}
        </div>
      </main>
    </AuthGate>
  );
}
