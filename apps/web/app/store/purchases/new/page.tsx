/**
 * New purchase (Step 16, auth-only): create a draft, then add items.
 * Rupees inputs → paise ints; qty kept as decimal string.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Purchase, type Supplier } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise } from "../../../../lib/khata";

function rupeesToPaise(s: string): number {
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.round(n * 100);
}

export default function NewPurchasePage() {
  const { t } = useAuth();
  const router = useRouter();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [discountRs, setDiscountRs] = useState("");
  const [chargesRs, setChargesRs] = useState("");
  const [notes, setNotes] = useState("");
  const [draft, setDraft] = useState<Purchase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // add-item form
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("");
  const [unitCostRs, setUnitCostRs] = useState("");

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    api.listSuppliers(token).then(setSuppliers).catch(() => undefined);
  }, []);

  const reload = useCallback(async (id: string) => {
    const token = getStoredToken();
    if (!token) return;
    setDraft(await api.getPurchase(token, id));
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy) return;
    setBusy(true);
    try {
      const p = await api.createPurchase(token, {
        supplier_id: supplierId || null,
        purchase_date: purchaseDate || null,
        discount_paise: discountRs.trim() ? rupeesToPaise(discountRs) : undefined,
        other_charges_paise: chargesRs.trim() ? rupeesToPaise(chargesRs) : undefined,
        notes: notes.trim() || null,
      });
      setDraft(p);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onAddItem(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !draft || busy || !variantId.trim() || !qty.trim() || !unitCostRs.trim()) return;
    setBusy(true);
    try {
      await api.addPurchaseItem(token, draft.id, {
        variant_id: variantId.trim(),
        qty: qty.trim(),
        unit_cost_paise: rupeesToPaise(unitCostRs),
      });
      setVariantId("");
      setQty("");
      setUnitCostRs("");
      await reload(draft.id);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveItem(itemId: string) {
    const token = getStoredToken();
    if (!token || !draft || busy) return;
    setBusy(true);
    try {
      await api.removePurchaseItem(token, draft.id, itemId);
      await reload(draft.id);
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
        <h1>＋ नवीन खरेदी New Purchase</h1>
        {error ? <p className="form-error">{error}</p> : null}
        {!draft ? (
          <section className="card">
            <h2>मसुदा तयार करा Create Draft</h2>
            <form onSubmit={onCreate}>
              <label>पुरवठादार Supplier<br />
                <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">— निवडा नाही No supplier —</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </label><br />
              <label>खरेदी तारीख Purchase Date<br />
                <input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
              </label><br />
              <label>सूट (₹) Discount<br />
                <input inputMode="decimal" placeholder="0" value={discountRs} onChange={(e) => setDiscountRs(e.target.value)} />
              </label><br />
              <label>इतर शुल्क (₹) Other Charges<br />
                <input inputMode="decimal" placeholder="0" value={chargesRs} onChange={(e) => setChargesRs(e.target.value)} />
              </label><br />
              <label>नोंद Notes<br />
                <input value={notes} onChange={(e) => setNotes(e.target.value)} />
              </label><br />
              <button className="btn" type="submit" disabled={busy}>{busy ? t.loading : "मसुदा तयार करा Create Draft"}</button>
            </form>
          </section>
        ) : (
          <>
            <section className="card">
              <h2>मसुदा Draft: {draft.id.slice(0, 8)}</h2>
              <p className="farm-area">एकूण Total: ₹{formatPaise(draft.total_paise)}</p>
              {draft.items.map((it) => (
                <p key={it.id}>
                  {it.variant_name ?? it.variant_id.slice(0, 8)} · नग Qty: {it.qty} · ₹{formatPaise(it.line_total_paise)}
                  {" "}
                  <button type="button" className="link-btn-plain" disabled={busy} onClick={() => onRemoveItem(it.id)}>
                    काढा Remove
                  </button>
                </p>
              ))}
            </section>
            <section className="card">
              <h2>नोंद जोडा Add Item</h2>
              <form onSubmit={onAddItem}>
                <label>Variant ID<br />
                  <input value={variantId} onChange={(e) => setVariantId(e.target.value)} required placeholder="variant UUID" />
                </label><br />
                <label>नग Qty<br />
                  <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required placeholder="e.g. 10 or 2.5" />
                </label><br />
                <label>एकक किंमत (₹) Unit Cost<br />
                  <input inputMode="decimal" value={unitCostRs} onChange={(e) => setUnitCostRs(e.target.value)} required placeholder="0.00" />
                </label><br />
                <button className="btn" type="submit" disabled={busy}>{busy ? t.loading : "जोडा Add"}</button>
              </form>
            </section>
            <p>
              <button type="button" className="btn" onClick={() => router.push(`/store/purchases/${draft.id}`)}>
                पुढे जा Continue →
              </button>
            </p>
          </>
        )}
      </main>
    </AuthGate>
  );
}
