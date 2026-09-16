/**
 * Order Details (auth-only): number, dates, snapshot items, address,
 * server-computed totals, payment status, status timeline, cancel rule.
 * Display only — no status editing, no payment actions.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { orderStatusLabel } from "../../../../components/orderLabels";
import { ApiError, api, getStoredToken, type Address, type Order, type PaymentInitiate } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise, paymentStatusLabel } from "../../../../lib/khata";

const TIMELINE_STEPS = [
  "pending",
  "confirmed",
  "processing",
  "packed",
  "shipped",
  "out_for_delivery",
  "delivered",
];

export default function OrderDetailsPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [payment, setPayment] = useState<PaymentInitiate | null>(null);
  const [delivery, setDelivery] = useState<Address | null>(null);
  const [payBusy, setPayBusy] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  const [providerDisabled, setProviderDisabled] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const o = await api.getOrder(token, params.id);
      setOrder(o);
      // Backend returns address_id only — resolve the snapshot from the address list.
      if (o.address_id) {
        const list = await api.listAddresses(token).catch(() => [] as Address[]);
        setDelivery(list.find((a) => a.id === o.address_id) ?? null);
      } else {
        setDelivery(null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function onCancel() {
    if (!window.confirm(t.cancelOrderConfirm)) return;
    const token = getStoredToken();
    if (!token || busy) return;
    setBusy(true);
    try {
      setOrder(await api.cancelOrder(token, params.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onPayNow() {
    const token = getStoredToken();
    if (!token || !order || payBusy) return;
    setPayBusy(true);
    setPayError(null);
    try {
      // Idempotency key: a fresh UUID per tap; the backend dedupes retries.
      const p = await api.initiatePayment(token, order.id, crypto.randomUUID());
      setPayment(p);
    } catch (err) {
      if (err instanceof ApiError && err.code === "PAYMENT_PROVIDER_DISABLED") {
        setProviderDisabled(true);
        setPayError("पेमेंट सध्या बंद आहे (Payment provider unavailable).");
      } else {
        setPayError(err instanceof ApiError ? err.message : "Error");
      }
    } finally {
      setPayBusy(false);
    }
  }

  const cancellable =
    order !== null && (order.status === "pending" || order.status === "confirmed");

  const payPending =
    order !== null && (order.payment_status === "pending" || order.payment_status === "failed");
  const showPayNow = payPending && !providerDisabled && payment?.status !== "paid";

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/orders">← {t.myOrders}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!order ? (
          <p className="muted">{t.loading}</p>
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
              <h2>पेमेंट Payment</h2>
              <p>
                स्थिती Status: {paymentStatusLabel(order.payment_status)}
              </p>
              {payError ? <p className="form-error">{payError}</p> : null}
              {showPayNow ? (
                <button
                  className="btn"
                  type="button"
                  disabled={payBusy}
                  onClick={onPayNow}
                >
                  {payBusy ? t.loading : "आता भरा Pay Now"}
                </button>
              ) : null}
              {payment ? (
                <>
                  <p className="muted">
                    संदर्भ Ref: {payment.provider_ref} · मंजूर Approved:{" "}
                    {payment.approved ? t.yes : t.no}
                  </p>
                  {payment.provider === "mock" ? (
                    <p className="form-error">
                      ⚠️ विकास चाचणी / DEV-ONLY mock — real settlement नाही.
                    </p>
                  ) : (
                    <p className="muted">प्रदाता Provider: {payment.provider}</p>
                  )}
                </>
              ) : null}
            </section>

            <section className="card">
              <h2>{t.orderSummary}</h2>
              {order.items.map((item) => (
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

            {delivery ? (
              <section className="card">
                <h2>{t.selectAddress}</h2>
                <p>{delivery.label ?? delivery.line1}</p>
                <p className="muted">
                  {delivery.line1}, {delivery.city}, {delivery.state}{" "}
                  {delivery.pincode}
                </p>
              </section>
            ) : null}

            <section className="card">
              <h2>{t.timeline ?? "Timeline"}</h2>
              {order.status === "cancelled" ? (
                <p>✓ {orderStatusLabel(t, "cancelled")}</p>
              ) : (
                TIMELINE_STEPS.map((s) => {
                  const done =
                    TIMELINE_STEPS.indexOf(s) <= TIMELINE_STEPS.indexOf(order.status);
                  return done ? (
                    <p key={s}>
                      ✓ {orderStatusLabel(t, s)}
                    </p>
                  ) : (
                    <p key={s} className="muted">
                      ○ {orderStatusLabel(t, s)}
                    </p>
                  );
                })
              )}
            </section>

            {cancellable ? (
              <button
                className="btn-danger"
                type="button"
                disabled={busy}
                onClick={onCancel}
              >
                {t.cancelOrderBtn}
              </button>
            ) : null}
            <p>
              <button
                type="button"
                className="link-btn-plain"
                onClick={() => router.push("/store/orders")}
              >
                ← {t.myOrders}
              </button>
            </p>
          </>
        )}
      </main>
    </AuthGate>
  );
}
