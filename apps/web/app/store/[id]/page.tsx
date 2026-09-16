/**
 * Product Details (auth-only): images, facts, packs, verification status.
 * Display only — no cart, orders, or recommendations.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type StoreProductDetail } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function ProductPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [product, setProduct] = useState<StoreProductDetail | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("1");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const row = await api.getStoreProduct(token, params.id);
      setProduct(row);
      const first = (row.variants ?? []).find((v) => v.selling_price !== null) ?? row.variants?.[0];
      if (first && !variantId) setVariantId(first.id);
      const primary = (row.images ?? []).find((i) => i.is_primary) ?? row.images?.[0];
      if (primary) {
        const blob = await api.storeImageBlob(token, primary.id);
        setPhotoUrl(URL.createObjectURL(blob));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  useEffect(() => {
    load();
    return () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store">← {t.backToStore}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!product ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <section className="card">
            <h1>
              🌱 {product.name}
            </h1>
            <p>
              {product.is_verified ? `✓ ${t.verifiedProduct}` : t.verificationPending}
            </p>
            {photoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photoUrl} alt={product.name} className="result-img" />
            ) : null}
            <KV k={t.brandLabel} v={product.brand} t={t} />
            <KV k={t.manufacturerLabel} v={product.manufacturer} t={t} />
            <KV k={t.categoryLabel} v={product.category_name} t={t} />
            <KV k={t.shortDescriptionLabel} v={product.short_description ?? product.description} t={t} />
            {product.registration_number ? (
              <KV k="Registration" v={product.registration_number} />
            ) : null}

            <h2>{t.packsTitle}</h2>
            {!product.variants || product.variants.length === 0 ? (
              <p className="muted">{t.noProducts}</p>
            ) : (
              <>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t.fertQuantity}</th>
                      <th>{t.mrpLabel}</th>
                      <th>{t.sellingPriceLabel}</th>
                      <th>{t.obsStatus}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {product.variants.map((v) => (
                      <tr key={v.id}>
                        <td>
                          {v.pack_size} {v.pack_unit}
                        </td>
                        <td>{v.mrp !== null ? `₹${formatINR(v.mrp)}` : t.priceUnavailable}</td>
                        <td>
                          {v.selling_price !== null ? `₹${formatINR(v.selling_price)}` : t.priceUnavailable}
                        </td>
                        <td>{stockLabel(t, v.stock_status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <label className="field">
                  <span>{t.fertQuantity}</span>
                  <select value={variantId} onChange={(e) => setVariantId(e.target.value)}>
                    {product.variants.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.pack_size} {v.pack_unit}
                        {v.selling_price !== null ? ` — ₹${formatINR(v.selling_price)}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>{t.quantityLabel}</span>
                  <input
                    value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    inputMode="numeric"
                    min={1}
                  />
                </label>
                <button
                  className="btn"
                  type="button"
                  disabled={!variantId}
                  onClick={async () => {
                    const token = getStoredToken();
                    if (!token || !variantId) return;
                    try {
                      await api.addCartItem(token, variantId, Math.max(1, Number(qty) || 1));
                      router.push("/store/cart");
                    } catch (err) {
                      setError(err instanceof ApiError ? err.message : "Error");
                    }
                  }}
                >
                  {t.addToCart}
                </button>
              </>
            )}
          </section>
        )}
      </main>
    </AuthGate>
  );
}

function KV({ k, v, t }: { k: string; v: string | null | undefined; t?: { notSet: string } }) {
  return (
    <p>
      <strong>{k}:</strong> {v ?? t?.notSet ?? "—"}
    </p>
  );
}

function formatINR(value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function stockLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    in_stock: t.stockInStock,
    low_stock: t.stockLowStock,
    out_of_stock: t.stockOutOfStock,
    unavailable: t.stockUnavailable,
  };
  return map[v] ?? v;
}
