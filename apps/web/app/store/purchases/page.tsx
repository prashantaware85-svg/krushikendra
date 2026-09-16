/**
 * Purchases list (Step 16, auth-only): filters by supplier/status/date range.
 * Money in paise via formatPaise; server-computed totals only.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Purchase } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise } from "../../../lib/khata";

export default function PurchasesPage() {
  const { t } = useAuth();
  const [purchases, setPurchases] = useState<Purchase[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [supplierId, setSupplierId] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const load = useCallback(async (f: { supplier_id?: string; status?: string; from?: string; to?: string }) => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setPurchases(await api.listPurchases(token, f));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load({});
  }, [load]);

  function onFilter(e: React.FormEvent) {
    e.preventDefault();
    load({
      ...(supplierId.trim() ? { supplier_id: supplierId.trim() } : {}),
      ...(status ? { status } : {}),
      ...(from ? { from } : {}),
      ...(to ? { to } : {}),
    });
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>🧾 खरेदी Purchases</h1>
        <p>
          <Link href="/store/purchases/new">＋ नवीन खरेदी New Purchase</Link>
          {" · "}
          <Link href="/store/suppliers">पुरवठादार Suppliers</Link>
          {" · "}
          <Link href="/store/inventory">साठा Inventory</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        <form onSubmit={onFilter}>
          <input placeholder="पुरवठादार ID Supplier ID" value={supplierId} onChange={(e) => setSupplierId(e.target.value)} />
          {" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">सर्व स्थिती All statuses</option>
            <option value="draft">मसुदा Draft</option>
            <option value="received">प्राप्त Received</option>
            <option value="cancelled">रद्द Cancelled</option>
          </select>
          {" "}
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          {" "}
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          {" "}
          <button className="btn" type="submit">लागू करा Apply</button>
        </form>
        {purchases === null ? (
          <p className="muted">{t.loading}</p>
        ) : purchases.length === 0 ? (
          <p className="muted">खरेदी नाही No purchases yet.</p>
        ) : (
          <div className="grid">
            {purchases.map((p) => (
              <article className="card" key={p.id}>
                <h2>{p.id.slice(0, 8)}</h2>
                <p className="muted">{p.supplier_name ?? "पुरवठादार नाही No supplier"} · {p.purchase_date ?? "—"}</p>
                <p>{p.status}</p>
                <p className="farm-area">₹{formatPaise(p.total_paise)}</p>
                <p>
                  <Link href={`/store/purchases/${p.id}`}>{t.viewDetails} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
