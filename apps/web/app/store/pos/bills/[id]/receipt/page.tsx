/**
 * POS Receipt (Step 18, staff-only): print-friendly JSON receipt +
 * window.print() button. Print CSS hides navigation/chrome.
 * No tax/GST row — the backend has no GST engine (see docs/pos.md).
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type PosReceipt } from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";
import { formatPaise } from "../../../../../../lib/khata";

export default function PosReceiptPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [receipt, setReceipt] = useState<PosReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setReceipt(await api.posReceipt(token, params.id));
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
        <style>{`@media print { .no-print { display: none !important; } .main { max-width: 100%; padding: 0; } .card { border: none; } }`}</style>
        <div className="no-print">
          <p>
            <Link href={`/store/pos/bills/${params.id}`}>← बिल Bill</Link>
          </p>
          {error ? <p className="form-error">{error}</p> : null}
          <p className="muted small">कर (Tax/GST): लागू नाही — totals = subtotal − discount + other (see docs/pos.md).</p>
        </div>
        {!receipt ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h1>{String(receipt.store?.name ?? "Krushi Seva Kendra")}</h1>
              <p className="muted">बिल Bill: {receipt.bill_number}</p>
              <p className="muted">दिनांक Date: {String(receipt.created_at).slice(0, 16).replace("T", " ")}</p>
              <p className="muted">कॅशियर Cashier: {receipt.cashier}</p>
              <p className="muted">ग्राहक Customer: {receipt.customer ?? "वॉक-इन Walk-in"}</p>
              <hr />
              {receipt.items.map((it, i) => (
                <p key={i}>
                  {it.product_name} · {it.variant_name}
                  <br />
                  नग Qty: {String(it.qty)} × ₹{formatPaise(it.unit_price_paise)} = ₹{formatPaise(it.line_total_paise)}
                </p>
              ))}
              <hr />
              <p>उप-एकूण Subtotal: ₹{formatPaise(receipt.subtotal_paise)}</p>
              <p>सूट Discount: ₹{formatPaise(receipt.discount_paise)}</p>
              <p>इतर Other: ₹{formatPaise(receipt.other_charges_paise)}</p>
              <p className="farm-area">एकूण Total: ₹{formatPaise(receipt.total_paise)}</p>
              <p className="muted">
                विक्री Sale: {receipt.sale_status} · पेमेंट Payment: {receipt.payment_status}
              </p>
              <p className="muted">
                पद्धत Mode: {receipt.payment?.mode ?? "—"}
                {receipt.payment?.paid_paise !== null && receipt.payment?.paid_paise !== undefined
                  ? ` · भरले Paid: ₹${formatPaise(receipt.payment.paid_paise)}`
                  : ""}
                {receipt.payment?.received_paise !== null && receipt.payment?.received_paise !== undefined
                  ? ` · मिळाले Received: ₹${formatPaise(receipt.payment.received_paise)}`
                  : ""}
                {receipt.payment?.change_paise !== null && receipt.payment?.change_paise !== undefined
                  ? ` · सुटे Change: ₹${formatPaise(receipt.payment.change_paise)}`
                  : ""}
                {receipt.payment?.balance_due_paise ? ` · बाकी Due: ₹${formatPaise(receipt.payment.balance_due_paise)}` : ""}
                {receipt.payment?.reference ? ` · संदर्भ Ref: ${receipt.payment.reference}` : ""}
              </p>
              {receipt.payment?.refund_note ? <p className="muted">{receipt.payment.refund_note}</p> : null}
              <p>{receipt.footer}</p>
            </section>
            <div className="no-print">
              <p>
                <button type="button" className="btn" onClick={() => window.print()}>
                  छापा Print
                </button>
              </p>
            </div>
          </>
        )}
      </main>
    </AuthGate>
  );
}
