/**
 * Shared Khata + payment display helpers (frontend only).
 *
 * Display only — the frontend NEVER computes or edits balances.
 * Outstanding/limit come from khataSummary; per-row snapshots come
 * from khataEntries. Signed deltas below are for read-only grouping.
 */

export function formatPaise(paise: number): string {
  const rupees = paise / 100;
  if (!Number.isFinite(rupees)) return String(paise);
  return rupees.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/** Backend Khata entry types: debit | credit | payment (Marathi-first). */
export function khataEntryTypeLabel(entryType: string): string {
  const map: Record<string, string> = {
    debit: "उधार (Debit)",
    credit: "जमा (Credit)",
    payment: "पेमेंट (Payment)",
  };
  return map[entryType] ?? entryType;
}

/** Order/payment status → Marathi-first label. */
export function paymentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "थकबाकी (Pending)",
    paid: "भरले (Paid)",
    failed: "अयशस्वी (Failed)",
    refunded: "परतावा (Refunded)",
  };
  return map[status] ?? status;
}

/**
 * Read-only signed delta, mirroring backend khata/service.py:
 * credits + payments reduce what the farmer owes, debits increase it.
 */
export function signedDelta(entryType: string, amountPaise: number): number {
  if (entryType === "credit" || entryType === "payment") return amountPaise;
  return -amountPaise;
}
