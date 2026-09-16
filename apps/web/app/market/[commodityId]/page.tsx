/**
 * Commodity Details (auth-only): latest prices, market comparison table,
 * recent history table. Factual display only — no sell recommendations.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Commodity, type MarketPrice } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function CommodityPage({ params }: { params: { commodityId: string } }) {
  const { t } = useAuth();
  const [commodity, setCommodity] = useState<Commodity | null>(null);
  const [prices, setPrices] = useState<MarketPrice[] | null>(null);
  const [history, setHistory] = useState<MarketPrice[] | null>(null);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const c = await api.getCommodity(token, params.commodityId);
      setCommodity(c);
      const q = `?commodity_id=${params.commodityId}&limit=50`;
      const latest = await api.marketPrices(token, q);
      setPrices(latest.prices);
      setStale(latest.data_state === "stale");
      const hist = await api.priceHistory(token, q).catch(() => null);
      setHistory(hist ? hist.prices.slice(-10).reverse() : []);
    } catch (err) {
      if (err instanceof ApiError && err.code === "MARKET_DATA_UNAVAILABLE") {
        setError(t.marketDataUnavailable);
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, [params.commodityId, t]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href="/market">← {t.marketTitle}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!commodity ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="hero">
              <h1>
                🌾 {commodity.local_name ?? commodity.name}
              </h1>
              <p>
                {commodity.name} · {commodity.category}
              </p>
            </section>

            <div className="card">
              <h2>
                {t.compareMarkets}{" "}
                {stale ? <span className="badge-stale">{t.weatherStale}</span> : null}
              </h2>
              {prices === null ? (
                <p className="muted">{t.loading}</p>
              ) : prices.length === 0 ? (
                <p className="muted">{t.noPrices}</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t.market}</th>
                      <th>{t.modalPrice}</th>
                      <th>{t.priceDate}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prices.map((p) => (
                      <tr key={p.id}>
                        <td>{p.market.name}</td>
                        <td>
                          ₹{formatINR(p.modal_price)} / {unitLabel(t, p.unit)}
                          {p.is_sample ? (
                            <>
                              <br />
                              <span className="badge-stale">{t.sampleData}</span>
                            </>
                          ) : null}
                        </td>
                        <td>{p.price_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="card">
              <h2>{t.priceHistory}</h2>
              {history === null ? (
                <p className="muted">{t.loading}</p>
              ) : history.length === 0 ? (
                <p className="muted">{t.noPrices}</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t.priceDate}</th>
                      <th>{t.modalPrice}</th>
                      <th>
                        {t.minPrice} / {t.maxPrice}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((p) => (
                      <tr key={p.id}>
                        <td>{p.price_date}</td>
                        <td>
                          ₹{formatINR(p.modal_price)} / {unitLabel(t, p.unit)}
                        </td>
                        <td>
                          ₹{formatINR(p.min_price)} / ₹{formatINR(p.max_price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {prices && prices[0] ? (
                <p className="muted small">
                  {t.priceUnit}: {unitLabel(t, prices[0].unit)} · {t.priceSource}:{" "}
                  {prices[0].source} · {t.updatedOn}: {prices[0].fetched_at.slice(0, 10)}
                </p>
              ) : null}
            </div>

            {prices && prices[0] ? (
              <div className="card">
                <h2>
                  {prices[0].market.name} · {t.priceDate} {prices[0].price_date}
                </h2>
                <p>
                  {t.minPrice} ₹{formatINR(prices[0].min_price)}
                </p>
                <p>
                  {t.maxPrice} ₹{formatINR(prices[0].max_price)}
                </p>
                <p>
                  {t.modalPrice} ₹{formatINR(prices[0].modal_price)}
                </p>
              </div>
            ) : null}
          </>
        )}
      </main>
    </AuthGate>
  );
}

function formatINR(value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function unitLabel(t: Record<string, string>, unit: string): string {
  if (unit === "kg") return t.kg;
  if (unit === "tonne") return t.tonne;
  if (unit === "other") return unit;
  return t.quintal;
}
