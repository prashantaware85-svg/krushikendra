/**
 * Shared activity create/edit form (mobile-first, quantity/cost optional).
 * Recording only — no recommendations. Strings from `t`.
 */
"use client";

import type { FormEvent } from "react";
import type { ActivityWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export const ACTIVITY_TYPES = [
  "land_preparation",
  "sowing",
  "transplanting",
  "irrigation",
  "fertilizer_application",
  "pesticide_application",
  "fungicide_application",
  "herbicide_application",
  "weeding",
  "interculture",
  "pruning",
  "scouting",
  "harvesting",
  "other",
] as const;

export const ACTIVITY_STATUSES = ["planned", "completed", "skipped", "cancelled"] as const;

export type ActivityFormValues = {
  activity_type: string;
  title: string;
  description: string;
  activity_date: string;
  status: string;
  quantity: string;
  quantity_unit: string;
  cost: string;
  notes: string;
};

export const EMPTY_ACTIVITY: ActivityFormValues = {
  activity_type: "sowing",
  title: "",
  description: "",
  activity_date: "",
  status: "planned",
  quantity: "",
  quantity_unit: "",
  cost: "",
  notes: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

export function toActivityWrite(f: ActivityFormValues): ActivityWrite {
  return {
    activity_type: f.activity_type,
    title: f.title.trim(),
    description: opt(f.description),
    activity_date: f.activity_date,
    status: f.status,
    quantity: opt(f.quantity),
    quantity_unit: opt(f.quantity_unit),
    cost: opt(f.cost),
    notes: opt(f.notes),
  };
}

export function ActivityForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
  typeLabel,
  statusLabelFn,
}: {
  t: Record<StringKey, string>;
  values: ActivityFormValues;
  onChange: (v: ActivityFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  typeLabel: (v: string) => string;
  statusLabelFn: (v: string) => string;
}) {
  const set = (key: keyof ActivityFormValues, value: string) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.activityType}</span>
        <select value={values.activity_type} onChange={(e) => set("activity_type", e.target.value)}>
          {ACTIVITY_TYPES.map((v) => (
            <option key={v} value={v}>
              {typeLabel(v)}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>{t.activityTitle}</span>
        <input
          value={values.title}
          onChange={(e) => set("title", e.target.value)}
          placeholder={t.activityTitlePlaceholder}
          required
          maxLength={128}
        />
      </label>

      <div className="row2">
        <label className="field">
          <span>{t.activityDate}</span>
          <input
            type="date"
            value={values.activity_date}
            onChange={(e) => set("activity_date", e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>{t.statusLabel}</span>
          <select value={values.status} onChange={(e) => set("status", e.target.value)}>
            {ACTIVITY_STATUSES.map((v) => (
              <option key={v} value={v}>
                {statusLabelFn(v)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="row2">
        <label className="field">
          <span>
            {t.quantity} ({t.optional})
          </span>
          <input
            inputMode="decimal"
            value={values.quantity}
            onChange={(e) => set("quantity", e.target.value)}
          />
        </label>
        <label className="field">
          <span>
            {t.quantityUnit} ({t.optional})
          </span>
          <input
            value={values.quantity_unit}
            onChange={(e) => set("quantity_unit", e.target.value)}
            placeholder={t.quantityUnitPlaceholder}
            maxLength={32}
          />
        </label>
      </div>

      <label className="field">
        <span>
          {t.cost} ({t.optional})
        </span>
        <input
          inputMode="decimal"
          value={values.cost}
          onChange={(e) => set("cost", e.target.value)}
        />
      </label>

      <label className="field">
        <span>
          {t.description} ({t.optional})
        </span>
        <textarea
          value={values.description}
          onChange={(e) => set("description", e.target.value)}
          maxLength={2000}
          rows={2}
        />
      </label>

      <label className="field">
        <span>
          {t.notes} ({t.optional})
        </span>
        <textarea
          value={values.notes}
          onChange={(e) => set("notes", e.target.value)}
          placeholder={t.notesPlaceholder}
          maxLength={2000}
          rows={2}
        />
      </label>

      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
