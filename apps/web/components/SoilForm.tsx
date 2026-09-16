/**
 * Shared soil create/edit form. Storage only — no advice or recommendations.
 */
"use client";

import type { FormEvent } from "react";
import type { SoilWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type SoilFormValues = {
  soil_type: string;
  soil_test_available: boolean;
  soil_test_date: string;
  ph: string;
  organic_carbon: string;
  nitrogen: string;
  phosphorus: string;
  potassium: string;
  soil_test_document_reference: string;
};

export const EMPTY_SOIL: SoilFormValues = {
  soil_type: "",
  soil_test_available: false,
  soil_test_date: "",
  ph: "",
  organic_carbon: "",
  nitrogen: "",
  phosphorus: "",
  potassium: "",
  soil_test_document_reference: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

export function toSoilWrite(f: SoilFormValues): SoilWrite {
  return {
    soil_type: opt(f.soil_type),
    soil_test_available: f.soil_test_available,
    soil_test_date: opt(f.soil_test_date),
    ph: opt(f.ph),
    organic_carbon: opt(f.organic_carbon),
    nitrogen: opt(f.nitrogen),
    phosphorus: opt(f.phosphorus),
    potassium: opt(f.potassium),
    soil_test_document_reference: opt(f.soil_test_document_reference),
  };
}

export function SoilForm({
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
  const set = (key: keyof SoilFormValues, value: string | boolean) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.soilType}</span>
        <input
          value={values.soil_type}
          onChange={(e) => set("soil_type", e.target.value)}
          placeholder={t.soilTypePlaceholder}
          maxLength={32}
        />
      </label>

      <label className="check">
        <input
          type="checkbox"
          checked={values.soil_test_available}
          onChange={(e) => set("soil_test_available", e.target.checked)}
        />
        <span>{t.soilTestAvailable}</span>
      </label>

      <label className="field">
        <span>{t.soilTestDate}</span>
        <input
          type="date"
          value={values.soil_test_date}
          onChange={(e) => set("soil_test_date", e.target.value)}
        />
      </label>

      <div className="row2">
        <label className="field">
          <span>{t.phLabel}</span>
          <input
            inputMode="decimal"
            value={values.ph}
            onChange={(e) => set("ph", e.target.value)}
            placeholder="6.5"
          />
        </label>
        <label className="field">
          <span>{t.organicCarbon}</span>
          <input
            inputMode="decimal"
            value={values.organic_carbon}
            onChange={(e) => set("organic_carbon", e.target.value)}
            placeholder="0.75"
          />
        </label>
      </div>

      <div className="row2">
        <label className="field">
          <span>{t.nitrogen}</span>
          <input
            inputMode="decimal"
            value={values.nitrogen}
            onChange={(e) => set("nitrogen", e.target.value)}
          />
        </label>
        <label className="field">
          <span>{t.phosphorus}</span>
          <input
            inputMode="decimal"
            value={values.phosphorus}
            onChange={(e) => set("phosphorus", e.target.value)}
          />
        </label>
      </div>

      <label className="field">
        <span>{t.potassium}</span>
        <input
          inputMode="decimal"
          value={values.potassium}
          onChange={(e) => set("potassium", e.target.value)}
        />
      </label>

      <label className="field">
        <span>{t.docRef}</span>
        <input
          value={values.soil_test_document_reference}
          onChange={(e) => set("soil_test_document_reference", e.target.value)}
          placeholder={t.docRefPlaceholder}
          maxLength={256}
        />
      </label>

      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
