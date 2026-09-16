/**
 * POS Bill detail (Step 18, staff-only): server-computed totals, items,
 * payment split, receipt link + manager-only Cancel (staff 403).
 * No tax/GST row exists — totals = subtotal − discount + other.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  posItemProductName,
  posItemVariantName,
  type PosBill,
} from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";
import { formatPaise } from "../../../../../lib/khata";

export default function PosBillDetailPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [bill, setBill] = useState<PosBill | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [cancelForbidden, setCancelForbidden] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setBill(await api.getPosBill(token, params.id));
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setForbidden(true);
        setError("प्रवेश नाही — फक्त स्टाफ (Staff only).");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function onCancel() {
    if (!window.confirm("हे बिल रद्द करायचे का? Cancel this bill?")) return;
    const token = getStoredToken();
    if (!token || !bill || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const out = await api.cancelPosBill(token, bill.id, reason);
      setBill(out.bill);
      setCancelForbidden(false);
      setReason("");
      setNotice(
        out.duplicate
          ? "आधीच रद्द झाले होते (Already cancelled, duplicate=True)."
          : "बिल रद्द झाले Bill cancelled.",
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        // Backend is authoritative: cancel needs store_manager+ (STORE_MANAGER_REQUIRED).
        setCancelForbidden(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/pos/bills">← बिले Bills</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {notice ? <p className="muted">{notice}</p> : null}
        {!bill ? (
          forbidden ? (
            <p className="muted">प्रवेश नाही — हे पान फक्त स्टोअर स्टाफसाठी आहे (Staff only, 403).</p>
          ) : (
            <p className="muted">{t.loading}</p>
          )
        ) : (
          <>
            <section className="card">
              <h1>🧾 {bill.bill_number}</h1>
              <p className="muted">तारीख Date: {bill.created_at.slice(0, 10)}</p>
              <p>विक्री Sale: {bill.sale_status}</p>
              <p>पेमेंट Payment: {bill.payment_status}{bill.payment_mode ? ` · ${bill.payment_mode}` : ""}</p>
              <p className="muted">ग्राहक Customer: {bill.customer_id ?? "वॉक-इन Walk-in"}</p>
              {bill.payment_reference ? <p>संदर्भ Reference: {bill.payment_reference}</p> : null}
            </section>
            <section className="card">
              <h2>नोंदी Items</h2>
              {bill.items.length === 0 ? (
                <p className="muted">नोंदी नाहीत No items.</p>
              ) : (
                bill.items.map((it) => (
                  <p key={it.id}>
                    {posItemProductName(it)} · {posItemVariantName(it)} · नग Qty: {String(it.qty)} · ₹
                    {formatPaise(it.unit_price_paise)} → ₹{formatPaise(it.line_total_paise)}
                  </p>
                ))
              )}
              <p>उप-एकूण Subtotal: ₹{formatPaise(bill.subtotal_paise)}</p>
              <p>सूट Discount: ₹{formatPaise(bill.discount_paise)}</p>
              <p>इतर शुल्क Other Charges: ₹{formatPaise(bill.other_charges_paise)}</p>
              <p className="farm-area">एकूण Total: ₹{formatPaise(bill.total_paise)}</p>
              <p className="muted">कर (Tax/GST): लागू नाही — totals = subtotal − discount + other.</p>
            </section>
            <section className="card">
              <h2>पेमेंट तपशील Payment</h2>
              <p>भरले Paid: ₹{formatPaise(bill.amount_paid_paise)}</p>
              <p>मिळाले Received: {bill.amount_received_paise === null ? "—" : `₹${formatPaise(bill.amount_received_paise)}`}</p>
              <p>बाकी Balance Due: ₹{formatPaise(bill.balance_due_paise)}</p>
              <p className="muted">नोंद Notes: {bill.notes ?? "—"}</p>
              <p>
                <Link href={`/store/pos/bills/${bill.id}/receipt`}>पावती पहा/छापा Receipt →</Link>
              </p>
            </section>
            {bill.sale_status !== "cancelled" ? (
              <section className="card">
                <h2>बिल रद्द करा Cancel Bill</h2>
                {cancelForbidden ? (
                  <p className="muted">फक्त व्यवस्थापक — रद्द करण्यासाठी manager+ लागतो (staff 403 STORE_MANAGER_REQUIRED).</p>
                ) : (
                  <p className="muted">फक्त व्यवस्थापक Manager+ only — staff ला 403 मिळेल.</p>
                )}
                <label>
                  कारण Reason (ऐच्छिक optional)
                  <br />
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="उदा. चुकीची नोंद" />
                </label>
                <br />
                <button className="btn-danger" type="button" disabled={busy} onClick={onCancel}>
                  {busy ? t.loading : "रद्द करा Cancel"}
                </button>
              </section>
            ) : (
              <p className="muted">हे बिल रद्द झाले आहे (Cancelled).</p>
            )}
          </>
        )}
      </main>
    </AuthGate>
  );
}
