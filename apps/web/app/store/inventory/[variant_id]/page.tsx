/**
 * Inventory detail (Step 16, auth-only): stock levels + movement history
 * + adjust form with before/after preview. Server is authoritative —
 * after every adjust the detail + movements reload from the backend.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type InventoryDetail,
  type MovementPage,
} from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { stockBadge } from "../../../../components/stockBadge";

export default function InventoryDetailPage({ params }: { params: { variant_id: string } }) {
  const { t } = useAuth();
  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [movements, setMovements] = useState<MovementPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [movementType, setMovementType] = useState("adjustment");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  // ── Step 17: reorder level (visible to all; PUT is admin+manager, staff 403) ──
  const [reorderLevel, setReorderLevel] = useState("");
  const [reorderQty, setReorderQty] = useState("");
  const [reorderBusy, setReorderBusy] = useState(false);
  const [reorderForbidden, setReorderForbidden] = useState(false);
  const [reorderError, setReorderError] = useState<string | null>(null);

  const load = useCallback(async (movementTypeFilter?: string) => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setDetail(await api.getInventory(token, params.variant_id));
      setMovements(
        await api.inventoryMovements(token, params.variant_id, {
          ...(movementTypeFilter ? { movement_type: movementTypeFilter } : {}),
          limit: 50,
          offset: 0,
        }),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.variant_id]);

  useEffect(() => {
    load();
  }, [load]);

  function previewAfter(): string | null {
    if (!detail || !quantity.trim()) return null;
    const before = Number(detail.qty_on_hand);
    const delta = Number(quantity);
    if (!Number.isFinite(before) || !Number.isFinite(delta)) return null;
    // Preview only — the server computes the authoritative qty_after.
    return String(before + delta);
  }

  async function onAdjust(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy || !quantity.trim()) return;
    setBusy(true);
    try {
      await api.adjustInventory(token, params.variant_id, {
        movement_type: movementType,
        quantity: quantity.trim(),
        reason: reason.trim() || null,
      });
      setQuantity("");
      setReason("");
      setNotice("जतन झाले Adjustment saved — server values reloaded.");
      await load(typeFilter || undefined);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  function onFilter(e: React.FormEvent) {
    e.preventDefault();
    load(typeFilter || undefined);
  }

  function reorderQuantityOf(d: InventoryDetail): string {
    return d.reorder_quantity ?? d.reorder_qty ?? "—";
  }

  async function onSaveReorder(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || reorderBusy) return;
    // Frontend validation mirrors the contract; the backend stays authoritative.
    if (reorderLevel.trim() === "" || Number(reorderLevel) < 0 || !Number.isFinite(Number(reorderLevel))) {
      setReorderError("पुनःऑर्डर पातळी ≥ 0 हवी Reorder level must be >= 0.");
      return;
    }
    if (reorderQty.trim() !== "" && (!(Number(reorderQty) > 0) || !Number.isFinite(Number(reorderQty)))) {
      setReorderError("पुनःऑर्डर प्रमाण > 0 हवे Reorder quantity must be > 0.");
      return;
    }
    setReorderBusy(true);
    try {
      await api.updateReorderLevel(token, params.variant_id, {
        reorder_level: reorderLevel.trim(),
        ...(reorderQty.trim() ? { reorder_quantity: reorderQty.trim() } : {}),
      });
      setReorderQty("");
      setReorderError(null);
      setReorderForbidden(false);
      setNotice("पुनःऑर्डर पातळी जतन झाली Reorder level saved — server values reloaded.");
      await load(typeFilter || undefined);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        // No frontend role guess: the 403 from PUT is the signal (staff read-only).
        setReorderForbidden(true);
        setReorderError(null);
      } else {
        setReorderError(err instanceof ApiError ? err.message : "Error");
      }
    } finally {
      setReorderBusy(false);
    }
  }

  const after = previewAfter();

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/store/inventory">← साठा Inventory</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {notice ? <p className="muted">{notice}</p> : null}
        {!detail ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="card">
              <h1>{stockBadge(detail.status)} {detail.product_name ?? detail.variant_id.slice(0, 8)}</h1>
              <p className="muted">{detail.variant_name ?? ""}{detail.sku ? ` · SKU: ${detail.sku}` : ""}</p>
              <p>हातात On Hand: {detail.qty_on_hand}</p>
              <p>राखीव Reserved: {detail.qty_reserved}</p>
              <p>उपलब्ध Available: {detail.available}</p>
              <p className="muted">स्थिती Status: {detail.status}</p>
              <p>पुनःऑर्डर पातळी Reorder Level: {detail.reorder_level ?? "—"}</p>
              <p>पुनःऑर्डर प्रमाण Reorder Quantity: {reorderQuantityOf(detail)}</p>
            </section>
            <section className="card">
              <h2>पुनःऑर्डर पातळी Edit Reorder Level</h2>
              {reorderForbidden ? (
                <p className="muted">फक्त व्यवस्थापक Read-only — reorder edits need admin/manager (staff 403).</p>
              ) : null}
              {reorderError ? <p className="form-error">{reorderError}</p> : null}
              <form onSubmit={onSaveReorder}>
                <label>पुनःऑर्डर पातळी Reorder Level (≥ 0)<br />
                  <input
                    inputMode="decimal"
                    value={reorderLevel}
                    onChange={(e) => setReorderLevel(e.target.value)}
                    placeholder={String(detail.reorder_level ?? "0")}
                  />
                </label><br />
                <label>पुनःऑर्डर प्रमाण Reorder Quantity (&gt; 0, ऐच्छिक optional)<br />
                  <input
                    inputMode="decimal"
                    value={reorderQty}
                    onChange={(e) => setReorderQty(e.target.value)}
                    placeholder={reorderQuantityOf(detail)}
                  />
                </label><br />
                <button className="btn" type="submit" disabled={reorderBusy || !reorderLevel.trim()}>
                  {reorderBusy ? t.loading : "जतन करा Save"}
                </button>
              </form>
            </section>
            <section className="card">
              <h2>साठा समायोजन Adjust Stock</h2>
              <form onSubmit={onAdjust}>
                <label>प्रकार Movement Type<br />
                  <select value={movementType} onChange={(e) => setMovementType(e.target.value)}>
                    <option value="adjustment">समायोजन Adjustment</option>
                    <option value="purchase">खरेदी Purchase</option>
                    <option value="sale">विक्री Sale</option>
                    <option value="return">परतावा Return</option>
                    <option value="damage">नुकसान Damage</option>
                  </select>
                </label><br />
                <label>प्रमाण Quantity (+/−)<br />
                  <input inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} required placeholder="e.g. 5 or -2" />
                </label><br />
                <label>कारण Reason<br />
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="उदा. मोजणी दुरुस्ती" />
                </label><br />
                <p className="muted">
                  आधी Before: {detail.qty_on_hand}
                  {after !== null ? ` → नंतर After (अंदाज preview): ${after}` : ""}
                </p>
                <button className="btn" type="submit" disabled={busy || !quantity.trim()}>
                  {busy ? t.loading : "जतन करा Save"}
                </button>
              </form>
            </section>
            <section className="card">
              <h2>हालचाल इतिहास Movement History</h2>
              <form onSubmit={onFilter}>
                <input placeholder="प्रकार Filter by type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} />
                {" "}
                <button className="btn" type="submit">लागू करा Apply</button>
              </form>
              {!movements ? (
                <p className="muted">{t.loading}</p>
              ) : movements.movements.length === 0 ? (
                <p className="muted">हालचाल नाही No movements yet.</p>
              ) : (
                movements.movements.map((m) => (
                  <p key={m.id} className="muted">
                    {m.created_at.slice(0, 10)} · {m.movement_type} · {m.quantity}
                    {m.qty_before !== null ? ` (${m.qty_before} → ${m.qty_after ?? "—"})` : ""}
                    {m.reason ? ` · ${m.reason}` : ""}
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
