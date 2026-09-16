/**
 * Market section home (auth-only): commodity search + list, market list.
 * Facts only — no selling, predictions, or recommendations.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ApiError, api, getStoredToken, type Commodity, type MarketInfo } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function MarketPage() {
  const { t } = useAuth();
  const [search, setSearch] = useState("");
  const [commodities, setCommodities] = useState<Commodity[] | null>(null);
  const [markets, setMarkets] = useState<MarketInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (q: string) => {
      const token = getStoredToken();
      if (!token) return;
      try {
        const [c, m] = await Promise.all([
          api.listCommodities(token, q || undefined),
          api.listMarkets(token),
        ]);
        setCommodities(c);
        setMarkets(m);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.code === "MARKET_DATA_UNAVAILABLE") {
          setError(t.marketDataUnavailable);
        } else {
          setError(err instanceof ApiError ? err.message : "Error");
        }
      }
    },
    [t],
  );

  useEffect(() => {
    load("");
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <div className="page-head">
          <div>
            <h1>📊 {t.marketTitle}</h1>
            <p className="muted">{t.marketHint}</p>
          </div>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            load(search.trim());
          }}
        >
          <label className="field">
            <span>{t.searchCommodity}</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.searchPlaceholder}
              maxLength={64}
            />
          </label>
          <button className="btn" type="submit">
            {t.searchCommodity}
          </button>
        </form>

        <h2>🌾 {t.commodity}</h2>
        {commodities === null ? (
          <p className="muted">{t.loading}</p>
        ) : commodities.length === 0 ? (
          <p className="muted">{t.noCommodities}</p>
        ) : (
          <div className="grid">
            {commodities.map((c) => (
              <article className="card" key={c.id}>
                <h2>{c.local_name ?? c.name}</h2>
                <p className="muted">
                  {c.name} · {c.category}
                </p>
                <p>
                  <Link href={`/market/${c.id}`}>{t.viewDetails} →</Link>
                </p>
              </article>
            ))}
          </div>
        )}

        <h2>🏪 {t.nearbyMarkets}</h2>
        {markets === null ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <div className="grid">
            {markets.map((m) => (
              <article className="card" key={m.id}>
                <h2>{m.name}</h2>
                <p className="muted">
                  {m.district}, {m.state}
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
