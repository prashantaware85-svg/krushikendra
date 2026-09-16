/**
 * POS Counter (Step 18, staff-only): product search + draft bill panel +
 * create (draft) + payment modal + complete + today's summary.
 *
 * No customer-search endpoint exists, so the counter defaults to walk-in
 * (customer_id null) with an optional manual customer-ID (users.id UUID)
 * input — staff paste it from the customers/Khata screen. Credit and
 * partial payments REQUIRE a customer (backend 422 POS_CUSTOMER_REQUIRED).
 *
 * Money is integer paise end-to-end (₹ inputs × 100); quantities are
 * decimal strings. Server math always wins — line previews below are
 * estimates only. No tax/GST row exists (totals = subtotal − discount +
 * other); see docs/pos.md.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type PosBill,
  type PosProduct,
  type PosSummary,
} from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { formatPaise } from "../../../lib/khata";

type DraftLine = {
  product: PosProduct;
  qty: string;
};

function rupeesToPaise(s: string): number {
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.round(n * 100);
}

/** Client-side line preview only — the backend recomputes authoritatively. */
function previewLineTotal(qtyStr: string, unitPricePaise: number): number {
  const q = Number(qtyStr);
  if (!Number.isFinite(q) || q <= 0) return 0;
  return Math.round(q * unitPricePaise);
}

function saleStatusLabel(s: string): string {
  if (s === "draft") return "मसुदा Draft";
  if (s === "completed") return "पूर्ण Completed";
  if (s === "cancelled") return "रद्द Cancelled";
  return s;
}

function paymentStatusLabelPos(s: string): string {
  if (s === "pending") return "थकबाकी Pending";
  if (s === "paid") return "भरले Paid";
  if (s === "partial") return "अर्धवट Partial";
  if (s === "credit") return "उधार Credit";
  return s;
}

const PAYMENT_MODES = ["cash", "upi", "card", "credit"] as const;

