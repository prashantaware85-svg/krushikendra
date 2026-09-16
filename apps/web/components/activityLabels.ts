/**
 * Shared activity label helpers (type/status → localized string).
 * Lives outside page files — Next.js page entries may only export components.
 */

export function activityTypeLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    land_preparation: t.typeLandPreparation,
    sowing: t.typeSowing,
    transplanting: t.typeTransplanting,
    irrigation: t.typeIrrigation,
    fertilizer_application: t.typeFertilizer,
    pesticide_application: t.typePesticide,
    fungicide_application: t.typeFungicide,
    herbicide_application: t.typeHerbicide,
    weeding: t.typeWeeding,
    interculture: t.typeInterculture,
    pruning: t.typePruning,
    scouting: t.typeScouting,
    harvesting: t.typeHarvesting,
    other: t.typeOther,
  };
  return map[v] ?? v;
}

export function activityStatusLabel(t: Record<string, string>, v: string): string {
  const map: Record<string, string> = {
    planned: t.statusPlanned,
    completed: t.statusCompleted,
    skipped: t.statusSkipped,
    cancelled: t.statusCancelled,
  };
  return map[v] ?? v;
}
