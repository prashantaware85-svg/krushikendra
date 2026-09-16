/**
 * Weather display helpers (Step 7): condition key → emoji + localized label.
 * Units are NOT converted here — the backend already normalizes to
 * °C / km/h / mm / % (see backend units.py). This file only formats.
 */

export function conditionEmoji(condition: string): string {
  const map: Record<string, string> = {
    clear: "☀️",
    partly_cloudy: "⛅",
    cloudy: "☁️",
    fog: "🌫️",
    drizzle: "🌦️",
    rain: "🌧️",
    freezing_rain: "🌨️",
    storm: "⛈️",
    snow: "❄️",
  };
  return map[condition] ?? "🌡️";
}

export function conditionLabel(t: Record<string, string>, condition: string): string {
  const map: Record<string, string> = {
    clear: t.condClear,
    partly_cloudy: t.condPartlyCloudy,
    cloudy: t.condCloudy,
    fog: t.condFog,
    drizzle: t.condDrizzle,
    rain: t.condRain,
    freezing_rain: t.condFreezingRain,
    storm: t.condStorm,
    snow: t.condSnow,
  };
  return map[condition] ?? condition;
}

export function stateBadge(t: Record<string, string>, state: string): string {
  if (state === "fresh") return t.weatherFresh;
  if (state === "cached") return t.weatherCached;
  return t.weatherStale;
}
