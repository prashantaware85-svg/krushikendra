/**
 * Step 16 shared helper: inventory stock-status → availability badge.
 * Display only (🟢 in stock / 🟠 low / 🔴 out).
 */

export function stockBadge(status: string): string {
  if (status === "in_stock") return "🟢";
  if (status === "low_stock") return "🟠";
  return "🔴";
}
