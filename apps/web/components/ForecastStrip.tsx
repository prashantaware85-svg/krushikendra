/**
 * 7-day forecast strip (Step 7): one row per day, localized day names.
 */
import { conditionEmoji, conditionLabel, stateBadge } from "./weatherLabels";
import type { WeatherForecast } from "../lib/api";
import type { Language, StringKey } from "../lib/i18n";

export function ForecastStrip({
  t,
  language,
  forecast,
}: {
  t: Record<StringKey, string>;
  language: Language;
  forecast: WeatherForecast | null | undefined;
}) {
  if (!forecast) return null;
  const locale = language === "mr" ? "mr-IN" : language === "hi" ? "hi-IN" : "en-IN";
  const todayStr = toISODate(new Date());
  const tomorrowStr = toISODate(new Date(Date.now() + 86400000));

  return (
    <div className="card">
      <h2>
        📅 {t.forecastTitle}{" "}
        <span className={forecast.data_state === "stale" ? "badge-stale" : "badge-fresh"}>
          {stateBadge(t, forecast.data_state)}
        </span>
      </h2>
      {forecast.days.map((d, i) => (
        <p key={d.date} className="fc-row">
          <strong>{dayName(t, locale, d.date, todayStr, tomorrowStr, i)}</strong>{" "}
          {conditionEmoji(d.condition)} {d.temp_max ?? "—"}°C{" "}
          <span className="muted">
            {conditionLabel(t, d.condition)} · 🌧️ {d.precipitation_probability ?? "—"}%
          </span>
        </p>
      ))}
    </div>
  );
}

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function dayName(
  t: Record<StringKey, string>,
  locale: string,
  iso: string,
  today: string,
  tomorrow: string,
  index: number,
): string {
  if (iso === today || index === 0) return t.today;
  if (iso === tomorrow) return t.tomorrow;
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { weekday: "long" }).format(new Date(y, m - 1, d));
}
