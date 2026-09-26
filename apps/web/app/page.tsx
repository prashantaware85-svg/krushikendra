import Link from "next/link";
import { BackendStatus } from "./components/BackendStatus";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HealthPayload = {
  status: string;
  service?: string;
  version?: string;
  environment?: string;
};

async function getBackendHealth(): Promise<{
  data: HealthPayload | null;
  error: string | null;
}> {
  try {
    const res = await fetch(`${API_URL}/health`, { next: { revalidate: 60 } });
    if (!res.ok) {
      return { data: null, error: `Backend responded with HTTP ${res.status}` };
    }
    const data = (await res.json()) as HealthPayload;
    return { data, error: null };
  } catch {
    return { data: null, error: "Backend unreachable — is FastAPI running?" };
  }
}

export default async function HomePage() {
  const { data, error } = await getBackendHealth();

  return (
    <main className="main">
      <section className="hero">
        <span className="badge">STEP 1 · Foundation</span>
        <h1>🌱 Krushi Seva</h1>
        <p>Production-ready agriculture platform for Indian farmers.</p>
        <p className="muted" style={{ color: "#e8f5e9" }}>
          Next.js frontend skeleton — backend status is checked live below.
        </p>
      </section>

      <div className="grid">
        <BackendStatus data={data} error={error} apiUrl={API_URL} />

        <div className="card">
          <h2>🔌 Endpoints</h2>
          <p>
            Frontend: <code>GET /api/health</code>
          </p>
          <p>
            Backend: <code>GET /health</code> · <code>GET /api/v1/health</code>
          </p>
          <p>
            API docs: <code>{API_URL}/docs</code>
          </p>
        </div>

        <div className="card">
          <h2>🧑‍🌾 Farmer Login</h2>
          <p className="muted">
            OTP login for farmers (Marathi / Hindi / English ready).
          </p>
          <p>
            <Link href="/login">Login with mobile number →</Link>
          </p>
        </div>

        <div className="card">
          <h2>🗺️ Roadmap</h2>
          <p className="muted">
            Step 2: Postgres + auth + farmer/farm modules. Step 5: AI/RAG
            (Krushi Mitra). See <code>docs/architecture.md</code>.
          </p>
        </div>
      </div>

      <p className="footer muted">
        Step 1 foundation only — no auth, database, AI, or domain features yet.
      </p>
    </main>
  );
}
