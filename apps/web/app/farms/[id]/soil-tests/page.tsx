/**
 * Soil Test History (auth-only): chronological lab records for one farm.
 * Display only — no recommendations derived from values.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type SoilTest } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";

export default function SoilHistoryPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [tests, setTests] = useState<SoilTest[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setTests(await api.listSoilTests(token, params.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}`}>← {t.backToFarm}</Link>
        </p>
        <div className="page-head">
          <h1>🧪 {t.soilHistory}</h1>
          <Link className="btn add-btn" href={`/farms/${params.id}/soil-tests/new`}>
            + {t.addSoilTest}
          </Link>
        </div>
        {error ? <p className="form-error">{error}</p> : null}
        {tests === null ? (
          <p className="muted">{t.loading}</p>
        ) : tests.length === 0 ? (
          <section className="card">
            <p className="muted">{t.noSoilTest}</p>
            <Link className="btn" href={`/farms/${params.id}/soil-tests/new`}>
              + {t.addSoilTest}
            </Link>
          </section>
        ) : (
          <div className="grid">
            {tests.map((s) => (
              <article className="card" key={s.id}>
                <h2>{s.test_date}</h2>
                <p>
                  pH {s.ph ?? t.notSet} · N: {s.nitrogen ?? t.notSet} · P:{" "}
                  {s.phosphorus ?? t.notSet} · K: {s.potassium ?? t.notSet}
                </p>
                <p className="muted">
                  {s.laboratory_name ?? ""} {s.has_report ? `· 📎 ${t.hasReport}` : ""}
                </p>
                <p>
                  <Link href={`/farms/${params.id}/soil-tests/${s.id}`}>
                    [{t.viewDetails}]
                  </Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
