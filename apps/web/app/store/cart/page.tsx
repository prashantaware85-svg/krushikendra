/**
 * Cart page (auth-only): lines with +/- qty, validation issues, subtotal.
 * Prices shown come from the server (display); checkout re-reads them.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Cart, type CartIssue } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise } from "../../../lib/khata";

export default function CartPage() {
  const { t } = useAuth();
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [issues, setIssues] = useState<CartIssue[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [c, v] = await Promise.all([
        api.getCart(token),
        api.validateCart(token).catch(() => null),
      ]);
      setCart(c);
      setIssues(v && !v.valid ? v.issues : []);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function setQty(itemId: string, qty: number) {
    const token = getStoredToken();
    if (!token || qty < 1) return;
    try {
      await api.updateCartItem(token, itemId, qty);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function remove(itemId: string) {
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.removeCartItem(token, itemId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function clear() {
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.clearCart(token);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <h1>🛒 {t.cartTitle}</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {!cart ? (
          <p className="muted">{t.loading}</p>
        ) : cart.items.length === 0 ? (
          <section className="card">
            <p className="muted">{t.cartEmpty}</p>
            <p className="muted">{t.cartEmptyHint}</p>
            <p>
              <Link href="/store">{t.storeTitle} →</Link>
            </p>
          </section>
        ) : (
          <>
            {issues.length > 0 ? (
              <section className="card">
                <p className="form-error">{t.cartBlocked}</p>
                {issues.map((i) => (
                  <p key={i.item_id ?? i.code} className="form-error small">
                    • {i.message}
                  </p>
                ))}
              </section>
            ) : null}
            {cart.items.map((item) => (
              <section className="card" key={item.item_id}>
                <h2>{item.product_name ?? item.variant_name}</h2>
                <p className="muted">
                  {item.variant_name}
                </p>
                <p className="farm-area">
                  {item.unit_price_paise !== null ? `₹${formatPaise(item.unit_price_paise)}` : t.priceUnavailable}
                </p>
                {item.price_on_request ? (
                  <p className="form-error small">
                    ⚠️ {issues.find((i) => i.item_id === item.item_id)?.message ?? t.noProducts}
                  </p>
                ) : null}
                <div className="card-actions">
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => setQty(item.item_id, item.qty - 1)}
                    disabled={item.qty <= 1}
                  >
                    [-]
                  </button>
                  <span>
                    {t.quantityLabel}: {item.qty}
                  </span>
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => setQty(item.item_id, item.qty + 1)}
                  >
                    [+]
                  </button>
                  <button
                    className="btn-danger"
                    type="button"
                    aria-label={t.deleteAddress}
                    onClick={() => remove(item.item_id)}
                  >
                    ×
                  </button>
                </div>
              </section>
            ))}
            <section className="card">
              <p>
                <strong>{t.subtotalLabel}:</strong> ₹{formatPaise(cart.subtotal_paise)}
              </p>
              <button
                className="btn"
                type="button"
                disabled={issues.length > 0}
                onClick={() => router.push("/store/checkout")}
              >
                {t.checkoutTitle} →
              </button>
              <p>
                <button type="button" className="link-btn-plain" onClick={clear}>
                  {t.emptyCartBtn}
                </button>
              </p>
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
