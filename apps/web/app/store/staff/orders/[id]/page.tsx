/**
 * Staff Order Details (store-wide, display-only): number, date, items,
 * status, payment status, server-computed totals.
 * No cancel/pay buttons — staff view is read-only.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import { orderStatusLabel } from "../../../../../components/orderLabels";
import { ApiError, api, getStoredToken, type Order, type OrderItem } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";
import { formatPaise, paymentStatusLabel } from "../../../../../lib/khata";

export default function StaffOrderDetailsPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [items, setItems] = useState<OrderItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const o = await api.getStaffOrder(token, params.id);
      setOrder(o);
      setItems(o.items ?? (await api.staffOrderItems(token, params.id)));
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
        setError("प्रवेश नाही");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = items ?? order?.items ?? [];

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/staff/orders">← Orders / ऑर्डर</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!order ? (
          forbidden ? (
            <p className="muted">प्रवेश नाही</p>
          ) : (
            <p className="muted">{t.loading}</p>
          )
        ) : (
          <>
            <section className="card">
              <h1>📦 {order.order_number ?? order.id.slice(0, 8)}</h1>
              <p className="muted">
                {t.orderDate}: {order.created_at.slice(0, 10)}
              </p>
              <p>
                {t.orderStatusLabel}: {orderStatusLabel(t, order.status)}
              </p>
              <p>
                पेमेंट Payment: {paymentStatusLabel(order.payment_status)}
              </p>
            </section>

            <section className="card">
              <h2>{t.orderSummary}</h2>
              {rows.map((item) => (
                <p key={item.id}>
                  {item.variant_id ? item.variant_id.slice(0, 8) : "—"} ·{" "}
                  {t.quantityLabel}: {item.qty} · ₹{formatPaise(item.line_total_paise)}
                </p>
              ))}
              <p>
                {t.subtotalLabel}: ₹{formatPaise(order.subtotal_paise)}
              </p>
              <p>
                {t.deliveryLabel}: ₹{formatPaise(order.delivery_paise)}
              </p>
              <p className="farm-area">
                {t.totalLabel}: ₹{formatPaise(order.total_paise)}
              </p>
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
