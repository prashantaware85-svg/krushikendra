/**
 * Shared fertilizer create/edit form (mobile-first).
 * Records usage only ("farmer used X") — never advice. Units stored
 * verbatim, never converted. Strings come from `t`.
 */
"use client";

import type { FormEvent } from "react";
import type { FertilizerWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type FertilizerFormValues = {
  fertilizer_name: string;
  fertilizer_type: string;
  quantity: string;
  quantity_unit: string;
  application_date: string;
  application_method: string;
  purpose: string;
  notes: string;
};

export const EMPTY_FERTILIZER: FertilizerFormValues = {
  fertilizer_name: "",
  fertilizer_type: "",
  quantity: "",
  quantity_unit: "kg",
  application_date: "",
  application_method: "",
  purpose: "",
  notes: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

/** Convert form values to the API payload (empty optionals omitted). */
export function toFertilizerWrite(f: FertilizerFormValues): FertilizerWrite {
  return {
    fertilizer_name: f.fertilizer_name.trim(),
    fertilizer_type: (opt(f.fertilizer_type) ?? undefined) as FertilizerWrite["fertilizer_type"],
    quantity: f.quantity.trim(),
    quantity_unit: f.quantity_unit as FertilizerWrite["quantity_unit"],
    application_date: f.application_date,
    application_method: opt(f.application_method),
    purpose: opt(f.purpose),
    notes: opt(f.notes),
  };
}

export function FertilizerForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
}: {
  t: Record<StringKey, string>;
  values: FertilizerFormValues;
  onChange: (v: FertilizerFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
}) {
  const set = (key: keyof FertilizerFormValues, value: string) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.fertilizerName}</span>
        <input
          value={values.fertilizer_name}
          onChange={(e) => set("fertilizer_name", e.target.value)}
          placeholder={t.fertilizerNamePlaceholder}
          required
          maxLength={128}
        />
      </label>
      <div className="row2">
        <label className="field">
          <span>{t.fertilizerType}</span>
          <select value={values.fertilizer_type} onChange={(e) => set("fertilizer_type", e.target.value)}>
            <option value="">—</option>
            <option value="organic">{t.typeOrganic}</option>
            <option value="nitrogen">{t.typeNitrogen}</option>
            <option value="phosphorus">{t.typePhosphorus}</option>
            <option value="potassium">{t.typePotassium}</option>
            <option value="micronutrient">{t.typeMicronutrient}</option>
            <option value="npk">{t.typeNpk}</option>
            <option value="other">{t.typeOther}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.fertUnit}</span>
          <select value={values.quantity_unit} onChange={(e) => set("quantity_unit", e.target.value)}>
            <option value="kg">{t.kg}</option>
            <option value="quintal">{t.quintal}</option>
            <option value="litre">Litre</option>
            <option value="gram">Gram</option>
            <option value="other">{t.typeOther}</option>
          </select>
        </label>
      </div>
      <div className="row2">
        <label className="field">
          <span>{t.fertQuantity}</span>
          <input
            inputMode="decimal"
            value={values.quantity}
            onChange={(e) => set("quantity", e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>{t.applicationDate}</span>
          <input
            type="date"
            value={values.application_date}
            onChange={(e) => set("application_date", e.target.value)}
            required
          />
        </label>
      </div>
      <label className="field">
        <span>{t.applicationMethod}</span>
        <input
          value={values.application_method}
          onChange={(e) => set("application_method", e.target.value)}
          placeholder={t.applicationMethodPlaceholder}
          maxLength={64}
        />
      </label>
      <label className="field">
        <span>{t.purposeLabel}</span>
        <input
          value={values.purpose}
          onChange={(e) => set("purpose", e.target.value)}
          placeholder={t.purposePlaceholder}
          maxLength={256}
        />
      </label>
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
      <p className="muted small">{t.recordActivityNote}</p>
      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
