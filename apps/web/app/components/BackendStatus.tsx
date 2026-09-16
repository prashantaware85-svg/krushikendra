type Props = {
  data: {
    status: string;
    service?: string;
    version?: string;
    environment?: string;
  } | null;
  error: string | null;
  apiUrl: string;
};

/**
 * Server-rendered status card. No client JS needed in Step 1.
 */
export function BackendStatus({ data, error, apiUrl }: Props) {
  const ok = data?.status === "ok" && !error;
  return (
    <div className="card">
      <h2>⚙️ Backend status</h2>
      {ok ? (
        <p className="status-ok">● Connected ({data?.service})</p>
      ) : (
        <p className="status-err">● {error ?? "Unknown backend error"}</p>
      )}
      <p className="muted">
        API: <code>{apiUrl}</code>
        {data?.environment ? (
          <>
            {" · "}env: <code>{data.environment}</code>
          </>
        ) : null}
        {data?.version ? (
          <>
            {" · "}v<code>{data.version}</code>
          </>
        ) : null}
      </p>
    </div>
  );
}
