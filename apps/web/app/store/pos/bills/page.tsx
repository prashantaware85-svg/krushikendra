/**
 * POS Bills history (Step 18, staff-only): filters + limit/offset pagination.
 * Server-computed paise totals only; 401/403 shows प्रवेश नाही.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type PosBillPage } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { formatPaise } from "../../../../lib/khata";

const PAGE_SIZE = 20;

export default function PosBillsPage() {
  const { t } = useAuth();
  const [page, setPage] = useState<PosBillPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [offset, setOffset] = useState(0);
  const [billNumber, setBillNumber] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [paymentMode, setPaymentMode] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [saleStatus, setSaleStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const load = useCallback(
    async (nextOffset: number) => {
      const token = getStoredToken();
      if (!token) return;
      try {
        setPage(
          await api.listPosBills(token, {
            ...(billNumber.trim() ? { bill_number: billNumber.trim() } : {}),
            ...(customerId.trim() ? { customer_id: customerId.trim() } : {}),
            ...(paymentMode ? { payment_mode: paymentMode } : {}),
            ...(paymentStatus ? { payment_status: paymentStatus } : {}),
            ...(saleStatus ? { sale_status: saleStatus } : {}),
            ...(dateFrom ? { date_from: dateFrom } : {}),
            ...(dateTo ? { date_to: dateTo } : {}),
            limit: PAGE_SIZE,
            offset: nextOffset,
          }),
        );
        setOffset(nextOffset);
        setError(null);
        setForbidden(false);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setForbidden(true);
          setPage({ bills: [], total: 0, limit: PAGE_SIZE, offset: nextOffset });
          setError("प्रवेश नाही — फक्त स्टाफ (Staff only).");
        } else {
          setError(err instanceof ApiError ? err.message : "Error");
        }
      }
    },
    [billNumber, customerId, paymentMode, paymentStatus, saleStatus, dateFrom, dateTo],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  function onFilter(e: React.FormEvent) {
    e.preventDefault();
    load(0);
  }

  const total = page?.total ?? 0;

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>🧾 बिले Bills</h1>
        <p>
          <Link href="/store/pos">← POS काउंटर Counter</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {forbidden ? (
          <p className="muted">प्रवेश नाही — हे पान फक्त स्टोअर स्टाफसाठी आहे (Staff only, 403).</p>
        ) : (
          <>
            <form onSubmit={onFilter}>
              <input
                placeholder="बिल क्रमांक Bill number"
                value={billNumber}
                onChange={(e) => setBillNumber(e.target.value)}
              />{" "}
              <input
                placeholder="ग्राहक ID Customer ID"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
              />{" "}
              <select value={paymentMode} onChange={(e) => setPaymentMode(e.target.value)}>
                <option value="">सर्व पद्धती All modes</option>
                <option value="cash">cash</option>
                <option value="upi">upi</option>
                <option value="card">card</option>
                <option value="credit">credit</option>
              </select>{" "}
              <select value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value)}>
                <option value="">सर्व पेमेंट All payments</option>
                <option value="pending">pending</option>
                <option value="paid">paid</option>
                <option value="partial">partial</option>
                <option value="credit">credit</option>
              </select>{" "}
              <select value={saleStatus} onChange={(e) => setSaleStatus(e.target.value)}>
                <option value="">सर्व विक्री All sales</option>
                <option value="draft">draft</option>
                <option value="completed">completed</option>
                <option value="cancelled">cancelled</option>
              </select>{" "}
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />{" "}
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />{" "}
              <button className="btn" type="submit">
                लागू करा Apply
              </button>
            </form>
            {page === null ? (
              <p className="muted">{t.loading}</p>
            ) : page.bills.length === 0 ? (
              <p className="muted">बिले नाहीत No bills found.</p>
            ) : (
              <>
                <p className="muted">एकूण Total: {total}</p>
                <div className="grid">
                  {page.bills.map((b) => (
                    <article className="card" key={b.id}>
                      <h2>{b.bill_number}</h2>
                      <p className="muted">{b.created_at.slice(0, 10)}</p>
                      <p>
                        विक्री Sale: {b.sale_status} · पेमेंट Payment: {b.payment_status}
                        {b.payment_mode ? ` · ${b.payment_mode}` : ""}
                      </p>
                      <p className="farm-area">₹{formatPaise(b.total_paise)}</p>
                      <p>
                        <Link href={`/store/pos/bills/${b.id}`}>{t.viewDetails} →</Link>
                      </p>
                    </article>
                  ))}
                </div>
                <p>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={offset === 0}
                    onClick={() => load(Math.max(0, offset - PAGE_SIZE))}
                  >
                    ← मागील Prev
                  </button>{" "}
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={offset + PAGE_SIZE >= total}
                    onClick={() => load(offset + PAGE_SIZE)}
                  >
                    पुढील Next →
                  </button>
                </p>
                <p className="muted">
                  दाखवत आहे Showing {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
                </p>
              </>
            )}
          </>
        )}
      </main>
    </AuthGate>
  );
}
