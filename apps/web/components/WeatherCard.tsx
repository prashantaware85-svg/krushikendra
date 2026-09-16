/**
 * Current-weather card (Step 7): farmer-friendly units, honest status badge.
 * Shows nothing silently stale — the badge always says what the data is.
 */
import { conditionEmoji, conditionLabel, stateBadge } from "./weatherLabels";
import type { WeatherCurrent } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export function WeatherCard({
  t,
  weather,
  onRetry,
}: {
  t: Record<StringKey, string>;
  weather: WeatherCurrent | null | undefined;
  onRetry?: () => void;
}) {
  if (weather === undefined) {
    return (
      <div className="card">
        <h2>🌦️ {t.todayWeather}</h2>
        <p className="muted">{t.loading}</p>
      </div>
    );
  }
  if (weather === null) {
    return (
      <div className="card">
        <h2>🌦️ {t.todayWeather}</h2>
        <p className="muted">{t.weatherUnavailable}</p>
        {onRetry ? (
          <button className="btn-secondary" type="button" onClick={onRetry}>
            {t.weatherRetry}
          </button>
        ) : null}
      </div>
    );
  }
  return (
    <div className="card">
      <h2>
        🌦️ {t.todayWeather}{" "}
        <span className={weather.data_state === "stale" ? "badge-stale" : "badge-fresh"}>
          {stateBadge(t, weather.data_state)}
        </span>
      </h2>
      <p className="wx-temp">
        {conditionEmoji(weather.condition)}{" "}
        {weather.temperature ?? "—"}°C
      </p>
      <p className="muted">
        {conditionLabel(t, weather.condition)}
        {weather.feels_like !== null ? ` · ${t.feelsLike} ${weather.feels_like}°C` : ""}
      </p>
      <p>
        💧 {t.humidity} {weather.humidity ?? "—"}% · 🌧️ {t.rainChance}{" "}
        {weather.precipitation_probability ?? "—"}%
      </p>
      <p>
        💨 {t.wind} {weather.wind_speed ?? "—"} km/h
      </p>
    </div>
  );
}
