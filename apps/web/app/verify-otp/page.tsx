/**
 * OTP verification screen (guest-only): code → session → home/profile-setup.
 */
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const MOBILE_KEY = "krushi.login_mobile";

export default function VerifyOtpPage() {
  const { t, sendOtp, verifyOtp } = useAuth();
  const router = useRouter();
  const [mobile, setMobile] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(MOBILE_KEY);
    if (!saved) router.replace("/login");
    else setMobile(saved);
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!mobile) return;
    setError(null);
    setBusy(true);
    try {
      const { needsProfile } = await verifyOtp(mobile, otp);
      sessionStorage.removeItem(MOBILE_KEY);
      router.push(needsProfile ? "/profile-setup" : "/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    if (!mobile) return;
    setError(null);
    setInfo(null);
    try {
      const res = await sendOtp(mobile);
      setDevOtp(res.dev_otp ?? null);
      setInfo(`${t.sendOtp} ✓`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resend OTP.");
    }
  }

  return (
    <AuthGate mode="guest">
      <main className="main auth-wrap">
        <section className="card auth-card">
          <h2>{t.verifyTitle}</h2>
          <p className="muted">
            {t.verifySubtitle} <code>{mobile ?? "…"}</code>
          </p>
          {devOtp ? (
            <p className="dev-banner">
              {t.devOtpNote} <code>{devOtp}</code>
            </p>
          ) : null}
          <form onSubmit={onSubmit}>
            <label className="field">
              <span>{t.otpLabel}</span>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder={t.otpPlaceholder}
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
              />
            </label>
            {error ? <p className="form-error">{error}</p> : null}
            {info ? <p className="form-ok">{info}</p> : null}
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t.verifying : t.verify}
            </button>
          </form>
          <button className="btn-secondary" type="button" onClick={onResend}>
            {t.resend}
          </button>
        </section>
      </main>
    </AuthGate>
  );
}
