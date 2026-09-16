/**
 * Shared activity timeline rows (used by calendar list view + crop details).
 * Kept outside page files — Next.js page entries may only export components.
 */
import Link from "next/link";
import { activityStatusLabel, activityTypeLabel } from "./activityLabels";

export type TimelineActivity = {
  id: string;
  title: string;
  activity_date: string;
  activity_type: string;
  status: string;
};

export function TimelineList({
  items,
  t,
  base,
}: {
  items: TimelineActivity[];
  t: Record<string, string>;
  base: string;
}) {
  if (items.length === 0) {
    return (
      <>
        <p className="muted">{t.noActivities}</p>
        <p className="muted">{t.noActivitiesHint}</p>
      </>
    );
  }
  return (
    <div className="timeline">
      {items.map((a) => (
        <ActivityRow key={a.id} a={a} t={t} href={`${base}/${a.id}`} />
      ))}
    </div>
  );
}

export function ActivityRow({
  a,
  t,
  href,
}: {
  a: TimelineActivity;
  t: Record<string, string>;
  href: string;
}) {
  const mark = a.status === "completed" ? "✓" : "○";
  return (
    <p className="tl-row">
      <span className={a.status === "completed" ? "tl-done" : "tl-todo"}>{mark}</span>{" "}
      <strong>{a.title}</strong>
      <br />
      <span className="muted">
        {a.activity_date} · {activityTypeLabel(t, a.activity_type)} ·{" "}
        {activityStatusLabel(t, a.status)}{" "}
      </span>
      <Link href={href}>[{t.viewDetails}]</Link>
    </p>
  );
}
