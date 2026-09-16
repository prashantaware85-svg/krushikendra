/**
 * Inventory list (Step 16, auth-only): summary cards + search/status filters.
 * Quantities are decimal strings — displayed as-is.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { stockBadge } from "../../../components/stockBadge";
import { ApiError, api, getStoredToken, type InventoryList, type InventorySummary } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function InventoryPage() {
  const { t } = useAuth();
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [list, setList] = useState<InventoryList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const load = useCallback(async (f: { search?: string; status?: string }) => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setSummary(await api.inventorySummary(token));
      setList(await api.listInventory(token, {
        ...(f.search ? { search: f.search } : {}),
        ...(f.status ? { status: f.status } : {}),
        limit: 50,
        offset: 0,
      }));
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
    load({ ...(search.trim() ? { search: search.trim() } : {}), ...(status ? { status } : {}) });
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>📦 साठा Inventory</h1>
        <p>
          <Link href="/store/inventory/low-stock">कमी साठा Low Stock →</Link>
          {" · "}
          <Link href="/store/purchases">खरेदी Purchases</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {summary ? (
          <div className="grid">
            <article className="card"><h2>एकूण Variants: {summary.total_variants}</h2></article>
            <article className="card"><h2>🟢 उपलब्ध In Stock: {summary.in_stock}</h2></article>
            <article className="card"><h2>🟠 कमी Low: {summary.low_stock}</h2></article>
            <article className="card"><h2>🔴 संपला Out: {summary.out_of_stock}</h2></article>
          </div>
        ) : (
          <p className="muted">{t.loading}</p>
        )}
        <form onSubmit={onFilter}>
          <input type="search" placeholder="शोधा Search" value={search} onChange={(e) => setSearch(e.target.value)} />
          {" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">सर्व All</option>
            <option value="in_stock">🟢 उपलब्ध In Stock</option>
            <option value="low_stock">🟠 कमी Low Stock</option>
            <option value="out_of_stock">🔴 संपला Out of Stock</option>
          </select>
          {" "}
          <button className="btn" type="submit">लागू करा Apply</button>
        </form>
        {list === null ? (
          <p className="muted">{t.loading}</p>
        ) : list.items.length === 0 ? (
          <p className="muted">साठा नाही No inventory rows.</p>
        ) : (
          <>
            <p className="muted">एकूण Total: {list.total}</p>
            <div className="grid">
              {list.items.map((it) => (
                <article className="card" key={it.variant_id}>
                  <h2>{stockBadge(it.status)} {it.product_name ?? it.variant_id.slice(0, 8)}</h2>
                  <p className="muted">{it.variant_name ?? ""}</p>
                  <p>हातात On Hand: {it.qty_on_hand} · राखीव Reserved: {it.qty_reserved} · उपलब्ध Available: {it.available}</p>
                  <p>
                    <Link href={`/store/inventory/${it.variant_id}`}>{t.viewDetails} →</Link>
                  </p>
                </article>
              ))}
            </div>
          </>
        )}
      </main>
    </AuthGate>
  );
}
