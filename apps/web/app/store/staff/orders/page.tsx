/**
 * Staff Orders list (store-wide, read-only): order number, date, total, status.
 * Same OrderOut shape as farmer orders; 403 for non-staff shows प्रवेश नाही.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { orderStatusLabel } from "../../../../components/orderLabels";
import { ApiError, api, getStoredToken, type Order } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise } from "../../../../lib/khata";

export default function StaffOrdersPage() {
  const { t } = useAuth();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setOrders(await api.listStaffOrders(token));
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setOrders([]);
        setForbidden(true);
        setError("प्रवेश नाही");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>📋 Orders / ऑर्डर</h1>
        <p>
          <Link href="/store/staff">← कर्मचारी Staff</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {orders === null ? (
          <p className="muted">{t.loading}</p>
        ) : forbidden ? (
          <p className="muted">प्रवेश नाही</p>
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
                  <Link href={`/store/staff/orders/${o.id}`}>{t.viewDetails} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
