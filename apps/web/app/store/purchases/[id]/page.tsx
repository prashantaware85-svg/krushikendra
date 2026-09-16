/**
 * Purchase detail (Step 16, auth-only): draft edit + add/remove items,
 * Save Draft (PUT, draft only), Receive (confirm), Cancel.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Purchase } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise } from "../../../../lib/khata";

function rupeesToPaise(s: string): number {
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.round(n * 100);
}

export default function PurchaseDetailPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [discountRs, setDiscountRs] = useState("");
  const [chargesRs, setChargesRs] = useState("");
  const [notes, setNotes] = useState("");
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("");
  const [unitCostRs, setUnitCostRs] = useState("");

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const p = await api.getPurchase(token, params.id);
      setPurchase(p);
      setDiscountRs(String((p.discount_paise ?? 0) / 100));
      setChargesRs(String((p.other_charges_paise ?? 0) / 100));
      setNotes(p.notes ?? "");
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  const isDraft = purchase?.status === "draft";

  async function onSaveDraft(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !purchase || busy) return;
    setBusy(true);
    try {
      const p = await api.updatePurchase(token, purchase.id, {
        discount_paise: discountRs.trim() ? rupeesToPaise(discountRs) : 0,
        other_charges_paise: chargesRs.trim() ? rupeesToPaise(chargesRs) : 0,
        notes: notes.trim() || null,
      });
      setPurchase(p);
      setNotice("मसुदा जतन झाला Draft saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onAddItem(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !purchase || busy) return;
    setBusy(true);
    try {
      await api.addPurchaseItem(token, purchase.id, {
        variant_id: variantId.trim(),
        qty: qty.trim(),
        unit_cost_paise: rupeesToPaise(unitCostRs),
      });
      setVariantId("");
      setQty("");
      setUnitCostRs("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveItem(itemId: string) {
    const token = getStoredToken();
    if (!token || !purchase || busy) return;
    setBusy(true);
    try {
      await api.removePurchaseItem(token, purchase.id, itemId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onReceive() {
    if (!window.confirm("साठा प्राप्त करायचा का? Receive this purchase into stock?")) return;
    const token = getStoredToken();
    if (!token || !purchase || busy) return;
    setBusy(true);
    try {
      const p = await api.receivePurchase(token, purchase.id);
      setPurchase(p);
      setNotice(p.duplicate ? "आधीच प्राप्त झाली होती (Already received)." : "प्राप्त झाली Received.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!window.confirm("ही खरेदी रद्द करायची का? Cancel this purchase?")) return;
    const token = getStoredToken();
    if (!token || !purchase || busy) return;
    setBusy(true);
    try {
      setPurchase(await api.cancelPurchase(token, purchase.id));
      setNotice("रद्द झाली Cancelled.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/purchases">← खरेदी Purchases</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {notice ? <p className="muted">{notice}</p> : null}
        {!purchase ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h1>🧾 {purchase.id.slice(0, 8)}</h1>
              <p className="muted">
                पुरवठादार Supplier: {purchase.supplier_name ?? "—"} · तारीख Date: {purchase.purchase_date ?? "—"}
              </p>
              <p>स्थिती Status: {purchase.status}</p>
              <p>{t.subtotalLabel}: ₹{formatPaise(purchase.subtotal_paise)}</p>
              <p>सूट Discount: ₹{formatPaise(purchase.discount_paise)}</p>
              <p>इतर शुल्क Other Charges: ₹{formatPaise(purchase.other_charges_paise)}</p>
              <p className="farm-area">{t.totalLabel}: ₹{formatPaise(purchase.total_paise)}</p>
              <p className="muted">नोंद Notes: {purchase.notes ?? "—"}</p>
            </section>
            <section className="card">
              <h2>नोंदी Items</h2>
              {purchase.items.length === 0 ? (
                <p className="muted">नोंदी नाहीत No items yet.</p>
              ) : (
                purchase.items.map((it) => (
                  <p key={it.id}>
                    {it.variant_name ?? it.variant_id.slice(0, 8)} · नग Qty: {it.qty} · ₹{formatPaise(it.line_total_paise)}
                    {isDraft ? (
                      <>
                        {" "}
                        <button type="button" className="link-btn-plain" disabled={busy} onClick={() => onRemoveItem(it.id)}>
                          काढा Remove
                        </button>
                      </>
                    ) : null}
                  </p>
                ))
              )}
              {isDraft ? (
                <form onSubmit={onAddItem}>
                  <input placeholder="Variant ID" value={variantId} onChange={(e) => setVariantId(e.target.value)} required />
                  {" "}
                  <input inputMode="decimal" placeholder="नग Qty" value={qty} onChange={(e) => setQty(e.target.value)} required />
                  {" "}
                  <input inputMode="decimal" placeholder="किंमत ₹ Unit Cost" value={unitCostRs} onChange={(e) => setUnitCostRs(e.target.value)} required />
                  {" "}
                  <button className="btn" type="submit" disabled={busy}>जोडा Add</button>
                </form>
              ) : null}
            </section>
            {isDraft ? (
              <section className="card">
                <h2>मसुदा बदला Edit Draft</h2>
                <form onSubmit={onSaveDraft}>
                  <label>सूट (₹) Discount<br />
                    <input inputMode="decimal" value={discountRs} onChange={(e) => setDiscountRs(e.target.value)} />
                  </label><br />
                  <label>इतर शुल्क (₹) Other Charges<br />
                    <input inputMode="decimal" value={chargesRs} onChange={(e) => setChargesRs(e.target.value)} />
                  </label><br />
                  <label>नोंद Notes<br />
                    <input value={notes} onChange={(e) => setNotes(e.target.value)} />
                  </label><br />
                  <button className="btn" type="submit" disabled={busy}>{busy ? t.loading : "मसुदा जतन करा Save Draft"}</button>
                </form>
                <p>
                  <button className="btn" type="button" disabled={busy} onClick={onReceive}>
                    प्राप्त करा Receive
                  </button>
                  {" "}
                  <button className="btn-danger" type="button" disabled={busy} onClick={onCancel}>
                    रद्द करा Cancel
                  </button>
                </p>
              </section>
            ) : null}
          </>
        )}
      </main>
    </AuthGate>
  );
}
