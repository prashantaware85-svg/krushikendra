/**
 * Authenticated farmer dashboard (auth-only): greeting, profile, alerts,
 * quick links to every service, weather + forecast, logout.
 *
 * Alerts come only from real endpoints: khata over-limit (ledger field) and
 * rain in the 7-day forecast (weather data). Missing data → empty state.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ForecastStrip } from "../../components/ForecastStrip";
import { WeatherCard } from "../../components/WeatherCard";
import {
  api,
  getStoredToken,
  type KhataSummary,
  type WeatherCurrent,
  type WeatherForecast,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function HomePage() {
  const { t, language, user, logout } = useAuth();
  const profile = user?.profile;
  const [weather, setWeather] = useState<WeatherCurrent | null | undefined>(undefined);
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [summary, setSummary] = useState<KhataSummary | null>(null);

  // Dashboard data: weather from the first GPS-located farm (oldest first);
  // khata summary for the alerts card. No GPS anywhere → unavailable state.
  const loadDashboard = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    setWeather(undefined);
    try {
      const farms = await api.listFarms(token);
      const located = farms.find((f) => f.latitude && f.longitude);
      const [w, fc, kh] = await Promise.all([
        located ? api.weatherCurrent(token, located.id) : Promise.resolve(null),
        located
          ? api.weatherForecast(token, located.id).catch(() => null)
          : Promise.resolve(null),
        api.khataSummary(token).catch(() => null),
      ]);
      setWeather(w);
      setForecast(fc);
      setSummary(kh);
    } catch {
      setWeather(null);
      setForecast(null);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const alerts: { text: string; href?: string }[] = [];
  if (summary?.over_limit) alerts.push({ text: t.alertKhataLimit, href: "/khata" });
  if (forecast?.days?.some((d) => (d.precipitation_probability ?? 0) >= 50)) {
    alerts.push({ text: t.alertRain });
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <section className="hero">
          <h1>
            {t.homeTitle} {profile?.full_name ?? ""}
          </h1>
          <p>{t.homeSubtitle}</p>
        </section>

        <div className="grid">
          <div className="card">
            <h2>🔔 {t.alertsTitle}</h2>
            {alerts.length === 0 ? (
              <p className="muted">{t.alertNoAlerts}</p>
            ) : (
              <ul className="alert-list">
                {alerts.map((a, i) => (
                  <li className="alert-item" key={i}>
                    {a.href ? <Link href={a.href}>{a.text}</Link> : a.text}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h2>{t.profileTitle}</h2>
            <p>
              📱 <code>{user?.mobile_number}</code>
            </p>
            <p>
              {t.fullNameLabel}: {profile?.full_name ?? t.notSet}
            </p>
            <p>
              {t.languageLabel}: <code>{profile?.preferred_language ?? "en"}</code>
            </p>
            <p>
              {[profile?.village, profile?.taluka, profile?.district, profile?.state]
                .filter(Boolean)
                .join(", ") || t.notSet}
            </p>
            <p>
              <Link href="/profile-setup">{t.updateProfile} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>🌾 {t.myFarms}</h2>
            <p className="muted">{t.myFarmsHint}</p>
            <p>
              <Link href="/farms">{t.openFarms} →</Link>
            </p>
            <button className="btn-secondary" type="button" onClick={logout}>
              {t.logout}
            </button>
          </div>

          <div className="card">
            <h2>🌱 {t.myCrops}</h2>
            <p className="muted">{t.cropsHint}</p>
            <p>
              <Link href="/farms">{t.myCrops} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>🩺 {t.cropHealthTitle}</h2>
            <p className="muted">{t.cropHealthHint}</p>
            <p>
              <Link href="/farms">{t.cropHealthTitle} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>📦 {t.navOrders}</h2>
            <p className="muted">{t.ordersHint}</p>
            <p>
              <Link href="/store/orders">{t.myOrders} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>📒 {t.navKhata}</h2>
            <p className="muted">{t.khataHint}</p>
            <p>
              <Link href="/khata">{t.khataTitle} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>🧑‍🌾 {t.navProfile}</h2>
            <p className="muted">{t.profileHint}</p>
            <p>
              <Link href="/profile-setup">{t.updateProfile} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>📊 {t.marketTitle}</h2>
            <p className="muted">{t.marketHint}</p>
            <p>
              <Link href="/market">{t.marketTitle} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>🤖 {t.aiTitle}</h2>
            <p className="muted">{t.aiGreeting}</p>
            <p>
              <Link href="/ai">{t.aiTitle} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>📸 {t.cropCheckTitle}</h2>
            <p className="muted">{t.cropCheckHint}</p>
            <p>
              <Link href="/crop-check">{t.cropCheckTitle} →</Link>
            </p>
          </div>

          <div className="card">
            <h2>🛒 {t.storeTitle}</h2>
            <p className="muted">{t.storeHint}</p>
            <p>
              <Link href="/store">{t.storeTitle} →</Link>
            </p>
          </div>

          <WeatherCard t={t} weather={weather} onRetry={loadDashboard} />
          <ForecastStrip t={t} language={language} forecast={forecast} />
        </div>
      </main>
    </AuthGate>
  );
}
