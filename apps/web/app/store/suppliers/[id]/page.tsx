/**
 * Supplier detail (Step 16, auth-only): master record + purchase history.
 * Purchase history comes from GET /store/purchases?supplier_id=.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Purchase, type Supplier } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise } from "../../../../lib/khata";

export default function SupplierDetailPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [purchases, setPurchases] = useState<Purchase[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setSupplier(await api.getSupplier(token, params.id));
      setPurchases(await api.listPurchases(token, { supplier_id: params.id }));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/suppliers">← पुरवठादार Suppliers</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!supplier ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h1>🏭 {supplier.name}</h1>
              <p className="muted">मोबाईल Mobile: {supplier.mobile_number ?? "—"}</p>
              <p className="muted">ईमेल Email: {supplier.email ?? "—"}</p>
              <p className="muted">पत्ता Address: {supplier.address ?? "—"}</p>
              <p className="muted">नोंद Notes: {supplier.notes ?? "—"}</p>
              <p>{supplier.is_active ? "सक्रिय Active" : "बंद Inactive"}</p>
            </section>
            <section className="card">
              <h2>खरेदी इतिहास Purchase History</h2>
              {purchases === null ? (
                <p className="muted">{t.loading}</p>
              ) : purchases.length === 0 ? (
                <p className="muted">खरेदी नाही No purchases from this supplier.</p>
              ) : (
                purchases.map((p) => (
                  <p key={p.id}>
                    <Link href={`/store/purchases/${p.id}`}>{p.id.slice(0, 8)}</Link>
                    {" · "}{p.status}
                    {" · "}{p.purchase_date ?? "—"}
                    {" · ₹"}{formatPaise(p.total_paise)}
                  </p>
                ))
              )}
            </section>
          </>
        )}
      </main>
    </AuthGate>
  );
}
