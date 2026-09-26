/**
 * Public landing: farmer-first welcome + login entry point (production app).
 * Authenticated users are redirected to /home by AuthGate — no demo content,
 * no backend status card, no roadmap, no raw API URLs.
 */
"use client";

import Link from "next/link";
import { AuthGate } from "../components/AuthGate";
import { LANGUAGES } from "../lib/i18n";
import { useAuth } from "../lib/auth";

export default function LandingPage() {
  const { t, language, setLanguage } = useAuth();

  return (
    <AuthGate mode="guest">
      <main className="main landing">
        <section className="hero">
          <h1>🌱 {t.appName}</h1>
          <p>{t.tagline}</p>
          <p className="landing-lead">{t.landingLead}</p>
          <Link href="/login" className="btn landing-cta">
            {t.landingCta}
          </Link>
        </section>

        <div className="grid">
          <div className="card">
            <h2>🌾 {t.myFarms}</h2>
            <p className="muted">{t.myFarmsHint}</p>
            <Link href="/farms">{t.openFarms} →</Link>
          </div>

          <div className="card">
            <h2>📊 {t.marketTitle}</h2>
            <p className="muted">{t.marketHint}</p>
            <Link href="/market">{t.marketTitle} →</Link>
          </div>

          <div className="card">
            <h2>🛒 {t.storeTitle}</h2>
            <p className="muted">{t.storeHint}</p>
            <Link href="/store">{t.storeTitle} →</Link>
          </div>

          <div className="card">
            <h2>🤖 {t.aiTitle}</h2>
            <p className="muted">{t.aiGreeting}</p>
            <Link href="/ai">{t.aiTitle} →</Link>
          </div>
        </div>

        <label className="field landing-lang">
          <span>{t.languageLabel}</span>
          <select
            aria-label={t.languageLabel}
            value={language}
            onChange={(e) => setLanguage(e.target.value as typeof language)}
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
      </main>
    </AuthGate>
  );
}
