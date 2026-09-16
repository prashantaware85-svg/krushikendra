/**
 * Crop Calendar (auth-only): month grid + timeline list, status/type filters.
 * Tap a day → that day's records; tap a record → details. Manual records
 * only — nothing is generated or recommended here.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { activityStatusLabel, activityTypeLabel } from "../../../../../../components/activityLabels";
import { TimelineList } from "../../../../../../components/ActivityTimeline";
import { AuthGate } from "../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Activity } from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";
import type { Language } from "../../../../../../lib/i18n";

const ALL_TYPES = "";

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function monthCells(year: number, month: number): (Date | null)[] {
  // Sunday-start grid (matches printed Marathi calendars).
  const first = new Date(year, month, 1);
  const cells: (Date | null)[] = Array(first.getDay()).fill(null);
  const days = new Date(year, month + 1, 0).getDate();
  for (let d = 1; d <= days; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export default function CropCalendarPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t, language } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [view, setView] = useState<"calendar" | "list">("calendar");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState(ALL_TYPES);
  const [selectedDay, setSelectedDay] = useState<string | null>(dayKey(now));
  const [activities, setActivities] = useState<Activity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setActivities(await api.getTimeline(token, params.id, params.cropId).then((r) => r.activities));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () =>
      (activities ?? []).filter(
        (a) =>
          (statusFilter === "all" || a.status === statusFilter) &&
          (typeFilter === ALL_TYPES || a.activity_type === typeFilter),
      ),
    [activities, statusFilter, typeFilter],
  );

  const byDay = useMemo(() => {
    const m = new Map<string, Activity[]>();
    for (const a of filtered) {
      const list = m.get(a.activity_date) ?? [];
      list.push(a);
      m.set(a.activity_date, list);
    }
    return m;
  }, [filtered]);

  const typeOptions = useMemo(
    () => Array.from(new Set((activities ?? []).map((a) => a.activity_type))).sort(),
    [activities],
  );

  const locale = language === "mr" ? "mr-IN" : language === "hi" ? "hi-IN" : "en-IN";
  const monthTitle = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month, 1));
  const weekdayNames = useMemo(() => {
    const fmt = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
    return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2026, 5, 7 + i)));
  }, [locale]);

  function shift(delta: number) {
    const d = new Date(year, month + delta, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth());
  }

  const dayList = selectedDay ? (byDay.get(selectedDay) ?? []) : [];

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}/crops/${params.cropId}`}>← {t.backToCrop}</Link>
        </p>
        <div className="page-head">
          <h1>📅 {t.cropCalendar}</h1>
          <Link
            className="btn add-btn"
            href={`/farms/${params.id}/crops/${params.cropId}/activities/new`}
          >
            + {t.addActivity}
          </Link>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        <div className="chip-row">
          {(["all", "planned", "completed", "skipped", "cancelled"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={statusFilter === s ? "chip chip-on" : "chip"}
              onClick={() => setStatusFilter(s)}
            >
              {s === "all" ? t.filterAll : activityStatusLabel(t, s)}
            </button>
          ))}
        </div>

        <div className="chip-row">
          <button
            type="button"
            className={view === "calendar" ? "chip chip-on" : "chip"}
            onClick={() => setView("calendar")}
          >
            {t.calendarView}
          </button>
          <button
            type="button"
            className={view === "list" ? "chip chip-on" : "chip"}
            onClick={() => setView("list")}
          >
            {t.listView} / {t.timeline}
          </button>
          <select
            aria-label={t.activityType}
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="chip-select"
          >
            <option value={ALL_TYPES}>
              {t.activityType}: {t.filterAll}
            </option>
            {typeOptions.map((v) => (
              <option key={v} value={v}>
                {activityTypeLabel(t, v)}
              </option>
            ))}
          </select>
        </div>

        {activities === null ? (
          <p className="muted">{t.loading}</p>
        ) : view === "list" ? (
          <TimelineList
            items={filtered}
            t={t}
            base={`/farms/${params.id}/crops/${params.cropId}/activities`}
          />
        ) : (
          <>
            <div className="cal-nav">
              <button type="button" className="btn-secondary cal-btn" onClick={() => shift(-1)}>
                ‹
              </button>
              <strong>{monthTitle}</strong>
              <button type="button" className="btn-secondary cal-btn" onClick={() => shift(1)}>
                ›
              </button>
            </div>
            <div className="cal-grid">
              {weekdayNames.map((w, i) => (
                <span key={i} className="cal-dow">
                  {w}
                </span>
              ))}
              {monthCells(year, month).map((d, i) =>
                d === null ? (
                  <span key={i} className="cal-day cal-empty" />
                ) : (
                  <DayCell
                    key={i}
                    date={d}
                    items={byDay.get(dayKey(d)) ?? []}
                    selected={selectedDay === dayKey(d)}
                    onSelect={() => setSelectedDay(dayKey(d))}
                  />
                ),
              )}
            </div>
            {selectedDay ? (
              <section className="card">
                <h2>{selectedDay}</h2>
                {dayList.length === 0 ? (
                  <p className="muted">{t.noActivities}</p>
                ) : (
                  <TimelineList
                    items={dayList}
                    t={t}
                    base={`/farms/${params.id}/crops/${params.cropId}/activities`}
                  />
                )}
              </section>
            ) : null}
          </>
        )}
      </main>
    </AuthGate>
  );
}

function dotClass(status: string): string {
  if (status === "completed") return "dot dot-ok";
  if (status === "planned") return "dot dot-plan";
  return "dot";
}

function DayCell({
  date,
  items,
  selected,
  onSelect,
}: {
  date: Date;
  items: Activity[];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={selected ? "cal-day cal-sel" : "cal-day"}
      onClick={onSelect}
    >
      <span>{date.getDate()}</span>
      <span className="dots">
        {items.slice(0, 3).map((a) => (
          <span key={a.id} className={dotClass(a.status)} />
        ))}
      </span>
    </button>
  );
}
