/**
 * App navigation shell (production app).
 *
 * Mobile: fixed bottom navigation with the five primary destinations.
 * Desktop: sticky top bar with the full destination set + logout.
 *
 * Rendered from the root layout; hides itself on public routes
 * (landing / login / verify-otp) and until the session is authenticated.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";

const PUBLIC_PATHS = ["/", "/login", "/verify-otp"];

const BOTTOM_ITEMS = [
  { href: "/home", key: "navHome" as const, icon: "🏠", exact: true },
  { href: "/farms", key: "navFarms" as const, icon: "🌾", exact: false },
  { href: "/market", key: "navMarket" as const, icon: "📊", exact: false },
  { href: "/store", key: "navStore" as const, icon: "🛒", exact: false },
  { href: "/khata", key: "navKhata" as const, icon: "📒", exact: false },
];

const TOP_ITEMS = [
  ...BOTTOM_ITEMS,
  { href: "/ai", key: "navAi" as const, icon: "🤖", exact: false },
  { href: "/crop-check", key: "navCropCheck" as const, icon: "📸", exact: false },
  { href: "/store/orders", key: "navOrders" as const, icon: "📦", exact: false },
  { href: "/profile-setup", key: "navProfile" as const, icon: "🧑‍🌾", exact: false },
];

export function AppNav() {
  const { status, t, logout } = useAuth();
  const pathname = usePathname();

  if (status !== "authed") return null;
  if (!pathname || PUBLIC_PATHS.includes(pathname)) return null;

  function isActive(href: string, exact: boolean): boolean {
    if (exact) return pathname === href;
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <>
      <nav className="app-topnav" aria-label="App navigation">
        <Link href="/home" className="app-brand">
          🌱 {t.appName}
        </Link>
        {TOP_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={isActive(item.href, item.exact) ? "nav-active" : undefined}
          >
            {t[item.key]}
          </Link>
        ))}
        <button className="link-btn-plain app-logout" type="button" onClick={logout}>
          {t.logout}
        </button>
      </nav>

      <nav className="app-bottomnav" aria-label="App navigation">
        {BOTTOM_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={isActive(item.href, item.exact) ? "nav-active" : undefined}
          >
            <span aria-hidden="true">{item.icon}</span>
            {t[item.key]}
          </Link>
        ))}
      </nav>
    </>
  );
}
