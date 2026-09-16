/**
 * Authenticated home (auth-only): greeting + profile + farm entry + weather + logout.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ForecastStrip } from "../../components/ForecastStrip";
import { WeatherCard } from "../../components/WeatherCard";
import { ApiError, api, getStoredToken, type WeatherCurrent, type WeatherForecast } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function HomePage() {
  const { t, language, user, logout } = useAuth();
  const profile = user?.profile;
  const [weather, setWeather] = useState<WeatherCurrent | null | undefined>(undefined);
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);

  // Home weather: first farm (oldest) that has GPS coordinates.
  // No GPS anywhere → unavailable state (never forced, never faked).
  const loadWeather = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    setWeather(undefined);
    try {
      const farms = await api.listFarms(token);
      const located = farms.find((f) => f.latitude && f.longitude);
      if (!located) {
        setWeather(null);
        return;
      }
      const [w, fc] = await Promise.all([
        api.weatherCurrent(token, located.id),
        api.weatherForecast(token, located.id).catch(() => null),
      ]);
      setWeather(w);
      setForecast(fc);
    } catch {
      setWeather(null);
    }
  }, []);

  useEffect(() => {
    loadWeather();
  }, [loadWeather]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <section className="hero">
          <span className="badge">STEP 3 · Farmer Auth</span>
          <h1>
            {t.homeTitle} {profile?.full_name ?? ""}
          </h1>
          <p>{t.homeSubtitle}</p>
        </section>

        <div className="grid">
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

          <WeatherCard t={t} weather={weather} onRetry={loadWeather} />
          <ForecastStrip t={t} language={language} forecast={forecast} />
        </div>
      </main>
    </AuthGate>
  );
}
