import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, type HomeStatus, type LegacyFound } from "../api/client";

/** Until a data folder is chosen (first start of this version, or the folder went missing) the app shows the setup
 * screen instead of the pages; data written by a newer version shows a read-only banner above them. */
export function SetupGate({ children }: { children: ReactNode }) {
  const q = useQuery({ queryKey: ["setup"], queryFn: api.setupStatus, staleTime: Infinity, retry: false });
  const up = useQuery({ queryKey: ["updates"], queryFn: api.updates, staleTime: 60 * 60_000, retry: false,
    enabled: q.data?.state === "ok" });
  if (q.isLoading) return <div className="skeleton" style={{ height: 400 }} aria-busy="true" />;
  const s = q.data;
  if (s && (s.state === "unset" || s.state === "missing")) return <Setup status={s} />;
  return (
    <>
      {s?.state === "newer" && <div className="setup-banner neg" role="alert"><b>Read-only:</b> {s.read_only}</div>}
      {s?.warning && <div className="setup-banner warn-text" role="alert">{s.warning}</div>}
      {up.data?.newer && (
        <div className="setup-banner">Market Radar {up.data.latest} is out (you have {up.data.current}).{" "}
          {up.data.url && <a href={up.data.url} target="_blank" rel="noreferrer">What&apos;s new and the download</a>}
          {" "}· <Link to="/guide/brugervejledning/dine-data">How to update</Link></div>
      )}
      {children}
    </>
  );
}

function describe(f: LegacyFound): string {
  const c = f.counts;
  const bits = [
    c.transactions != null ? `${c.transactions} transactions` : null,
    c.portfolios != null ? `${c.portfolios} portfolios` : null,
    ...Object.entries(f.personal).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`),
    f.imports ? `${f.imports} broker files` : null,
    f.history_files ? `${f.history_files} history files` : null,
  ];
  return bits.filter(Boolean).join(" · ") || "no files";
}

function Setup({ status }: { status: HomeStatus }) {
  const qc = useQueryClient();
  const found = status.found;
  const [source, setSource] = useState<string | null>(found.find((f) => !f.moved)?.path ?? found[0]?.path ?? null);
  const [extra, setExtra] = useState<LegacyFound | null>(null);
  const [other, setOther] = useState("");
  const [target, setTarget] = useState(status.home ?? status.default_home);
  const [copyCache, setCopyCache] = useState(true);
  const [existing, setExisting] = useState("");
  const scan = useMutation({ mutationFn: api.setupScan, onSuccess: (f) => { setExtra(f); setSource(f.path); } });
  const run = useMutation({
    mutationFn: api.setup,
    onSuccess: () => qc.invalidateQueries(),     // every page loads again, now from the data folder
  });
  const all = extra && !found.some((f) => f.path === extra.path) ? [...found, extra] : found;
  const missing = status.state === "missing";
  return (
    <main className="setup">
      <h1>{missing ? "Your data folder can't be found" : `Welcome to Market Radar ${status.app_version}`}</h1>
      {missing ? (
        <p>Market Radar remembers your data in <code>{status.home}</code>, but that folder isn&apos;t there. If it is on a
          drive that isn&apos;t connected, connect it and reload. If you moved it, say where it is now.</p>
      ) : (
        <p>Your data now lives in a folder of its own, outside the program folder, so a new version never touches it:
          portfolios and trades, notes, research, the journal and the history the radar builds up. Choose where it goes,
          once. Market data is kept apart in <code>{status.default_cache}</code> and can always be downloaded again.</p>
      )}

      {missing && (
        <section className="card">
          <h2>Use the folder where it is now</h2>
          <div className="setup-row">
            <input className="setup-path" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Data folder" />
            <button className="btn primary" disabled={run.isPending}
              onClick={() => run.mutate({ action: "use", home: target, copy_cache: false })}>Use this folder</button>
          </div>
        </section>
      )}
      {!missing && (
        <details className="card">
          <summary>Already have a data folder? (copied from another computer, or moved)</summary>
          <div className="setup-row">
            <input className="setup-path" value={existing} onChange={(e) => setExisting(e.target.value)}
              placeholder="The folder that holds market-radar.json" aria-label="Existing data folder" />
            <button className="btn" disabled={!existing.trim() || run.isPending}
              onClick={() => run.mutate({ action: "use", home: existing.trim(), copy_cache: false })}>Use this folder</button>
          </div>
        </details>
      )}

      <section className="card">
        <h2>{all.length ? "Copy your data from an earlier version" : "Data from an earlier version"}</h2>
        {all.length ? (
          <fieldset className="setup-found">
            <legend className="muted small">Found next to this program folder. The old folder is not changed; it gets a note saying where the data went.</legend>
            {all.map((f) => (
              <label key={f.path} className={`setup-choice ${source === f.path ? "on" : ""}`}>
                <input type="radio" name="source" checked={source === f.path} onChange={() => setSource(f.path)} />
                <span><b>{f.path}</b>{f.is_this_install && <span className="muted"> (this folder)</span>}
                  {f.moved && <span className="muted"> (copied before)</span>}<br />
                  <span className="muted small">{describe(f)}{f.newest && ` · last change ${f.newest.replace("T", " ")}`}</span></span>
              </label>
            ))}
          </fieldset>
        ) : (
          <p className="muted">None found next to this program folder. If you used Market Radar before, type the folder you
            unzipped it in.</p>
        )}
        <div className="setup-row">
          <input className="setup-path" placeholder="Another folder, e.g. ~/Downloads/market-radar-v0.1" value={other}
            onChange={(e) => setOther(e.target.value)} aria-label="Old Market Radar folder" />
          <button className="btn" disabled={!other.trim() || scan.isPending} onClick={() => scan.mutate(other.trim())}>Look there</button>
        </div>
        {scan.isError && <p className="neg">{(scan.error as Error).message}</p>}
      </section>

      <section className="card">
        <h2>Where your data goes</h2>
        <div className="setup-row">
          <input className="setup-path" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="New data folder" />
        </div>
        <p className="muted small">Keep it out of OneDrive, iCloud Drive and Dropbox: a database synced while in use can be
          damaged. Backups can go there instead.</p>
        {source && (
          <label className="check small">
            <input type="checkbox" checked={copyCache} onChange={(e) => setCopyCache(e.target.checked)} /> Copy the
            downloaded market data too (saves downloading it again)
          </label>
        )}
        <div className="setup-row">
          {source && (
            <button className="btn primary" disabled={run.isPending}
              onClick={() => run.mutate({ action: "migrate", source, home: target, copy_cache: copyCache })}>
              {run.isPending ? "Copying and checking…" : "Copy my data"}</button>
          )}
          <button className="btn" disabled={run.isPending}
            onClick={() => run.mutate({ action: "create", home: target, copy_cache: false })}>Start with an empty folder</button>
        </div>
        {run.isError && <p className="neg">{(run.error as Error).message}</p>}
      </section>
      <p className="muted small">This computer remembers the choice in <code>{status.pointer}</code>. From the command
        line: <code>uv run radar setup</code> and <code>uv run radar paths</code>.</p>
    </main>
  );
}
