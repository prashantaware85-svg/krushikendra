/**
 * Shared crop create/edit form (mobile-first).
 *
 * Crop → Variety browsing: the crop input offers catalogue crops via a
 * native datalist; the variety dropdown filters to that crop's varieties.
 * Free text always works and variety stays optional — picking "not
 * selected" (or typing a custom variety) sends no crop_variety_id.
 * Strings come from `t` — no hardcoded UI text here.
 */
"use client";

import { useMemo, type FormEvent } from "react";
import type { CropVariety, CropWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type CropFormValues = {
  crop_name: string;
  variety_name: string;
  crop_variety_id: string | null;
  area: string;
  area_unit: CropWrite["area_unit"];
  season: string;
  sowing_date: string;
  expected_harvest_date: string;
  status: string;
  notes: string;
};

export const EMPTY_CROP: CropFormValues = {
  crop_name: "",
  variety_name: "",
  crop_variety_id: null,
  area: "",
  area_unit: "acre",
  season: "kharif",
  sowing_date: "",
  expected_harvest_date: "",
  status: "sown",
  notes: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

/** Convert form values to the API payload (empty optionals omitted). */
export function toCropWrite(f: CropFormValues): CropWrite {
  return {
    crop_name: f.crop_name.trim(),
    variety_name: opt(f.variety_name),
    crop_variety_id: f.crop_variety_id,
    area: f.area.trim(),
    area_unit: f.area_unit,
    season: f.season,
    sowing_date: f.sowing_date,
    expected_harvest_date: opt(f.expected_harvest_date),
    status: f.status,
    notes: opt(f.notes),
  };
}

export function CropForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
  varieties,
}: {
  t: Record<StringKey, string>;
  values: CropFormValues;
  onChange: (v: CropFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  varieties: CropVariety[];
}) {
  const cropNames = useMemo(
    () => Array.from(new Set(varieties.map((v) => v.crop_name))).sort(),
    [varieties],
  );

  const matchingVarieties = useMemo(() => {
    const typed = values.crop_name.trim().toLowerCase();
    if (!typed) return [];
    return varieties.filter((v) => v.crop_name.toLowerCase() === typed);
  }, [varieties, values.crop_name]);

  const set = (key: keyof CropFormValues, value: string | null) =>
    onChange({ ...values, [key]: value } as CropFormValues);

  function onCropName(name: string) {
    // Keep the linked variety only if it belongs to the typed crop.
    const stillValid = varieties.some(
      (v) => v.id === values.crop_variety_id && v.crop_name.toLowerCase() === name.trim().toLowerCase(),
    );
    onChange({
      ...values,
      crop_name: name,
      crop_variety_id: stillValid ? values.crop_variety_id : null,
    });
  }

  function onVarietySelect(id: string) {
    if (!id) {
      set("crop_variety_id", null);
      return;
    }
    const row = varieties.find((v) => v.id === id);
    if (!row) return;
    onChange({
      ...values,
      crop_variety_id: row.id,
      variety_name: row.variety_name ?? "",
      crop_name: row.crop_name,
    });
  }

  function onVarietyText(name: string) {
    // Custom text diverges from the catalogue row — unlink the id.
    onChange({ ...values, variety_name: name, crop_variety_id: null });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.cropName}</span>
        <input
          value={values.crop_name}
          onChange={(e) => onCropName(e.target.value)}
          placeholder={t.cropNamePlaceholder}
          list="krushi-crop-names"
          required
          maxLength={64}
        />
        <datalist id="krushi-crop-names">
          {cropNames.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </label>

      <label className="field">
        <span>{t.varietyLabel}</span>
        <select
          value={values.crop_variety_id ?? ""}
          onChange={(e) => onVarietySelect(e.target.value)}
          disabled={matchingVarieties.length === 0}
        >
          <option value="">— {t.varietyAny} —</option>
          {matchingVarieties.map((v) => (
            <option key={v.id} value={v.id}>
              {v.variety_name ?? v.crop_name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>
          {t.varietyLabel} ({t.optional})
        </span>
        <input
          value={values.variety_name}
          onChange={(e) => onVarietyText(e.target.value)}
          maxLength={64}
        />
      </label>

      <div className="row2">
        <label className="field">
          <span>{t.area}</span>
          <input
            inputMode="decimal"
            value={values.area}
            onChange={(e) => set("area", e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>{t.areaUnit}</span>
          <select
            value={values.area_unit}
            onChange={(e) => set("area_unit", e.target.value)}
          >
            <option value="acre">{t.acre}</option>
            <option value="hectare">{t.hectare}</option>
            <option value="guntha">{t.guntha}</option>
          </select>
        </label>
      </div>

      <div className="row2">
        <label className="field">
          <span>{t.season}</span>
          <select value={values.season} onChange={(e) => set("season", e.target.value)}>
            <option value="kharif">{t.seasonKharif}</option>
            <option value="rabi">{t.seasonRabi}</option>
            <option value="zaid">{t.seasonZaid}</option>
            <option value="perennial">{t.seasonPerennial}</option>
            <option value="other">{t.seasonOther}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.statusLabel}</span>
          <select value={values.status} onChange={(e) => set("status", e.target.value)}>
            <option value="planned">{t.statusPlanned}</option>
            <option value="sown">{t.statusSown}</option>
            <option value="growing">{t.statusGrowing}</option>
            <option value="harvested">{t.statusHarvested}</option>
            <option value="failed">{t.statusFailed}</option>
            <option value="cancelled">{t.statusCancelled}</option>
          </select>
        </label>
      </div>

      <div className="row2">
        <label className="field">
          <span>{t.sowingDate}</span>
          <input
            type="date"
            value={values.sowing_date}
            onChange={(e) => set("sowing_date", e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>
            {t.harvestDate} ({t.optional})
          </span>
          <input
            type="date"
            value={values.expected_harvest_date}
            onChange={(e) => set("expected_harvest_date", e.target.value)}
          />
        </label>
      </div>

      <label className="field">
        <span>
          {t.notes} ({t.optional})
        </span>
        <textarea
          value={values.notes}
          onChange={(e) => set("notes", e.target.value)}
          placeholder={t.notesPlaceholder}
          maxLength={2000}
          rows={3}
        />
      </label>

      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
