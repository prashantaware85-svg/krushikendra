import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "../lib/auth";
import { AppNav } from "../components/AppNav";

export const metadata: Metadata = {
  title: "Krushi Seva — Empowering Indian Farmers",
  description:
    "Krushi Seva farmer platform: OTP login, farmer profiles, and agri services.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="mr">
      <body>
        <AuthProvider>
          {children}
          <AppNav />
        </AuthProvider>
      </body>
    </html>
  );
}
