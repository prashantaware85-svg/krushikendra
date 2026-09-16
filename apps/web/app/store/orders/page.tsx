/**
 * My Orders list (auth-only): order number, date, total, status.
 * Snapshots — readable even after catalogue edits.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { orderStatusLabel } from "../../../components/orderLabels";
import { ApiError, api, getStoredToken, type Order } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise } from "../../../lib/khata";

export default function OrdersPage() {
  const { t } = useAuth();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setOrders(await api.listOrders(token));
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
        <h1>📋 {t.myOrders}</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {orders === null ? (
          <p className="muted">{t.loading}</p>
        ) : orders.length === 0 ? (
          <p className="muted">{t.noOrders}</p>
        ) : (
          <div className="grid">
            {orders.map((o) => (
              <article className="card" key={o.id}>
                <h2>{o.order_number ?? o.id.slice(0, 8)}</h2>
                <p className="muted">
                  {t.orderDate}: {o.created_at.slice(0, 10)}
                </p>
                <p className="farm-area">₹{formatPaise(o.total_paise)}</p>
                <p>
                  {t.orderStatusLabel}: {orderStatusLabel(t, o.status)}
                </p>
                <p>
                  <Link href={`/store/orders/${o.id}`}>{t.viewDetails} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
