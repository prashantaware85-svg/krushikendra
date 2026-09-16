/**
 * Shared farm create/edit form (mobile-first, large touch targets).
 * Strings come from `t` — no hardcoded UI text here.
 */
"use client";

import type { FormEvent } from "react";
import type { AreaUnit, FarmWrite } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export type FarmFormValues = {
  farm_name: string;
  area: string;
  area_unit: AreaUnit;
  state: string;
  district: string;
  taluka: string;
  village: string;
  latitude: string;
  longitude: string;
  land_type: string;
  soil_type: string;
  irrigation_type: string;
  water_source: string;
  ownership_type: string;
};

export const EMPTY_FARM: FarmFormValues = {
  farm_name: "",
  area: "",
  area_unit: "acre",
  state: "",
  district: "",
  taluka: "",
  village: "",
  latitude: "",
  longitude: "",
  land_type: "",
  soil_type: "",
  irrigation_type: "",
  water_source: "",
  ownership_type: "",
};

function opt(v: string): string | undefined {
  const s = v.trim();
  return s ? s : undefined;
}

/** Convert form values to the API payload (empty optionals omitted). */
export function toFarmWrite(f: FarmFormValues): FarmWrite {
  return {
    farm_name: f.farm_name.trim(),
    area: f.area.trim(),
    area_unit: f.area_unit,
    state: opt(f.state),
    district: opt(f.district),
    taluka: opt(f.taluka),
    village: opt(f.village),
    latitude: opt(f.latitude),
    longitude: opt(f.longitude),
    land_type: opt(f.land_type),
    soil_type: opt(f.soil_type),
    irrigation_type: (opt(f.irrigation_type) ?? undefined) as FarmWrite["irrigation_type"],
    water_source: (opt(f.water_source) ?? undefined) as FarmWrite["water_source"],
    ownership_type: (opt(f.ownership_type) ?? undefined) as FarmWrite["ownership_type"],
  };
}

export function FarmForm({
  t,
  values,
  onChange,
  onSubmit,
  busy,
  error,
  submitLabel,
}: {
  t: Record<StringKey, string>;
  values: FarmFormValues;
  onChange: (v: FarmFormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
}) {
  const set = (key: keyof FarmFormValues, value: string) =>
    onChange({ ...values, [key]: value });

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  const select = (
    key: "area_unit" | "irrigation_type" | "water_source" | "ownership_type",
    label: string,
    options: [string, string][],
    allowEmpty: boolean,
  ) => (
    <label className="field" key={key}>
      <span>{label}</span>
      <select value={values[key]} onChange={(e) => set(key, e.target.value)}>
        {allowEmpty ? <option value="">—</option> : null}
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <form onSubmit={submit}>
      <label className="field">
        <span>{t.farmName}</span>
        <input
          value={values.farm_name}
          onChange={(e) => set("farm_name", e.target.value)}
          placeholder={t.farmNamePlaceholder}
          required
          maxLength={128}
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
        {select("area_unit", t.areaUnit, [
          ["acre", t.acre],
          ["hectare", t.hectare],
          ["guntha", t.guntha],
        ], false)}
      </div>

      {select("ownership_type", t.ownership, [
        ["owned", t.ownershipOwned],
        ["leased", t.ownershipLeased],
        ["shared", t.ownershipShared],
        ["other", t.ownershipOther],
      ], true)}

      <h3>{t.location}</h3>
      {(
        [
          ["state", t.stateLabel],
          ["district", t.districtLabel],
          ["taluka", t.talukaLabel],
          ["village", t.villageLabel],
        ] as const
      ).map(([key, label]) => (
        <label className="field" key={key}>
          <span>{label}</span>
          <input
            value={values[key]}
            onChange={(e) => set(key, e.target.value)}
            maxLength={64}
          />
        </label>
      ))}

      <h3>{t.gps}</h3>
      <p className="muted small">{t.gpsHint}</p>
      <div className="row2">
        <label className="field">
          <span>{t.latitude}</span>
          <input
            inputMode="decimal"
            value={values.latitude}
            onChange={(e) => set("latitude", e.target.value)}
            placeholder="19.85"
          />
        </label>
        <label className="field">
          <span>{t.longitude}</span>
          <input
            inputMode="decimal"
            value={values.longitude}
            onChange={(e) => set("longitude", e.target.value)}
            placeholder="73.98"
          />
        </label>
      </div>

      <h3>{t.soilInfo}</h3>
      <label className="field">
        <span>{t.landType}</span>
        <input
          value={values.land_type}
          onChange={(e) => set("land_type", e.target.value)}
          placeholder={t.landTypePlaceholder}
          maxLength={32}
        />
      </label>
      <label className="field">
        <span>{t.soilType}</span>
        <input
          value={values.soil_type}
          onChange={(e) => set("soil_type", e.target.value)}
          placeholder={t.soilTypePlaceholder}
          maxLength={32}
        />
      </label>

      <h3>{t.irrigation}</h3>
      {select("irrigation_type", t.irrigation, [
        ["rainfed", t.irrigationRainfed],
        ["drip", t.irrigationDrip],
        ["sprinkler", t.irrigationSprinkler],
        ["flood", t.irrigationFlood],
        ["mixed", t.irrigationMixed],
        ["other", t.irrigationOther],
      ], true)}
      {select("water_source", t.waterSource, [
        ["rain", t.waterRain],
        ["borewell", t.waterBorewell],
        ["well", t.waterWell],
        ["canal", t.waterCanal],
        ["farm_pond", t.waterFarmPond],
        ["river", t.waterRiver],
        ["other", t.waterOther],
      ], true)}

      {error ? <p className="form-error">{error}</p> : null}
      <button className="btn" type="submit" disabled={busy}>
        {submitLabel}
      </button>
    </form>
  );
}
