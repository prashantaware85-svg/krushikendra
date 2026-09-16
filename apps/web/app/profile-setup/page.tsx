/**
 * Farmer profile setup screen (authenticated): basic details → /home.
 */
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ApiError, api } from "../../lib/api";
import { LANGUAGES } from "../../lib/i18n";
import { useAuth } from "../../lib/auth";

export default function ProfileSetupPage() {
  const { t, user, language, setLanguage, refreshUser } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: "",
    state: "",
    district: "",
    taluka: "",
    village: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.profile) {
      setForm({
        full_name: user.profile.full_name ?? "",
        state: user.profile.state ?? "",
        district: user.profile.district ?? "",
        taluka: user.profile.taluka ?? "",
        village: user.profile.village ?? "",
      });
    }
  }, [user]);

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const access = window.localStorage.getItem("krushi.access_token");
      if (!access) throw new ApiError(401, "AUTH_UNAUTHORIZED", "Session missing.");
      const saved = await api.updateProfile(access, {
        full_name: form.full_name || undefined,
        preferred_language: language,
        state: form.state || undefined,
        district: form.district || undefined,
        taluka: form.taluka || undefined,
        village: form.village || undefined,
      });
      setLanguage(saved.preferred_language);
      await refreshUser();
      router.push("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <section className="card auth-card">
          <h2>{t.profileSetupTitle}</h2>
          <p className="muted">{t.profileSetupSubtitle}</p>
          <form onSubmit={onSubmit}>
            <label className="field">
              <span>{t.fullNameLabel}</span>
              <input
                value={form.full_name}
                onChange={(e) => set("full_name", e.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>{t.languageLabel}</span>
              <select
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
            {(
              [
                ["state", t.stateLabel],
                ["district", t.districtLabel],
                ["taluka", t.talukaLabel],
                ["village", t.villageLabel],
              ] as const
            ).map(([key, label]) => (
              <label className="field" key={key}>
                <span>{label}</span>
                <input value={form[key]} onChange={(e) => set(key, e.target.value)} />
              </label>
            ))}
            {error ? <p className="form-error">{error}</p> : null}
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t.saving : t.saveProfile}
            </button>
          </form>
        </section>
      </main>
    </AuthGate>
  );
}
