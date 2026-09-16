/**
 * Shared health observation create/edit form (mobile-first).
 * Catalogue pickers optional — free-text observed_name always allowed.
 * Strings come from `t` — no hardcoded UI text here.
 */
"use client";

import type { FormEvent } from "react";
import type { HealthObservationWrite, PestDisease } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type HealthFormValues = {
  observation_type: string;
  pest_id: string;
  disease_id: string;
  observed_name: string;
  observation_date: string;
  severity: string;
  affected_area: string;
  affected_area_unit: string;
  symptoms: string;
  notes: string;
  status: string;
  source: string;
  linked_image_analysis_id: string;
};

export const EMPTY_OBSERVATION: HealthFormValues = {
  observation_type: "unknown",
  pest_id: "",
  disease_id: "",
  observed_name: "",
  observation_date: "",
  severity: "unknown",
  affected_area: "",
  affected_area_unit: "",
  symptoms: "",
  notes: "",
  status: "observed",
  source: "farmer",
  linked_image_analysis_id: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

/** Convert form values to the API payload (empty optionals omitted). */
export function toObservationWrite(f: HealthFormValues): HealthObservationWrite {
  return {
    observation_type: f.observation_type,
    pest_id: opt(f.pest_id) ?? undefined,
    disease_id: opt(f.disease_id) ?? undefined,
    observed_name: opt(f.observed_name),
    observation_date: f.observation_date,
    severity: f.severity,
    affected_area: opt(f.affected_area),
    affected_area_unit: (opt(f.affected_area_unit) ?? undefined) as HealthObservationWrite["affected_area_unit"],
    symptoms: opt(f.symptoms),
    notes: opt(f.notes),
    status: f.status as HealthObservationWrite["status"],
    source: f.source as HealthObservationWrite["source"],
    linked_image_analysis_id: opt(f.linked_image_analysis_id) ?? undefined,
  };
}

export function HealthForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
  pests,
  diseases,
}: {
  t: Record<StringKey, string>;
  values: HealthFormValues;
  onChange: (v: HealthFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  pests: PestDisease[];
  diseases: PestDisease[];
}) {
  const set = (key: keyof HealthFormValues, value: string) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.observationType}</span>
        <select value={values.observation_type} onChange={(e) => set("observation_type", e.target.value)}>
          <option value="pest">{t.typePest}</option>
          <option value="disease">{t.typeDisease}</option>
          <option value="unknown">{t.typeUnknown}</option>
          <option value="other">{t.typeOther}</option>
        </select>
      </label>

      {values.observation_type === "pest" ? (
        <label className="field">
          <span>
            {t.typePest} ({t.optional})
          </span>
          <select value={values.pest_id} onChange={(e) => set("pest_id", e.target.value)}>
            <option value="">—</option>
            {pests.map((p) => (
              <option key={p.id} value={p.id}>
                {p.local_name ?? p.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {values.observation_type === "disease" ? (
        <label className="field">
          <span>
            {t.typeDisease} ({t.optional})
          </span>
          <select value={values.disease_id} onChange={(e) => set("disease_id", e.target.value)}>
            <option value="">—</option>
            {diseases.map((d) => (
              <option key={d.id} value={d.id}>
                {d.local_name ?? d.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="field">
        <span>{t.obsName}</span>
        <input
          value={values.observed_name}
          onChange={(e) => set("observed_name", e.target.value)}
          placeholder={t.obsNamePlaceholder}
          maxLength={128}
        />
      </label>

      <div className="row2">
        <label className="field">
          <span>{t.severityLabel}</span>
          <select value={values.severity} onChange={(e) => set("severity", e.target.value)}>
            <option value="low">{t.severityLow}</option>
            <option value="medium">{t.severityMedium}</option>
            <option value="high">{t.severityHigh}</option>
            <option value="unknown">{t.severityUnknown}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.observationDate}</span>
          <input
            type="date"
            value={values.observation_date}
            onChange={(e) => set("observation_date", e.target.value)}
            required
          />
        </label>
      </div>

      <div className="row2">
        <label className="field">
          <span>
            {t.affectedArea} ({t.optional})
          </span>
          <input
            inputMode="decimal"
            value={values.affected_area}
            onChange={(e) => set("affected_area", e.target.value)}
          />
        </label>
        <label className="field">
          <span>{t.fertUnit}</span>
          <select
            value={values.affected_area_unit}
            onChange={(e) => set("affected_area_unit", e.target.value)}
          >
            <option value="">—</option>
            <option value="acre">{t.acre}</option>
            <option value="hectare">{t.hectare}</option>
            <option value="guntha">{t.guntha}</option>
            <option value="percentage">%</option>
          </select>
        </label>
      </div>

      <label className="field">
        <span>{t.symptomsLabel}</span>
        <textarea
          value={values.symptoms}
          onChange={(e) => set("symptoms", e.target.value)}
          placeholder={t.symptomsPlaceholder}
          maxLength={2000}
          rows={3}
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

      <div className="row2">
        <label className="field">
          <span>{t.obsStatus}</span>
          <select value={values.status} onChange={(e) => set("status", e.target.value)}>
            <option value="observed">{t.statusObserved}</option>
            <option value="monitoring">{t.statusMonitoring}</option>
            <option value="resolved">{t.statusResolved}</option>
            <option value="recurring">{t.statusRecurring}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.obsSource}</span>
          <select value={values.source} onChange={(e) => set("source", e.target.value)}>
            <option value="farmer">{t.sourceFarmer}</option>
            <option value="image_analysis">{t.sourceImageAnalysis}</option>
            <option value="expert">{t.sourceExpert}</option>
            <option value="other">{t.sourceOther}</option>
          </select>
        </label>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
