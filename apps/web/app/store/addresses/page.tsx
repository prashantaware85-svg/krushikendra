/**
 * Delivery Addresses (auth-only): list, add, edit, delete, default.
 * Owner-scoped — one default per farmer, enforced server-side.
 */
"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Address, type AddressWrite } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

const EMPTY = {
  full_name: "",
  mobile_number: "",
  address_line_1: "",
  address_line_2: "",
  village: "",
  taluka: "",
  district: "",
  state: "",
  pincode: "",
  landmark: "",
};

export default function AddressesPage() {
  const { t } = useAuth();
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setAddresses(await api.listAddresses(token));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function startAdd() {
    setEditing("new");
    setForm(EMPTY);
    setError(null);
  }

  function startEdit(a: Address) {
    setEditing(a.id);
    setForm({
      full_name: a.label ?? "",
      mobile_number: a.phone,
      address_line_1: a.line1,
      address_line_2: "",
      village: a.city,
      taluka: "",
      district: "",
      state: a.state,
      pincode: a.pincode,
      landmark: "",
    });
    setError(null);
  }

  function clean(values: typeof EMPTY): AddressWrite {
    // Backend contract: label/line1/city/state/pincode/phone only.
    // Extra UI inputs (line2/taluka/district/landmark) have no backend
    // field — line2 is folded into line1, the rest are not sent.
    const line1 = [values.address_line_1.trim(), values.address_line_2.trim()]
      .filter(Boolean)
      .join(", ");
    const label = values.full_name.trim();
    return {
      ...(label ? { label } : {}),
      line1,
      city: values.village.trim(),
      state: values.state.trim(),
      pincode: values.pincode.trim(),
      phone: values.mobile_number.trim(),
    };
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !editing || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (editing === "new") {
        await api.createAddress(token, clean(form));
      } else {
        await api.updateAddress(token, editing, clean(form));
      }
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t.deleteAddressConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteAddress(token, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function onDefault(id: string) {
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.setDefaultAddress(token, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  const set = (key: keyof typeof EMPTY, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <div className="page-head">
          <h1>📍 {t.addressesTitle}</h1>
          <button className="btn add-btn" type="button" onClick={startAdd}>
            + {t.addAddress}
          </button>
        </div>
        {error ? <p className="form-error">{error}</p> : null}

        {editing ? (
          <section className="card">
            <form onSubmit={onSubmit}>
              <label className="field">
                <span>{t.fullNameLabel}</span>
                <input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required maxLength={128} />
              </label>
              <div className="row2">
                <label className="field">
                  <span>{t.mobileLabel}</span>
                  <input value={form.mobile_number} onChange={(e) => set("mobile_number", e.target.value)} required inputMode="numeric" />
                </label>
                <label className="field">
                  <span>{t.pincodeLabel}</span>
                  <input value={form.pincode} onChange={(e) => set("pincode", e.target.value)} required inputMode="numeric" maxLength={10} />
                </label>
              </div>
              <label className="field">
                <span>{t.addressLine1}</span>
                <input value={form.address_line_1} onChange={(e) => set("address_line_1", e.target.value)} required maxLength={256} />
              </label>
              <label className="field">
                <span>{t.addressLine2}</span>
                <input value={form.address_line_2} onChange={(e) => set("address_line_2", e.target.value)} maxLength={256} />
              </label>
              <div className="row2">
                <label className="field">
                  <span>{t.villageLabel}</span>
                  <input value={form.village} onChange={(e) => set("village", e.target.value)} required maxLength={64} />
                </label>
                <label className="field">
                  <span>{t.talukaLabel}</span>
                  <input value={form.taluka} onChange={(e) => set("taluka", e.target.value)} maxLength={64} />
                </label>
              </div>
              <div className="row2">
                <label className="field">
                  <span>{t.districtLabel}</span>
                  <input value={form.district} onChange={(e) => set("district", e.target.value)} required maxLength={64} />
                </label>
                <label className="field">
                  <span>{t.stateLabel}</span>
                  <input value={form.state} onChange={(e) => set("state", e.target.value)} required maxLength={64} />
                </label>
              </div>
              <label className="field">
                <span>{t.landmarkLabel}</span>
                <input value={form.landmark} onChange={(e) => set("landmark", e.target.value)} maxLength={128} />
              </label>
              <div className="card-actions">
                <button className="btn" type="submit" disabled={busy}>
                  {t.saveAddress}
                </button>
                <button className="btn-secondary" type="button" onClick={() => setEditing(null)}>
                  {t.cancel}
                </button>
              </div>
            </form>
          </section>
        ) : null}

        {addresses === null ? (
          <p className="muted">{t.loading}</p>
        ) : (
          addresses.map((a) => (
            <section className="card" key={a.id}>
              <h2>
                {a.label ?? a.line1} {a.is_default ? `(${t.defaultBadge})` : ""}
              </h2>
              <p className="muted">
                {a.line1}, {a.city}, {a.state} {a.pincode}
              </p>
              <p className="muted">📱 {a.phone}</p>
              <div className="card-actions">
                {!a.is_default ? (
                  <button className="btn-secondary" type="button" onClick={() => onDefault(a.id)}>
                    {t.setDefault}
                  </button>
                ) : null}
                <button className="btn-secondary" type="button" onClick={() => startEdit(a)}>
                  {t.edit}
                </button>
                <button className="btn-danger" type="button" onClick={() => onDelete(a.id)}>
                  {t.deleteAddress}
                </button>
              </div>
            </section>
          ))
        )}
      </main>
    </AuthGate>
  );
}
