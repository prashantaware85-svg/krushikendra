/**
 * Shared crop label helpers (season/status → localized string).
 * Lives outside page files — Next.js page entries may only export components.
 */

export function seasonLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    kharif: t.seasonKharif,
    rabi: t.seasonRabi,
    zaid: t.seasonZaid,
    perennial: t.seasonPerennial,
    other: t.seasonOther,
  };
  return map[v] ?? v;
}

export function statusLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    planned: t.statusPlanned,
    sown: t.statusSown,
    growing: t.statusGrowing,
    harvested: t.statusHarvested,
    failed: t.statusFailed,
    cancelled: t.statusCancelled,
  };
  return map[v] ?? v;
}
