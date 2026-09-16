/**
 * Checkout page (auth-only): address select + server-computed summary.
 * Client sends address_id ONLY — totals come from the backend response.
 * No payment gateway in this step (order lands as payment pending).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Address, type Cart } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise } from "../../../lib/khata";

export default function CheckoutPage() {
  const { t } = useAuth();
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [addressId, setAddressId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [c, a] = await Promise.all([
        api.getCart(token),
        api.listAddresses(token).catch(() => [] as Address[]),
      ]);
      setCart(c);
      setAddresses(a);
      const def = a.find((x) => x.is_default) ?? a[0];
      if (def) setAddressId(def.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function confirm() {
    const token = getStoredToken();
    if (!token || !addressId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const order = await api.checkout(token, addressId);
      router.push(`/store/orders/${order.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <h1>📋 {t.checkoutTitle}</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {!cart || addresses === null ? (
          <p className="muted">{t.loading}</p>
        ) : cart.items.length === 0 ? (
          <section className="card">
            <p className="muted">{t.cartEmpty}</p>
            <p>
              <Link href="/store">{t.storeTitle} →</Link>
            </p>
          </section>
        ) : (
          <>
            <section className="card">
              <h2>{t.selectAddress}</h2>
              {addresses.length === 0 ? (
                <p>
                  <Link href="/store/addresses">+ {t.addAddress}</Link>
                </p>
              ) : (
                <label className="field">
                  <select value={addressId} onChange={(e) => setAddressId(e.target.value)}>
                    {addresses.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.label ?? a.line1}, {a.city}, {a.state} {a.pincode}
                        {a.is_default ? ` (${t.defaultBadge})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p>
                <Link href="/store/addresses">+ {t.addAddress}</Link>
              </p>
            </section>

            <section className="card">
              <h2>{t.orderSummary}</h2>
              {cart.items.map((item) => (
                <p key={item.item_id}>
                  {item.product_name ?? item.variant_name} · {item.variant_name} ·{" "}
                  {t.quantityLabel}: {item.qty} · ₹
                  {item.line_total_paise !== null ? formatPaise(item.line_total_paise) : "—"}
                </p>
              ))}
              <p>
                <strong>{t.subtotalLabel}:</strong> ₹{formatPaise(cart.subtotal_paise)}
              </p>
              <button
                className="btn"
                type="button"
                disabled={busy || !addressId}
                onClick={confirm}
              >
                {busy ? t.saving : t.confirmOrder}
              </button>
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
