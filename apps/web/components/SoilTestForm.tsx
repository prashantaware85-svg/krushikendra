/**
 * Shared soil-test create/edit form (mobile-first).
 * Units shown next to every nutrient (pH unitless, EC dS/m, OC %,
 * N/P/K kg/ha, S kg/ha, micros mg/kg) — values stored exactly as entered.
 * Strings come from `t` — no hardcoded UI text here.
 */
"use client";

import type { FormEvent } from "react";
import type { SoilTestWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type SoilFormValues = {
  test_date: string;
  laboratory_name: string;
  report_number: string;
  soil_type: string;
  ph: string;
  electrical_conductivity: string;
  organic_carbon: string;
  nitrogen: string;
  phosphorus: string;
  potassium: string;
  sulphur: string;
  zinc: string;
  iron: string;
  manganese: string;
  copper: string;
  boron: string;
  notes: string;
};

export const EMPTY_SOIL_TEST: SoilFormValues = {
  test_date: "",
  laboratory_name: "",
  report_number: "",
  soil_type: "",
  ph: "",
  electrical_conductivity: "",
  organic_carbon: "",
  nitrogen: "",
  phosphorus: "",
  potassium: "",
  sulphur: "",
  zinc: "",
  iron: "",
  manganese: "",
  copper: "",
  boron: "",
  notes: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

/** Convert form values to the API payload (empty optionals omitted). */
export function toSoilTestWrite(f: SoilFormValues): SoilTestWrite {
  return {
    test_date: f.test_date,
    laboratory_name: opt(f.laboratory_name),
    report_number: opt(f.report_number),
    soil_type: opt(f.soil_type),
    ph: opt(f.ph),
    electrical_conductivity: opt(f.electrical_conductivity),
    organic_carbon: opt(f.organic_carbon),
    nitrogen: opt(f.nitrogen),
    phosphorus: opt(f.phosphorus),
    potassium: opt(f.potassium),
    sulphur: opt(f.sulphur),
    zinc: opt(f.zinc),
    iron: opt(f.iron),
    manganese: opt(f.manganese),
    copper: opt(f.copper),
    boron: opt(f.boron),
    notes: opt(f.notes),
  };
}

const NUTRIENTS: [keyof SoilFormValues, StringKey][] = [
  ["ph", "phLabel"],
  ["electrical_conductivity", "ecLabel"],
  ["organic_carbon", "organicCarbonLabel"],
  ["nitrogen", "nitrogenLabel"],
  ["phosphorus", "phosphorusLabel"],
  ["potassium", "potassiumLabel"],
  ["sulphur", "sulphurLabel"],
  ["zinc", "zincLabel"],
  ["iron", "ironLabel"],
  ["manganese", "manganeseLabel"],
  ["copper", "copperLabel"],
  ["boron", "boronLabel"],
];

export function SoilTestForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
}: {
  t: Record<StringKey, string>;
  values: SoilFormValues;
  onChange: (v: SoilFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
}) {
  const set = (key: keyof SoilFormValues, value: string) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.soilTestDate}</span>
        <input
          type="date"
          value={values.test_date}
          onChange={(e) => set("test_date", e.target.value)}
          required
        />
      </label>
      <div className="row2">
        <label className="field">
          <span>{t.labName}</span>
          <input
            value={values.laboratory_name}
            onChange={(e) => set("laboratory_name", e.target.value)}
            maxLength={128}
          />
        </label>
        <label className="field">
          <span>{t.reportNumber}</span>
          <input
            value={values.report_number}
            onChange={(e) => set("report_number", e.target.value)}
            maxLength={64}
          />
        </label>
      </div>
      <label className="field">
        <span>{t.soilType}</span>
        <input
          value={values.soil_type}
          onChange={(e) => set("soil_type", e.target.value)}
          placeholder={t.soilTypePlaceholder}
          maxLength={32}
        />
      </label>
      {NUTRIENTS.map(([key, label]) => (
        <label className="field" key={key}>
          <span>{t[label]}</span>
          <input
            inputMode="decimal"
            value={values[key]}
            onChange={(e) => set(key, e.target.value)}
          />
        </label>
      ))}
      <label className="field">
        <span>
          {t.soilNotes} ({t.optional})
        </span>
        <textarea
          value={values.notes}
          onChange={(e) => set("notes", e.target.value)}
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
