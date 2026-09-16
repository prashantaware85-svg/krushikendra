/**
 * Farm Details screen (auth-only): Basic / Location / Soil / Soil Health /
 * Irrigation / Crops / Weather / Market. Values are facts only — no advice.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ForecastStrip } from "../../../components/ForecastStrip";
import { WeatherCard } from "../../../components/WeatherCard";
import { ApiError, api, getStoredToken, type Crop, type Farm, type FarmMarketResponse, type Soil, type SoilTest, type WeatherCurrent, type WeatherForecast } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function FarmDetailsPage({ params }: { params: { id: string } }) {
  const { t, language } = useAuth();
  const router = useRouter();
  const [farm, setFarm] = useState<Farm | null>(null);
  const [soil, setSoil] = useState<Soil | null | undefined>(undefined);
  const [latestTest, setLatestTest] = useState<SoilTest | null | undefined>(undefined);
  const [crops, setCrops] = useState<Crop[] | null>(null);
  const [weather, setWeather] = useState<WeatherCurrent | null | undefined>(undefined);
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [farmMarket, setFarmMarket] = useState<FarmMarketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setFarm(await api.getFarm(token, params.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
      return;
    }
    try {
      setSoil(await api.getSoil(token, params.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setSoil(null);
      else setError(err instanceof ApiError ? err.message : "Error");
    }
    try {
      const tests = await api.listSoilTests(token, params.id);
      setLatestTest(tests.length > 0 ? tests[0] : null);
    } catch {
      setLatestTest(null); // soil history is auxiliary — details work without it
    }
    try {
      setCrops(await api.listCrops(token, params.id));
    } catch {
      setCrops([]); // crops list is auxiliary — farm details work without it
    }
    // Market view is auxiliary too: no GPS or no data → card hides itself.
    try {
      setFarmMarket(await api.farmMarketPrices(token, params.id));
    } catch {
      setFarmMarket(null);
    }
    // Weather is auxiliary too: missing GPS → guidance message, never forced.
    try {
      const w = await api.weatherCurrent(token, params.id);
      setWeather(w);
      try {
        setForecast(await api.weatherForecast(token, params.id));
      } catch {
        setForecast(null);
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "FARM_LOCATION_MISSING") {
        setWeather(null);
      } else {
        setWeather(null); // provider down → unavailable card, details still work
      }
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function onDelete() {
    if (!window.confirm(t.deleteConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteFarm(token, params.id);
      router.push("/farms");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href="/farms">← {t.backToFarms}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!farm ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="hero">
              <h1>
                🌾 {farm.farm_name}
              </h1>
              <p>
                {farm.area} {farm.area_unit} ({farm.area_in_acres} acre)
              </p>
            </section>

            <div className="grid">
              <div className="card">
                <h2>{t.basicInfo}</h2>
                <KV k={t.farmName} v={farm.farm_name} />
                <KV k={t.area} v={`${farm.area} ${farm.area_unit}`} />
                <KV k={t.ownership} v={ownershipLabel(t, farm.ownership_type)} />
                <KV k={t.landType} v={farm.land_type} t={t} />
              </div>

              <div className="card">
                <h2>{t.location}</h2>
                <KV k={t.stateLabel} v={farm.state} t={t} />
                <KV k={t.districtLabel} v={farm.district} t={t} />
                <KV k={t.talukaLabel} v={farm.taluka} t={t} />
                <KV k={t.villageLabel} v={farm.village} t={t} />
                {farm.latitude || farm.longitude ? (
                  <KV
                    k={t.gps}
                    v={`📍 ${farm.latitude ?? "?"} , ${farm.longitude ?? "?"}`}
                  />
                ) : null}
              </div>

              <div className="card">
                <h2>{t.soilInfo}</h2>
                {soil === undefined ? (
                  <p className="muted">{t.loading}</p>
                ) : soil === null ? (
                  <>
                    <p className="muted">{t.noSoil}</p>
                    <Link className="btn" href={`/farms/${farm.id}/soil/edit`}>
                      {t.addSoil}
                    </Link>
                  </>
                ) : (
                  <>
                    <KV k={t.soilType} v={soil.soil_type} t={t} />
                    <KV
                      k={t.soilTestAvailable}
                      v={soil.soil_test_available ? t.yes : t.no}
                    />
                    <KV k={t.soilTestDate} v={soil.soil_test_date} t={t} />
                    <KV k={t.phLabel} v={soil.ph} t={t} />
                    <KV k={t.organicCarbon} v={soil.organic_carbon} t={t} />
                    <KV k={t.nitrogen} v={soil.nitrogen} t={t} />
                    <KV k={t.phosphorus} v={soil.phosphorus} t={t} />
                    <KV k={t.potassium} v={soil.potassium} t={t} />
                    <p>
                      <Link href={`/farms/${farm.id}/soil`}>{t.viewDetails}</Link>
                      {" · "}
                      <Link href={`/farms/${farm.id}/soil/edit`}>{t.editSoil}</Link>
                    </p>
                  </>
                )}
              </div>

              <div className="card">
                <h2>🧪 {t.soilHealth}</h2>
                {latestTest === undefined ? (
                  <p className="muted">{t.loading}</p>
                ) : latestTest === null ? (
                  <>
                    <p className="muted">{t.noSoilTest}</p>
                    <Link
                      className="btn"
                      href={`/farms/${farm.id}/soil-tests/new`}
                    >
                      + {t.addSoilTest}
                    </Link>
                  </>
                ) : (
                  <>
                    <KV k={t.soilTestDate} v={latestTest.test_date} />
                    <KV k={t.labName} v={latestTest.laboratory_name} t={t} />
                    <KV k={t.reportNumber} v={latestTest.report_number} t={t} />
                    <KV k="pH" v={latestTest.ph} />
                    <KV k={t.ecLabel} v={latestTest.electrical_conductivity} />
                    <KV k={t.organicCarbonLabel} v={latestTest.organic_carbon} />
                    <KV k={t.nitrogenLabel} v={latestTest.nitrogen} />
                    <KV k={t.phosphorusLabel} v={latestTest.phosphorus} />
                    <KV k={t.potassiumLabel} v={latestTest.potassium} />
                    <p>
                      <Link href={`/farms/${farm.id}/soil-tests`}>
                        {t.soilHistory} →
                      </Link>
                    </p>
                  </>
                )}
              </div>

              <div className="card">
                <h2>{t.irrigation}</h2>
                <KV k={t.irrigation} v={irrigationLabel(t, farm.irrigation_type)} />
                <KV k={t.waterSource} v={waterLabel(t, farm.water_source)} />
                <div className="card-actions">
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => router.push(`/farms/${farm.id}/edit`)}
                  >
                    {t.edit}
                  </button>
                  <button className="btn-danger" type="button" onClick={onDelete}>
                    {t.deleteFarm}
                  </button>
                </div>
              </div>

              <div className="card">
                <h2>🌱 {t.myCrops}</h2>
                {crops === null ? (
                  <p className="muted">{t.loading}</p>
                ) : crops.length === 0 ? (
                  <p className="muted">{t.noCrops}</p>
                ) : (
                  crops.slice(0, 5).map((c) => (
                    <p key={c.id}>
                      <strong>{c.crop_name}</strong> · {c.area} {c.area_unit} ·{" "}
                      {c.season} · {t.sowingDate}: {c.sowing_date} ·{" "}
                      {t.statusLabel}: {c.status}{" "}
                      <Link href={`/farms/${farm.id}/crops/${c.id}`}>
                        [{t.viewDetails}]
                      </Link>
                    </p>
                  ))
                )}
                <p>
                  <Link href={`/farms/${farm.id}/crops`}>{t.viewDetails}</Link>
                  {" · "}
                  <Link href={`/farms/${farm.id}/crops/new`}>+ {t.addCrop}</Link>
                </p>
              </div>

              {weather === undefined ? (
                <div className="card">
                  <h2>🌦️ {t.farmWeather}</h2>
                  <p className="muted">{t.loading}</p>
                </div>
              ) : weather === null ? (
                <div className="card">
                  <h2>🌦️ {t.farmWeather}</h2>
                  <p className="muted">
                    {t.farmLocationMissing}{" "}
                    <Link href={`/farms/${farm.id}/edit`}>{t.edit}</Link>
                  </p>
                </div>
              ) : (
                <WeatherCard t={t} weather={weather} />
              )}

              {farmMarket && farmMarket.markets.length > 0 ? (
                <div className="card">
                  <h2>📊 {t.marketTitle}</h2>
                  {farmMarket.markets.slice(0, 3).map((entry) => (
                    <div key={entry.market.id}>
                      <p>
                        <strong>{entry.market.name}</strong>{" "}
                        <span className="muted">
                          ({entry.market.distance_km} km)
                        </span>
                      </p>
                      {entry.prices.slice(0, 3).map((p) => (
                        <p key={p.id} className="muted">
                          {p.commodity.local_name ?? p.commodity.name}: ₹
                          {formatINR(p.modal_price)} / {p.unit} · {p.price_date}
                          {p.is_sample ? ` (${t.sampleData})` : ""}
                        </p>
                      ))}
                    </div>
                  ))}
                  <p>
                    <Link href="/market">{t.marketTitle} →</Link>
                  </p>
                </div>
              ) : null}
            </div>
            {forecast ? (
              <div className="grid">
                <ForecastStrip t={t} language={language} forecast={forecast} />
              </div>
            ) : null}
          </>
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

function ownershipLabel(t: Record<string, string>, v: string | null) {
  const map: Record<string, string> = {
    owned: t.ownershipOwned,
    leased: t.ownershipLeased,
    shared: t.ownershipShared,
    other: t.ownershipOther,
  };
  return (v && map[v]) || t.notSet;
}

function irrigationLabel(t: Record<string, string>, v: string | null) {
  const map: Record<string, string> = {
    rainfed: t.irrigationRainfed,
    drip: t.irrigationDrip,
    sprinkler: t.irrigationSprinkler,
    flood: t.irrigationFlood,
    mixed: t.irrigationMixed,
    other: t.irrigationOther,
  };
  return (v && map[v]) || t.notSet;
}

function waterLabel(t: Record<string, string>, v: string | null) {
  const map: Record<string, string> = {
    rain: t.waterRain,
    borewell: t.waterBorewell,
    well: t.waterWell,
    canal: t.waterCanal,
    farm_pond: t.waterFarmPond,
    river: t.waterRiver,
    other: t.waterOther,
  };
  return (v && map[v]) || t.notSet;
}
