import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type BackupRow, type DataFolder } from "../api/client";

const TIER: Record<DataFolder["tier"], string> = {
  personal: "yours: can't be downloaded again",
  history: "built up over time: can't be downloaded again",
  cache: "can be deleted: downloaded again by the next update",
};

const MIRROR_STALE_DAYS = 14;

function age(iso: string | undefined): number | null {
  return iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000) : null;
}

const kb = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} KB`);

/** "Your data" on the Data page: where everything is, backups (here and in a second folder), restore and export. */
export function DataHome() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["data-home"], queryFn: api.dataHome, retry: false });
  const refresh = () => qc.invalidateQueries({ queryKey: ["data-home"] });
  const backup = useMutation({ mutationFn: api.backupNow, onSuccess: refresh });
  const open = useMutation({ mutationFn: api.openFolder });
  const mirror = useMutation({ mutationFn: api.setMirror, onSuccess: (d) => qc.setQueryData(["data-home"], d) });
  const restore = useMutation({ mutationFn: api.restoreBackup, onSuccess: () => qc.invalidateQueries() });
  const up = useQuery({ queryKey: ["updates"], queryFn: api.updates, retry: false });
  const setUp = useMutation({ mutationFn: api.setUpdates, onSuccess: (u) => qc.setQueryData(["updates"], u) });
  const [mirrorPath, setMirrorPath] = useState("");
  const [showAll, setShowAll] = useState(false);
  if (!q.data) return q.isError ? <p className="neg">{(q.error as Error).message}</p> : null;
  const d = q.data;
  const last = d.backups[0];
  const lastMirror = d.mirror_backups[0];
  const mirrorAge = age(lastMirror?.created);
  const rows: BackupRow[] = showAll ? d.backups : d.backups.slice(0, 5);
  const ask = (b: BackupRow) => {
    if (window.confirm(`Replace your data with the backup from ${b.created.replace("T", " ")}?\n\nWhat is there now is backed up first, so this can be undone.`))
      restore.mutate(b.name);
  };
  return (
    <>
      <h2 id="your-data">Your data</h2>
      <div className="card">
        <p className="note">Your own data lives apart from the program, so installing a new version never touches it.
          Back up the data folder; the market data can always be downloaded again.
          {d.status.app_version && <> This is Market Radar {d.status.app_version}.</>}</p>
        {d.status.warning && <p className="warn-text">{d.status.warning}</p>}
        <table className="plain data-home">
          <tbody>
            {d.folders.map((f) => (
              <tr key={f.key}>
                <td><b>{f.label}</b><br /><span className="muted small">{TIER[f.tier]}</span></td>
                <td className="wrap"><code>{f.path}</code></td>
                <td className="num muted small">{f.files} files · {f.mb} MB</td>
                <td><button className="btn small" onClick={() => open.mutate(f.key)} title="Show in Explorer / Finder">Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Backups <span className="meta">{last ? `last ${last.created.replace("T", " ")}` : "none yet"}</span></h2>
        <p className="note">Taken by themselves once a day and before a new version first runs; kept 7 days, 5 weeks
          and 12 months. Each one holds your database, documents and history, and is checked file by file before a restore.</p>
        <div className="setup-row">
          <button className="btn primary" disabled={backup.isPending} onClick={() => backup.mutate()}>
            {backup.isPending ? "Backing up…" : "Back up now"}</button>
          <a className="btn" href={api.dataExportUrl} download>Export my data (CSV, JSON, Markdown)</a>
        </div>
        {backup.isError && <p className="neg">{(backup.error as Error).message}</p>}
        {restore.isSuccess && <p>Restored {restore.data.restored}. What was there before is in {restore.data.saved_first}.</p>}
        {restore.isError && <p className="neg">{(restore.error as Error).message}</p>}
        {d.backups.length > 0 && (
          <table className="plain data-home">
            <tbody>
              {rows.map((b) => (
                <tr key={b.name}>
                  <td>{b.created.replace("T", " ")}</td>
                  <td className="muted">{b.kind}</td>
                  <td className="num muted">{kb(b.size)}</td>
                  <td><button className="btn small" disabled={restore.isPending} onClick={() => ask(b)}>Restore…</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {d.backups.length > 5 && (
          <button className="btn small" onClick={() => setShowAll(!showAll)}>{showAll ? "Fewer" : `All ${d.backups.length}`}</button>
        )}

        <h3>A second copy, off this disk</h3>
        {d.mirror ? (
          <p>Every backup is also copied to <code>{d.mirror}</code>{" "}
            {mirrorAge == null ? <span className="warn-text">(nothing there yet)</span>
              : <span className={mirrorAge > MIRROR_STALE_DAYS ? "warn-text" : "muted"}>(newest {mirrorAge} day{mirrorAge === 1 ? "" : "s"} old)</span>}
            {" "}<button className="btn small" onClick={() => mirror.mutate(null)}>Stop</button></p>
        ) : (
          <p className="warn-text">Backups are only on this computer. Choose a second folder, such as a OneDrive, iCloud Drive
            or Dropbox folder or a USB disk, so a broken disk doesn&apos;t take them too.</p>
        )}
        <div className="setup-row">
          <input className="setup-path" placeholder="e.g. C:\Users\you\OneDrive\Market Radar backups" value={mirrorPath}
            onChange={(e) => setMirrorPath(e.target.value)} aria-label="Second backup folder" />
          <button className="btn" disabled={!mirrorPath.trim() || mirror.isPending} onClick={() => mirror.mutate(mirrorPath.trim())}>
            {d.mirror ? "Change" : "Use this folder"}</button>
        </div>
        {mirror.isError && <p className="neg">{(mirror.error as Error).message}</p>}
      </div>

      <div className="card">
        <h2>New versions</h2>
        <p className="note">To update: download the new zip, unzip it anywhere and start it. It finds this data folder, backs
          it up and carries on; the old program folder can then be deleted.</p>
        {up.data && (up.data.repo ? (
          <>
            <label className="check">
              <input type="checkbox" checked={up.data.enabled} disabled={setUp.isPending}
                onChange={(e) => setUp.mutate(e.target.checked)} /> Check for a new version once a day (asks GitHub; nothing
              about you is sent)
            </label>
            {up.data.enabled && (
              <p className="muted small">
                {up.data.newer ? <>Market Radar {up.data.latest} is out{up.data.url && <>: <a href={up.data.url} target="_blank" rel="noreferrer">release page</a></>}.</>
                  : up.data.error ? `Not checked: ${up.data.error}.` : `You have the newest version (${up.data.current}).`}
                {up.data.checked && <> Checked {up.data.checked.replace("T", " ")}.</>}
              </p>
            )}
          </>
        ) : <p className="muted small">This copy doesn&apos;t name a place to check for new versions (settings.yaml
          <code> updates.repo</code>); whoever gave you Market Radar will tell you when there is one.</p>)}
      </div>
    </>
  );
}
