/**
 * Route guard: redirects guests away from protected pages and
 * authenticated users away from guest-only pages (login/verify).
 */
"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "../lib/auth";

export function AuthGate({
  mode,
  children,
}: {
  mode: "auth" | "guest";
  children: ReactNode;
}) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading") return;
    if (mode === "auth" && status === "guest") router.replace("/login");
    if (mode === "guest" && status === "authed") router.replace("/home");
  }, [status, mode, router]);

  if (status === "loading") {
    return (
      <main className="main">
        <p className="muted">Loading…</p>
      </main>
    );
  }
  if (mode === "auth" && status === "guest") return null;
  if (mode === "guest" && status === "authed") return null;
  return <>{children}</>;
}
