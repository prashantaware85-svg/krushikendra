/**
 * Auth session provider (Step 3).
 *
 * Responsibilities:
 * - login state (guest | loading | authed) shared across screens
 * - token persistence in localStorage + restore on page refresh
 *   (Step 3 uses localStorage; httpOnly-cookie hardening is a documented
 *   future step — see docs/authentication.md)
 * - language preference (profile value, overridable locally)
 * - sendOtp / verifyOtp / logout actions used by the screens
 */
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api, type MeResponse } from "./api";
import { getStrings, type Language, type StringKey } from "./i18n";

const ACCESS_KEY = "krushi.access_token";
const REFRESH_KEY = "krushi.refresh_token";
const LANG_KEY = "krushi.language";

export type AuthStatus = "loading" | "guest" | "authed";

type AuthContextValue = {
  status: AuthStatus;
  user: MeResponse | null;
  language: Language;
  t: Record<StringKey, string>;
  setLanguage: (lang: Language) => void;
  sendOtp: (mobile: string) => Promise<{ mobile_number: string; dev_otp?: string | null }>;
  verifyOtp: (mobile: string, otp: string) => Promise<{ isNewUser: boolean; needsProfile: boolean }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readStorage(): { access: string | null; refresh: string | null; lang: Language } {
  // Marathi-first: farmers see मराठी unless they (or their profile) chose otherwise.
  if (typeof window === "undefined") return { access: null, refresh: null, lang: "mr" };
  const lang = window.localStorage.getItem(LANG_KEY);
  return {
    access: window.localStorage.getItem(ACCESS_KEY),
    refresh: window.localStorage.getItem(REFRESH_KEY),
    lang: lang === "hi" || lang === "en" ? lang : "mr",
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<MeResponse | null>(null);
  const [language, setLanguageState] = useState<Language>("mr");

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      window.localStorage.setItem(LANG_KEY, lang);
    } catch {
      /* storage unavailable — preference just won't persist */
    }
  }, []);

  /** Restore session after page refresh: /me, else one refresh attempt. */
  useEffect(() => {
    const { access, refresh, lang } = readStorage();
    setLanguageState(lang);
    (async () => {
      if (!access) {
        setStatus("guest");
        return;
      }
      try {
        const me = await api.me(access);
        setUser(me);
        if (me.profile?.preferred_language) setLanguageState(me.profile.preferred_language);
        setStatus("authed");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401 && refresh) {
          try {
            const pair = await api.refresh(refresh);
            window.localStorage.setItem(ACCESS_KEY, pair.access_token);
            window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
            const me = await api.me(pair.access_token);
            setUser(me);
            setStatus("authed");
            return;
          } catch {
            /* refresh failed — fall through to guest */
          }
        }
        window.localStorage.removeItem(ACCESS_KEY);
        window.localStorage.removeItem(REFRESH_KEY);
        setStatus("guest");
      }
    })();
  }, []);

  const sendOtp = useCallback(async (mobile: string) => {
    const res = await api.sendOtp(mobile);
    return { mobile_number: res.mobile_number, dev_otp: res.dev_otp ?? undefined };
  }, []);

  const verifyOtp = useCallback(async (mobile: string, otp: string) => {
    const pair = await api.verifyOtp(mobile, otp);
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    const me = await api.me(pair.access_token);
    setUser(me);
    if (me.profile?.preferred_language) setLanguage(me.profile.preferred_language);
    setStatus("authed");
    const needsProfile = pair.is_new_user || !me.profile?.full_name;
    return { isNewUser: pair.is_new_user, needsProfile };
  }, [setLanguage]);

  const logout = useCallback(async () => {
    const refresh = readStorage().refresh;
    if (refresh) {
      try {
        await api.logout(refresh);
      } catch {
        /* server revocation is best-effort — always clear locally */
      }
    }
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    setUser(null);
    setStatus("guest");
  }, []);

  const refreshUser = useCallback(async () => {
    const { access } = readStorage();
    if (!access) return;
    const me = await api.me(access);
    setUser(me);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      language,
      t: getStrings(language),
      setLanguage,
      sendOtp,
      verifyOtp,
      logout,
      refreshUser,
    }),
    [status, user, language, setLanguage, sendOtp, verifyOtp, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}
