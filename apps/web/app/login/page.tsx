/**
 * Mobile login screen (guest-only): mobile number → send OTP → /verify-otp.
 */
"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthGate } from "../../components/AuthGate";
import { LANGUAGES } from "../../lib/i18n";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const MOBILE_KEY = "krushi.login_mobile";

export default function LoginPage() {
  const { t, language, setLanguage, sendOtp } = useAuth();
  const router = useRouter();
  const [mobile, setMobile] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { mobile_number } = await sendOtp(mobile);
      sessionStorage.setItem(MOBILE_KEY, mobile_number);
      router.push("/verify-otp");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send OTP.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="guest">
      <main className="main auth-wrap">
        <section className="card auth-card">
          <h1>🌱 {t.appName}</h1>
          <p className="muted">{t.tagline}</p>
          <h2>{t.loginTitle}</h2>
          <p className="muted">{t.loginSubtitle}</p>

          <label className="field">
            <span>{t.mobileLabel}</span>
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

          <form onSubmit={onSubmit}>
            <label className="field">
              <span>{t.mobileLabel}</span>
              <input
                inputMode="numeric"
                autoComplete="tel"
                placeholder={t.mobilePlaceholder}
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                required
              />
            </label>
            {error ? <p className="form-error">{error}</p> : null}
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t.sending : t.sendOtp}
            </button>
          </form>
        </section>
      </main>
    </AuthGate>
  );
}