export default function PosCounterPage() {
  const { t } = useAuth();
  const [products, setProducts] = useState<PosProduct[] | null>(null);
  const [summary, setSummary] = useState<PosSummary | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(false);

  // Draft bill panel (client-side until POST /bills).
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [discountRs, setDiscountRs] = useState("");
  const [chargesRs, setChargesRs] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  // Created draft bill + payment modal.
  const [bill, setBill] = useState<PosBill | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [payOpen, setPayOpen] = useState(false);
  const [payMode, setPayMode] = useState<string>("cash");
  const [receivedRs, setReceivedRs] = useState("");
  const [reference, setReference] = useState("");
  const [partialRs, setPartialRs] = useState("");
  const [payBusy, setPayBusy] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  const load = useCallback(async (q?: string) => {
    const token = getStoredToken();
    if (!token) return;
    setLoading(true);
    try {
      const [items, sum] = await Promise.all([
        api.listPosProducts(token, {
          ...(q && q.trim() ? { search: q.trim() } : {}),
          limit: 50,
          offset: 0,
        }),
        api.posSummary(token),
      ]);
      setProducts(items);
      setSummary(sum);
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setForbidden(true);
        setProducts([]);
        setError("प्रवेश नाही — फक्त स्टाफ (Staff only).");
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    load(search);
  }

  function addLine(p: PosProduct) {
    if (p.price_on_request || p.unit_price_paise === null) return;
    setLines((prev) => {
      const found = prev.find((l) => l.product.variant_id === p.variant_id);
      if (found) {
        return prev.map((l) =>
          l.product.variant_id === p.variant_id
            ? { ...l, qty: String(Number(l.qty || "0") + 1) }
            : l,
        );
      }
      return [...prev, { product: p, qty: "1" }];
    });
  }

  function setLineQty(variantId: string, qty: string) {
    setLines((prev) => prev.map((l) => (l.product.variant_id === variantId ? { ...l, qty } : l)));
  }

  function stepQty(variantId: string, delta: number) {
    setLines((prev) =>
      prev.map((l) => {
        if (l.product.variant_id !== variantId) return l;
        const next = Number(l.qty || "0") + delta;
        return { ...l, qty: next <= 0 ? "0" : String(next) };
      }).filter((l) => Number(l.qty) > 0),
    );
  }

  function removeLine(variantId: string) {
    setLines((prev) => prev.filter((l) => l.product.variant_id !== variantId));
  }

  const draftSubtotal = lines.reduce(
    (acc, l) => acc + previewLineTotal(l.qty, l.product.unit_price_paise ?? 0),
    0,
  );

  async function onCreateBill(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy || lines.length === 0) return;
    const valid = lines.filter((l) => Number(l.qty) > 0 && Number.isFinite(Number(l.qty)));
    if (valid.length === 0) {
      setError("प्रमाण > 0 हवे (Quantity must be > 0).");
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const created = await api.createPosBill(token, {
        items: valid.map((l) => ({ variant_id: l.product.variant_id, qty: l.qty.trim() })),
        ...(customerId.trim() ? { customer_id: customerId.trim() } : {}),
        ...(discountRs.trim() ? { discount_paise: rupeesToPaise(discountRs) } : {}),
        ...(chargesRs.trim() ? { other_charges_paise: rupeesToPaise(chargesRs) } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      });
      setBill(created);
      setLines([]);
      setNotice(`मसुदा बिल तयार Draft bill ${created.bill_number} — पेमेंट पूर्ण करा.`);
      setPayMode("cash");
      setReceivedRs(String(created.total_paise / 100));
      setReference("");
      setPartialRs("");
      setPayError(null);
      setPayOpen(true);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  /** Local change preview — informational; the server settles the payment. */
  function previewChangePaise(): number | null {
    if (!bill) return null;
    const dueBase = partialRs.trim() ? rupeesToPaise(partialRs) : bill.total_paise;
    if (payMode !== "cash" || !receivedRs.trim()) return null;
    return rupeesToPaise(receivedRs) - dueBase;
  }

  async function onComplete(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !bill || payBusy) return;
    if ((payMode === "credit" || partialRs.trim()) && !bill.customer_id) {
      setPayError("उधार/अर्धवट पेमेंटसाठी ग्राहक ID आवश्यक (Credit/partial needs a customer).");
      return;
    }
    setPayBusy(true);
    setPayError(null);
    try {
      const out = await api.completePosBill(token, bill.id, {
        payment_mode: payMode,
        ...(payMode === "cash" && receivedRs.trim()
          ? { amount_received_paise: rupeesToPaise(receivedRs) }
          : {}),
        ...(reference.trim() ? { payment_reference: reference.trim() } : {}),
        ...(partialRs.trim() ? { amount_paid_paise: rupeesToPaise(partialRs) } : {}),
      });
      const change =
        payMode === "cash" && receivedRs.trim()
          ? rupeesToPaise(receivedRs) - (partialRs.trim() ? rupeesToPaise(partialRs) : out.bill.total_paise)
          : null;
      setBill({ ...out.bill });
      setPayOpen(false);
      setNotice(
        out.duplicate
          ? `आधीच पूर्ण झाले होते (Already completed, duplicate=True) — ${out.bill.bill_number}.`
          : `बिल पूर्ण झाले Bill ${out.bill.bill_number} completed.` +
            (change !== null && change >= 0 ? ` सुटे परत Change: ₹${formatPaise(change)}.` : ""),
      );
      // Refresh today's summary after a completed sale.
      const sum = await api.posSummary(token);
      setSummary(sum);
    } catch (err) {
      setPayError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setPayBusy(false);
    }
  }

  const changePreview = previewChangePaise();

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>🧾 POS काउंटर Counter</h1>
        <p>
          <Link href="/store/pos/bills">बिले Bills →</Link>
          {" · "}
          <Link href="/store/inventory">साठा Inventory</Link>
          {" · "}
          <Link href="/store/staff">कर्मचारी Staff</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {notice ? <p className="muted">{notice}</p> : null}

        {forbidden ? (
          <p className="muted">प्रवेश नाही — हे पान फक्त स्टोअर स्टाफसाठी आहे (Staff only, 403).</p>
        ) : (
          <>
            {summary ? (
              <div className="grid">
                <article className="card">
                  <h2>आजची बिले Today: {summary.bills}</h2>
                  <p className="farm-area">₹{formatPaise(summary.total_paise)}</p>
                  <p className="muted">दिनांक Date: {String(summary.date).slice(0, 10)}</p>
                </article>
                {(["cash", "upi", "card", "credit"] as const).map((m) => (
                  <article className="card" key={m}>
                    <h2>{m}</h2>
                    <p>
                      बिले Bills: {summary.breakdown[m]?.bills ?? 0} · ₹
                      {formatPaise(summary.breakdown[m]?.total_paise ?? 0)}
                    </p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">{t.loading}</p>
            )}

            <div className="grid">
              <section className="card">
                <h2>शोधा Search Products</h2>
                <form onSubmit={onSearch}>
                  <input
                    type="search"
                    placeholder="उत्पादन / व्हेरिएंट नाव…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    aria-label="उत्पादन शोधा"
                  />{" "}
                  <button className="btn" type="submit" disabled={loading}>
                    {loading ? t.loading : "शोधा Search"}
                  </button>
                </form>
                {products === null ? (
                  <p className="muted">{t.loading}</p>
                ) : products.length === 0 ? (
                  <p className="muted">उत्पादने नाहीत No products found.</p>
                ) : (
                  products.map((p) => (
                    <p key={p.variant_id}>
                      {p.stock_status} {p.product_name ?? p.variant_id.slice(0, 8)}{" "}
                      <span className="muted">{p.variant_name ?? ""}</span>
                      <br />
                      {p.price_on_request || p.unit_price_paise === null ? (
                        <span className="muted">किंमत विचारा Price on request</span>
                      ) : (
                        <span>₹{formatPaise(p.unit_price_paise)}</span>
                      )}{" "}
                      <span className="muted">· उपलब्ध Available: {p.available}</span>{" "}
                      <button
                        type="button"
                        className="link-btn-plain"
                        disabled={p.price_on_request || p.unit_price_paise === null}
                        onClick={() => addLine(p)}
                      >
                        जोडा Add
                      </button>
                    </p>
                  ))
                )}
              </section>

              <section className="card">
                <h2>बिल मसुदा Bill Draft</h2>
                {lines.length === 0 ? (
                  <p className="muted">रिकामे Empty — डावीकडून उत्पादने जोडा.</p>
                ) : (
                  lines.map((l) => (
                    <p key={l.product.variant_id}>
                      {l.product.product_name ?? l.product.variant_id.slice(0, 8)}{" "}
                      <span className="muted">{l.product.variant_name ?? ""}</span>
                      <br />
                      <button type="button" className="link-btn-plain" onClick={() => stepQty(l.product.variant_id, -1)}>
                        −
                      </button>{" "}
                      <input
                        inputMode="decimal"
                        aria-label="प्रमाण Quantity"
                        value={l.qty}
                        onChange={(e) => setLineQty(l.product.variant_id, e.target.value)}
                        style={{ width: "4rem" }}
                      />{" "}
                      <button type="button" className="link-btn-plain" onClick={() => stepQty(l.product.variant_id, 1)}>
                        ＋
                      </button>{" "}
                      <span className="muted">
                        ≈ ₹{formatPaise(previewLineTotal(l.qty, l.product.unit_price_paise ?? 0))} (अंदाज estimate)
                      </span>{" "}
                      <button type="button" className="link-btn-plain" onClick={() => removeLine(l.product.variant_id)}>
                        काढा Remove
                      </button>
                    </p>
                  ))
                )}
                {lines.length > 0 ? (
                  <>
                    <p className="muted">अंदाज उप-एकूण Estimated subtotal: ₹{formatPaise(draftSubtotal)}</p>
                    <p>
                      <button type="button" className="btn-secondary" onClick={() => setLines([])}>
                        साफ करा Clear
                      </button>
                    </p>
                  </>
                ) : null}
                <form onSubmit={onCreateBill}>
                  <label>
                    ग्राहक ID Customer ID (ऐच्छिक optional — वॉक-इनसाठी रिकामे)
                    <br />
                    <input
                      placeholder="users.id UUID (उधारसाठी आवश्यक)"
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                    />
                  </label>
                  <br />
                  <span className="muted small">
                    ग्राहक-शोध endpoint नाही — customers/Khata पानावरून user UUID paste करा. तपशील docs/pos.md मध्ये.
                  </span>
                  <br />
                  <label>
                    सूट (₹) Discount — स्टाफ मर्यादा ₹200
                    <br />
                    <input inputMode="decimal" value={discountRs} onChange={(e) => setDiscountRs(e.target.value)} />
                  </label>
                  <br />
                  <label>
                    इतर शुल्क (₹) Other Charges
                    <br />
                    <input inputMode="decimal" value={chargesRs} onChange={(e) => setChargesRs(e.target.value)} />
                  </label>
                  <br />
                  <label>
                    नोंद Notes
                    <br />
                    <input value={notes} onChange={(e) => setNotes(e.target.value)} />
                  </label>
                  <br />
                  <button className="btn" type="submit" disabled={busy || lines.length === 0}>
                    {busy ? t.loading : "बिल तयार करा Create Bill"}
                  </button>
                </form>
              </section>
            </div>

            {bill ? (
              <section className="card">
                <h2>बिल {bill.bill_number}</h2>
                <p className="muted">
                  विक्री Sale: {saleStatusLabel(bill.sale_status)} · पेमेंट Payment: {paymentStatusLabelPos(bill.payment_status)}
                  {bill.payment_mode ? ` · ${bill.payment_mode}` : ""}
                </p>
                {bill.items.map((it) => (
                  <p key={it.id}>
                    {it.product_name_snapshot} · {it.variant_name_snapshot} · नग Qty: {String(it.qty)} · ₹
                    {formatPaise(it.line_total_paise)}
                  </p>
                ))}
                <p>उप-एकूण Subtotal: ₹{formatPaise(bill.subtotal_paise)}</p>
                <p>सूट Discount: ₹{formatPaise(bill.discount_paise)}</p>
                <p>इतर Other: ₹{formatPaise(bill.other_charges_paise)}</p>
                <p className="farm-area">एकूण Total: ₹{formatPaise(bill.total_paise)}</p>
                <p>
                  <Link href={`/store/pos/bills/${bill.id}`}>तपशील Details →</Link>
                  {" · "}
                  <Link href={`/store/pos/bills/${bill.id}/receipt`}>पावती Receipt →</Link>
                </p>
                {bill.sale_status === "draft" && !payOpen ? (
                  <p>
                    <button type="button" className="btn" onClick={() => setPayOpen(true)}>
                      पेमेंट करा Pay / Complete
                    </button>
                  </p>
                ) : null}
              </section>
            ) : null}

            {payOpen && bill ? (
              <section className="card">
                <h2>पेमेंट Payment — {bill.bill_number}</h2>
                <p className="farm-area">एकूण Total: ₹{formatPaise(bill.total_paise)}</p>
                {payError ? <p className="form-error">{payError}</p> : null}
                <form onSubmit={onComplete}>
                  <label>
                    पद्धत Mode
                    <br />
                    <select value={payMode} onChange={(e) => setPayMode(e.target.value)}>
                      {PAYMENT_MODES.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </label>
                  <br />
                  {payMode === "cash" ? (
                    <label>
                      मिळाले (₹) Amount Received — रोखीसाठी आवश्यक
                      <br />
                      <input inputMode="decimal" value={receivedRs} onChange={(e) => setReceivedRs(e.target.value)} required />
                    </label>
                  ) : null}
                  {payMode === "cash" ? <br /> : null}
                  {changePreview !== null ? (
                    <p className="muted">
                      सुटे परत Change (अंदाज preview): ₹{formatPaise(changePreview)}
                      {changePreview < 0 ? " — रक्कम कमी आहे (insufficient)" : ""}
                    </p>
                  ) : null}
                  {payMode === "upi" || payMode === "card" ? (
                    <label>
                      संदर्भ Reference (UPI txn / card slip)
                      <br />
                      <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="ऐच्छिक optional" />
                    </label>
                  ) : null}
                  {payMode === "upi" || payMode === "card" ? <br /> : null}
                  <label>
                    अर्धवट भरणा (₹) Partial Amount Paid (ऐच्छिक — ग्राहक ID आवश्यक)
                    <br />
                    <input
                      inputMode="decimal"
                      value={partialRs}
                      onChange={(e) => setPartialRs(e.target.value)}
                      placeholder="पूर्ण भरणा = रिकामे"
                    />
                  </label>
                  <br />
                  {payMode === "credit" ? (
                    <p className="form-error">उधारसाठी ग्राहक ID आवश्यक आहे (Credit requires a customer).</p>
                  ) : null}
                  <button className="btn" type="submit" disabled={payBusy}>
                    {payBusy ? t.loading : "पूर्ण करा Complete"}
                  </button>{" "}
                  <button type="button" className="btn-secondary" onClick={() => setPayOpen(false)}>
                    बंद करा Close
                  </button>
                </form>
              </section>
            ) : null}
          </>
        )}
      </main>
    </AuthGate>
  );
}
