/**
 * Suppliers list (Step 16, auth-only): search + add + edit.
 * No GST/valuation/batch UI — plain supplier master only.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Supplier } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

const EMPTY = { name: "", mobile_number: "", email: "", address: "", gstin: "", notes: "" };

export default function SuppliersPage() {
  const { t } = useAuth();
  const [suppliers, setSuppliers] = useState<Supplier[] | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (q: string) => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setSuppliers(await api.listSuppliers(token, q.trim() || undefined));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load("");
  }, [load]);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    load(search);
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy || !form.name.trim()) return;
    setBusy(true);
    try {
      const created = await api.createSupplier(token, {
        name: form.name.trim(),
        mobile_number: form.mobile_number.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        gstin: form.gstin.trim() || null,
        notes: form.notes.trim() || null,
      });
      setSuppliers((prev) => (prev ? [created, ...prev] : [created]));
      setForm(EMPTY);
      setShowAdd(false);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onUpdate(e: React.FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || busy || !editing) return;
    setBusy(true);
    try {
      const updated = await api.updateSupplier(token, editing.id, {
        name: editing.name,
        mobile_number: editing.mobile_number,
        email: editing.email,
        address: editing.address,
        gstin: editing.gstin,
        notes: editing.notes,
        is_active: editing.is_active,
      });
      setSuppliers((prev) => prev?.map((s) => (s.id === updated.id ? updated : s)) ?? [updated]);
      setEditing(null);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <h1>🏭 पुरवठादार Suppliers</h1>
        <p>
          <Link href="/store/purchases">← खरेदी Purchases</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        <form onSubmit={onSearch}>
          <input
            type="search"
            placeholder="शोधा Search (नाव/mobile)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn" type="submit">शोधा Search</button>
        </form>
        <p>
          <button className="btn" type="button" onClick={() => setShowAdd((v) => !v)}>
            {showAdd ? t.cancel : "＋ नवीन पुरवठादार New Supplier"}
          </button>
        </p>
        {showAdd ? (
          <section className="card">
            <h2>नवीन पुरवठादार New Supplier</h2>
            <form onSubmit={onCreate}>
              <label>नाव Name*<br />
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </label><br />
              <label>मोबाईल Mobile<br />
                <input value={form.mobile_number} onChange={(e) => setForm({ ...form, mobile_number: e.target.value })} />
              </label><br />
              <label>ईमेल Email<br />
                <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </label><br />
              <label>पत्ता Address<br />
                <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </label><br />
              <label>नोंद Notes<br />
                <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </label><br />
              <button className="btn" type="submit" disabled={busy || !form.name.trim()}>
                {busy ? t.loading : t.save}
              </button>
            </form>
          </section>
        ) : null}
        {suppliers === null ? (
          <p className="muted">{t.loading}</p>
        ) : suppliers.length === 0 ? (
          <p className="muted">पुरवठादार नाहीत No suppliers yet.</p>
        ) : (
          <div className="grid">
            {suppliers.map((s) => (
              <article className="card" key={s.id}>
                <h2>{s.name}</h2>
                <p className="muted">{s.mobile_number ?? "—"} · {s.email ?? ""}</p>
                <p className="muted">{s.is_active ? "सक्रिय Active" : "बंद Inactive"}</p>
                <p>
                  <Link href={`/store/suppliers/${s.id}`}>{t.viewDetails} →</Link>
                  {" · "}
                  <button type="button" className="link-btn-plain" onClick={() => setEditing(s)}>
                    {t.edit}
                  </button>
                </p>
              </article>
            ))}
          </div>
        )}
        {editing ? (
          <section className="card">
            <h2>{t.edit}: {editing.name}</h2>
            <form onSubmit={onUpdate}>
              <label>नाव Name<br />
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} required />
              </label><br />
              <label>मोबाईल Mobile<br />
                <input value={editing.mobile_number ?? ""} onChange={(e) => setEditing({ ...editing, mobile_number: e.target.value || null })} />
              </label><br />
              <label>ईमेल Email<br />
                <input value={editing.email ?? ""} onChange={(e) => setEditing({ ...editing, email: e.target.value || null })} />
              </label><br />
              <label>पत्ता Address<br />
                <input value={editing.address ?? ""} onChange={(e) => setEditing({ ...editing, address: e.target.value || null })} />
              </label><br />
              <label>नोंद Notes<br />
                <input value={editing.notes ?? ""} onChange={(e) => setEditing({ ...editing, notes: e.target.value || null })} />
              </label><br />
              <label>
                <input type="checkbox" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
                {" "}सक्रिय Active
              </label><br />
              <button className="btn" type="submit" disabled={busy}>{busy ? t.loading : t.save}</button>
              {" "}
              <button className="btn" type="button" onClick={() => setEditing(null)}>{t.cancel}</button>
            </form>
          </section>
        ) : null}
      </main>
    </AuthGate>
  );
}
