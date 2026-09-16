/**
 * Low-stock list (Step 16, auth-only): server-driven GET /inventory/low-stock.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type InventoryItem } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { stockBadge } from "../../../../components/stockBadge";

export default function LowStockPage() {
  const { t } = useAuth();
  const [items, setItems] = useState<InventoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setItems(await api.lowStock(token));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href="/store/inventory">← साठा Inventory</Link>
        </p>
        <h1>🟠 कमी साठा Low Stock</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {items === null ? (
          <p className="muted">{t.loading}</p>
        ) : items.length === 0 ? (
          <p className="muted">सर्व साठा ठीक आहे All stock levels OK.</p>
        ) : (
          <div className="grid">
            {items.map((it) => (
              <article className="card" key={it.variant_id}>
                <h2>{stockBadge(it.status)} {it.product_name ?? it.variant_id.slice(0, 8)}</h2>
                <p className="muted">{it.variant_name ?? ""}</p>
                <p>हातात On Hand: {it.qty_on_hand} · उपलब्ध Available: {it.available}</p>
                <p>
                  <Link href={`/store/inventory/${it.variant_id}`}>{t.viewDetails} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
