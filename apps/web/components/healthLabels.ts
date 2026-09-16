/**
 * Shared health label helpers (type/severity/status/source → localized).
 * Lives outside page files — Next.js page entries may only export components.
 * Labels describe RECORDS, never diagnoses.
 */

export function observationTypeLabel(t: Record<string, string>, v: string | null): string {
  const map: Record<string, string> = {
    pest: t.typePest,
    disease: t.typeDisease,
    unknown: t.typeUnknown,
    other: t.typeOther,
  };
  return (v && map[v]) || t.notSet;
}

export function severityLabel(t: Record<string, string>, v: string | null): string {
  const map: Record<string, string> = {
    low: t.severityLow,
    medium: t.severityMedium,
    high: t.severityHigh,
    unknown: t.severityUnknown,
  };
  return (v && map[v]) || t.notSet;
}

export function observationStatusLabel(t: Record<string, string>, v: string | null): string {
  const map: Record<string, string> = {
    observed: t.statusObserved,
    monitoring: t.statusMonitoring,
    resolved: t.statusResolved,
    recurring: t.statusRecurring,
  };
  return (v && map[v]) || t.notSet;
}

export function observationSourceLabel(t: Record<string, string>, v: string | null): string {
  const map: Record<string, string> = {
    farmer: t.sourceFarmer,
    image_analysis: t.sourceImageAnalysis,
    expert: t.sourceExpert,
    other: t.sourceOther,
  };
  return (v && map[v]) || t.notSet;
}

export function severityDot(severity: string | null): string {
  if (severity === "high") return "🔴";
  if (severity === "medium") return "🟡";
  if (severity === "low") return "🟢";
  return "⚪";
}
