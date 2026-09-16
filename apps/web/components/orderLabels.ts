/**
 * Shared order status labels (status → localized string).
 * Lives outside page files — Next.js page entries may only export components.
 */

export function orderStatusLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    pending: t.statusPending,
    confirmed: t.statusConfirmed,
    processing: t.statusProcessing,
    packed: t.statusPacked,
    shipped: t.statusShipped,
    out_for_delivery: t.statusOutForDelivery,
    delivered: t.statusDelivered,
    cancelled: t.statusCancelled,
  };
  return map[v] ?? v;
}

export function formatINR(value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
