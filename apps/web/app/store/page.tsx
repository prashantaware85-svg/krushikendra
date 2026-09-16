/**
 * Krushi Store home (auth-only): search + category filter + product cards.
 * Facts only — no cart, orders, or recommendations. Prices shown only when
 * known ("price unavailable" otherwise — never fabricated).
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type ProductCategory,
  type StoreProduct,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function StorePage() {
  const { t } = useAuth();
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categories, setCategories] = useState<ProductCategory[] | null>(null);
  const [products, setProducts] = useState<StoreProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (q: string, cat: string) => {
      const token = getStoredToken();
      if (!token) return;
      try {
        const [cats, res] = await Promise.all([
          api.listStoreCategories(token),
          api.listStoreProducts(token, {
            search: q || undefined,
            category_id: cat || undefined,
          }),
        ]);
        setCategories(cats);
        setProducts(res.products);
        setError(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    },
    [],
  );

  useEffect(() => {
    load("", "");
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <div className="page-head">
          <div>
            <h1>🛒 {t.storeTitle}</h1>
            <p className="muted">{t.storeHint}</p>
          </div>
          <Link className="btn add-btn" href="/store/cart">
            🛒 {t.cartTitle}
          </Link>
        </div>
        <p>
          <Link href="/store/orders">{t.myOrders} →</Link>
          {" · "}
          <Link href="/store/addresses">{t.addressesTitle} →</Link>
        </p>

        {error ? <p className="form-error">{error}</p> : null}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            load(search.trim(), categoryId);
          }}
        >
          <label className="field">
            <span>{t.searchProduct}</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.searchProductPlaceholder}
              maxLength={64}
            />
          </label>
          <label className="field">
            <span>{t.categoryLabel}</span>
            <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">— {t.filterAll} —</option>
              {(categories ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" type="submit">
            {t.searchProduct}
          </button>
        </form>

        <h2>{t.categoriesTitle}</h2>
        <div className="chip-row">
          <button
            type="button"
            className={!categoryId ? "chip chip-on" : "chip"}
            onClick={() => {
              setCategoryId("");
              load(search.trim(), "");
            }}
          >
            {t.filterAll}
          </button>
          {(categories ?? []).filter((c) => !c.parent_id).map((c) => (
            <button
              key={c.id}
              type="button"
              className={categoryId === c.id ? "chip chip-on" : "chip"}
              onClick={() => {
                setCategoryId(c.id);
                load(search.trim(), c.id);
              }}
            >
              {categoryEmoji(c.slug)} {c.name}
            </button>
          ))}
        </div>

        {products === null ? (
          <p className="muted">{t.loading}</p>
        ) : products.length === 0 ? (
          <p className="muted">{t.noProducts}</p>
        ) : (
          <div className="grid">
            {products.map((p) => (
              <article className="card" key={p.id}>
                <h2>
                  {typeEmoji(p.product_type)} {p.name}
                </h2>
                <p className="muted">
                  {p.brand ?? t.notSet} · {p.category_name ?? ""}
                </p>
                <p>
                  {p.is_verified ? `✓ ${t.verifiedProduct}` : t.verificationPending}
                </p>
                <p>
                  <Link href={`/store/${p.id}`}>{t.viewProduct} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}

function categoryEmoji(slug: string): string {
  if (slug.includes("seed")) return "🌱";
  if (slug.includes("fertil")) return "🧪";
  if (slug.includes("protect") || slug.includes("control")) return "🐛";
  if (slug.includes("bio")) return "🌿";
  if (slug.includes("accessor")) return "🧰";
  return "📦";
}

function typeEmoji(productType: string): string {
  const map: Record<string, string> = {
    seed: "🌱",
    fertilizer: "🧪",
    crop_protection: "🐛",
    bio_product: "🌿",
    accessory: "🧰",
    other: "📦",
  };
  return map[productType] ?? "📦";
}
