/**
 * Khata — खाता ledger list (auth-only, READ-ONLY).
 *
 * No customer API exists in the backend, so this screen derives ledger
 * groups client-side from khata entries ONLY (khataSummary + khataEntries):
 * - "self" = the farmer's own general ledger (entries without an order_id)
 * - one group per order_id for order-linked entries
 * Search filters those groups by order id / note text. Display only —
 * the frontend never creates or edits balances.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type KhataEntry, type KhataSummary } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise, signedDelta } from "../../../lib/khata";

type LedgerGroup = {
  id: string;
  title: string;
  count: number;
  netPaise: number;
  lastAt: string;
  notes: string[];
};

function groupEntries(entries: KhataEntry[]): LedgerGroup[] {
  const map = new Map<string, LedgerGroup>();
  for (const e of entries) {
    const id = e.order_id ?? "self";
    let g = map.get(id);
    if (!g) {
      g = {
        id,
        title: id === "self" ? "माझे खाते (My ledger)" : `ऑर्डर खाते (Order ${id.slice(0, 8)}…)`,
        count: 0,
        netPaise: 0,
        lastAt: e.created_at,
        notes: [],
      };
      map.set(id, g);
    }
    g.count += 1;
    // Read-only grouping: debits increase dues, credits/payments reduce them.
    g.netPaise += -signedDelta(e.entry_type, e.amount_paise);
    if (e.created_at > g.lastAt) g.lastAt = e.created_at;
    if (e.note && g.notes.length < 3 && !g.notes.includes(e.note)) g.notes.push(e.note);
  }
  return Array.from(map.values()).sort((a, b) => (a.lastAt < b.lastAt ? 1 : -1));
}

export default function CustomersPage() {
  const { t } = useAuth();
  const [summary, setSummary] = useState<KhataSummary | null>(null);
  const [entries, setEntries] = useState<KhataEntry[] | null>(null);
  const [query, setQuery] = useState("");
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

  const groups = useMemo(() => groupEntries(entries ?? []), [entries]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groups;
    return groups.filter(
      (g) =>
        g.id.toLowerCase().includes(q) ||
        g.title.toLowerCase().includes(q) ||
        g.notes.some((n) => n.toLowerCase().includes(q)),
    );
  }, [groups, query]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>📒 खाता (Khata)</h1>
        <p className="muted">ग्राहक खातेवही — फक्त पाहण्यासाठी (Customer ledgers — view only).</p>
        {error ? <p className="form-error">{error}</p> : null}

        <section className="card">
          <h2>शिल्लक Outstanding</h2>
          {summary ? (
            <>
              <p className="farm-area">₹{formatPaise(summary.outstanding_paise)}</p>
              <p>
                पत मर्यादा Credit limit: ₹{formatPaise(summary.credit_limit_paise)}
              </p>
              {summary.over_limit ? (
                <p className="form-error">⚠️ मर्यादेबाहेर Over limit</p>
              ) : null}
            </>
          ) : (
            <p className="muted">{t.loading}</p>
          )}
        </section>

        <section className="card">
          <h2>शोधा Search</h2>
          <input
            type="search"
            placeholder="ऑर्डर id / नोंद शोधा (order id or note)…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="खाते शोधा"
          />
        </section>

        {entries === null ? (
          <p className="muted">{t.loading}</p>
        ) : filtered.length === 0 ? (
          <p className="muted">खाती सापडली नाहीत (No ledgers found).</p>
        ) : (
          <div className="grid">
            {filtered.map((g) => (
              <article className="card" key={g.id}>
                <h2>{g.title}</h2>
                <p>
                  गट शिल्लक Group dues: ₹{formatPaise(g.netPaise)}
                </p>
                <p className="muted">
                  नोंदी Entries: {g.count} · शेवटची Last: {g.lastAt.slice(0, 10)}
                </p>
                <p>
                  <Link href={`/store/customers/${g.id}`}>तपशील पहा View details →</Link>
                </p>
                <p>
                  <Link href={`/store/customers/${g.id}/khata`}>व्यवहार History →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
