import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, type SectorEtfRow, type SectorEtfSector, type SectorEtfsView } from "../api/client";
import { Loaded, PageHead, Pct, Quadrant } from "../components/cells";
import { useScrollToHash } from "../components/Markdown";
import { DataTable, type Col } from "../components/DataTable";
import { Sparkline } from "../components/Sparkline";
import { Term } from "../components/Term";
import { TickerLink } from "../components/TickerLink";
import { Badge } from "../components/ui";
import { date, num } from "../lib/format";
import { pageChapter, useGuideTree } from "../lib/guide";
import { sectorAnchor } from "../lib/sectorEtfs";


const SCOPE: Record<string, string> = { world: "World", us: "US", europe: "Europe", other: "Other" };

const ter = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(2)}%`);

function TaxBadge({ e, year }: { e: SectorEtfRow; year: number }) {
  const t = e.tax;
  const next = t.next_year === "no" && t.status === "yes" ? " Leaves the list next year." : "";
  if (t.tax_class === "aktiebaseret")
    return <Badge kind={next ? "warn" : "pos"} title={`On SKAT's positive list ${t.sheet_year}: share income, allowed on an aktiesparekonto.${next}`}>
      PL · ASK ✓</Badge>;
  if (t.tax_class === "kapitalindkomst")
    return <Badge kind="neg" title={`Not on SKAT's positive list ${t.sheet_year}: capital income, not on an aktiesparekonto.`}>off · ASK ✗</Badge>;
  return <Badge kind="na" title={t.status === "no_sheet" ? `No positive list for ${year} yet.` : "No ISIN to look up."}>?</Badge>;
}

function Rejected({ e, onAllow, busy }: { e: SectorEtfRow; onAllow: () => void; busy: boolean }) {
  const why = e.rejected_reason ? ` ("${e.rejected_reason}")` : "";
  return <>{" "}<Badge kind="neg" title={`You marked it for replacement${why}; replaced ${date(e.rejected_at)}. It isn't picked as the go-to again until you allow it.`}>
    rejected</Badge>{" "}
    <button type="button" className="linkish small" disabled={busy} onClick={onAllow}
      title="Let /sector-etfs pick this fund as the go-to again">Allow again</button></>;
}

function cols(year: number, onAllow: (e: SectorEtfRow) => void, busy: boolean): Col<SectorEtfRow>[] {
  return [
    { key: "rank", label: "#", sort: (e) => e.rank, render: (e) => e.rank, help: "sector_rank" },
    { key: "name", label: "Fund", align: "l", sort: (e) => e.name, search: (e) => `${e.name} ${e.ticker} ${e.isin} ${e.issuer ?? ""}`,
      render: (e) => <>{e.pick && <Badge kind="accent" title="The go-to ETF of the latest /sector-etfs run">go-to</Badge>}{" "}
        <TickerLink symbol={e.ticker} name={e.name} nameFirst />
        {e.rejected && <Rejected e={e} onAllow={() => onAllow(e)} busy={busy} />}</>, csv: (e) => e.ticker, csvHeader: "Ticker" },
    { key: "scope", label: "Scope", align: "l", sort: (e) => e.scope, render: (e) => SCOPE[e.scope] ?? e.scope, help: "fund_scope",
      filter: { kind: "enum" } },
    { key: "isin", label: "ISIN", align: "l", sort: (e) => e.isin, render: (e) => <code>{e.isin}</code>, help: "isin", hidden: true },
    { key: "ter", label: "TER", sort: (e) => e.ter, help: "ter", csv: (e) => e.ter,
      render: (e) => <span title={e.yahoo_ter !== null && e.yahoo_ter !== undefined ? `Yahoo: ${ter(e.yahoo_ter)}` : "Yahoo: –"}>
        {ter(e.ter)}{e.ter_mismatch && <> <Badge kind="warn" title={`Yahoo says ${ter(e.yahoo_ter)}: check the issuer`}>≠</Badge></>}</span> },
    { key: "aum", label: "Size", name: "Size (USD m)", sort: (e) => e.aum_musd, help: "aum", csv: (e) => e.aum_musd,
      render: (e) => e.aum_musd === null || e.aum_musd === undefined ? <span className="muted">–</span> : `${num(e.aum_musd, 0)}m` },
    { key: "dist", label: "Acc/Dist", align: "l", sort: (e) => e.distribution, filter: { kind: "enum" },
      render: (e) => e.distribution === "acc" ? "Acc" : e.distribution === "dist" ? "Dist" : <span className="muted">–</span> },
    { key: "domicile", label: "Dom.", name: "Domicile", align: "l", sort: (e) => e.domicile, render: (e) => e.domicile ?? "–", hidden: true },
    { key: "td", label: "Track. diff", name: "Tracking difference", sort: (e) => e.tracking_diff, help: "tracking_diff", hidden: true,
      render: (e) => <Pct v={e.tracking_diff} digits={2} /> },
    { key: "tax", label: `Tax ${year}`, name: "Tax status", align: "l", sort: (e) => e.tax.tax_class, help: "tax_class",
      filter: { kind: "enum", value: (e) => e.tax.tax_class }, csv: (e) => e.tax.tax_class, render: (e) => <TaxBadge e={e} year={year} /> },
    { key: "r1m", label: "1m", name: "1m DKK", sort: (e) => e.returns_dkk.r1m, render: (e) => <Pct v={e.returns_dkk.r1m} />, help: "ret_dkk", heat: true },
    { key: "r3m", label: "3m", name: "3m DKK", sort: (e) => e.returns_dkk.r3m, render: (e) => <Pct v={e.returns_dkk.r3m} />, help: "ret_dkk", heat: true },
    { key: "r6m", label: "6m", name: "6m DKK", sort: (e) => e.returns_dkk.r6m, render: (e) => <Pct v={e.returns_dkk.r6m} />, help: "ret_dkk", heat: true },
    { key: "r1y", label: "1y", name: "1y DKK", sort: (e) => e.returns_dkk.r1y, render: (e) => <Pct v={e.returns_dkk.r1y} />, help: "ret_dkk", heat: true },
    { key: "ytd", label: "YTD", name: "YTD DKK", sort: (e) => e.returns_dkk.ytd, render: (e) => <Pct v={e.returns_dkk.ytd} />, help: "ret_dkk", hidden: true },
    { key: "vs3m", label: "vs ACWI 3m", sort: (e) => e.vs_acwi.r3m, render: (e) => <Pct v={e.vs_acwi.r3m} />, help: "vs_acwi_dkk", heat: true },
    { key: "vs1y", label: "vs ACWI 1y", sort: (e) => e.vs_acwi.r1y, render: (e) => <Pct v={e.vs_acwi.r1y} />, help: "vs_acwi_dkk", heat: true },
    { key: "spark", label: "1 year", name: "Sparkline", csv: false, render: (e) => <Sparkline values={e.spark} width={90} height={24} /> },
  ];
}

function useFlags(key: string) {
  const qc = useQueryClient();
  const done = (view: SectorEtfsView) => qc.setQueryData(["sector-etfs"], view);
  const mark = useMutation({ mutationFn: (reason: string | null) => api.markSectorEtf(key, reason), onSuccess: done });
  const unflag = useMutation({ mutationFn: (isin: string) => api.unflagSectorEtf(key, isin), onSuccess: done });
  return { mark, unflag, busy: mark.isPending || unflag.isPending, error: mark.error ?? unflag.error };
}

function ReplaceControl({ s, f }: { s: SectorEtfSector; f: ReturnType<typeof useFlags> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  if (s.replace)
    return <>{" "}<Badge kind="warn" title={`The next /sector-etfs run picks another fund for ${s.label}`}>
      marked for replacement {date(s.replace.flagged_at)}</Badge>
      {s.replace.reason && <span className="muted"> &ldquo;{s.replace.reason}&rdquo;</span>}{" "}
      <span className="muted small">The next <code>/sector-etfs</code> run picks another fund.</span>{" "}
      <button type="button" className="btn small" disabled={f.busy} onClick={() => f.unflag.mutate(s.replace!.isin)}>Undo</button></>;
  if (!open)
    return <>{" "}<button type="button" className="btn small" onClick={() => setOpen(true)}
      title="Not traded at your broker, too expensive …: keep it on the page, and let the next /sector-etfs run pick another go-to">
      Mark for replacement</button></>;
  const save = () => f.mark.mutate(reason.trim() || null, { onSuccess: () => setOpen(false) });
  return (
    <span>
      {" "}<input type="text" maxLength={200} placeholder="Why (optional): not at my broker, too expensive …" value={reason}
        onChange={(ev) => setReason(ev.target.value)} onKeyDown={(ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") setOpen(false); }}
        aria-label="Why replace it" size={40} autoFocus />{" "}
      <button type="button" className="btn small primary" disabled={f.busy} onClick={save}>Mark</button>{" "}
      <button type="button" className="btn small" onClick={() => setOpen(false)}>Cancel</button>
    </span>
  );
}

function SectorCard({ s, v, parentLabel }: { s: SectorEtfSector; v: SectorEtfsView; parentLabel?: string }) {
  const pick = s.etfs.find((e) => e.pick);
  const f = useFlags(s.key);
  const { unflag, busy } = f;
  const columns = useMemo(() => cols(v.tax_year, (e) => unflag.mutate(e.isin), busy), [v.tax_year, unflag, busy]);
  return (
    <section id={sectorAnchor(s.key)} className="group">
      <h2>
        {s.label} <span className="muted">({s.key}{parentLabel ? ` · part of ${parentLabel}` : ""})</span>
        {s.rotation.map((r) => <span key={r.ticker}> <Quadrant q={r.quadrant} /></span>)}
      </h2>
      <div className="card">
        {s.rotation.length > 0 && (
          <p className="muted">
            In the rotation:{" "}
            {s.rotation.map((r, i) => <span key={r.ticker}>{i > 0 && " · "}<TickerLink symbol={r.ticker} />{" "}
              #{r.rank ?? "–"} in {r.group_label ?? r.group}, 3m vs ACWI <Pct v={r.rel_r3m} /></span>)}
          </p>
        )}
        {!s.etfs.length ? (
          <p className="muted">Not covered yet. Run <code>/sector-etfs {s.key.includes(" ") ? `"${s.key}"` : s.key}</code> in Claude Code.</p>
        ) : (
          <>
            {pick && (
              <p>
                <b>Go-to:</b> <TickerLink symbol={pick.ticker} name={pick.name} nameFirst /> · {SCOPE[pick.scope]} · TER {ter(pick.ter)} ·{" "}
                <TaxBadge e={pick} year={v.tax_year} />
                {s.reason && <> · <span className="muted">{s.reason}</span></>}
                {s.recheck && <> <Badge kind="warn" title="The rule now ranks another fund first, and the record gave no reason to keep this one. Mark it for replacement to have the next /sector-etfs run pick again.">re-check</Badge></>}
                {" "}<span className="muted">Updated {date(s.updated)}.</span>
                <ReplaceControl s={s} f={f} />
              </p>
            )}
            {f.error && <div className="error">Couldn&apos;t save the mark: {f.error.message}</div>}
            <DataTable id={`sector-${sectorAnchor(s.key)}`} csvName={`sector-etfs-${sectorAnchor(s.key)}`} rows={s.etfs} cols={columns}
              rowKey={(e) => e.isin} />
          </>
        )}
      </div>
    </section>
  );
}

export function SectorEtfs() {
  const q = useQuery({ queryKey: ["sector-etfs"], queryFn: api.sectorEtfs, retry: false, staleTime: 5 * 60_000 });
  const guide = useGuideTree().data;
  const chapter = guide ? pageChapter(guide.page_links, "/sectoretfs") : null;
  const [all, setAll] = useState(false);
  useScrollToHash(q.data, useLocation().hash);
  return (
    <Loaded q={q} title="Sector ETFs">
      {(v) => {
        const label = Object.fromEntries(v.sectors.map((s) => [s.key, s.label]));
        const gics = v.sectors.filter((s) => !s.parent);
        const subs = (k: string) => v.sectors.filter((s) => s.parent === k);
        const shown = (s: SectorEtfSector) => all || s.etfs.length > 0;
        const covered = v.sectors.filter((s) => s.etfs.length).length;
        return (
          <>
            <PageHead title="Sector ETFs">
              The <b>go-to UCITS ETF</b> per sector for a Danish investor, and its peers: what to buy for exposure to a sector the
              rotation points at. The list comes from <code>/sector-etfs</code> in Claude Code
              {v.as_of ? <> (last run {date(v.as_of)}, {v.age_days} days ago; {covered} of {v.sectors.length} sectors)</> : null}; prices,
              the <Term k="tax_class">tax status</Term> and the rotation are today&apos;s. Funds are ranked by a rule: on the positive list
              first, then size, <Term k="ter">TER</Term>, tracking and accumulating. Returns are in DKK. Analysis, not advice.
              {chapter && <> <Link to={`/guide/${chapter}`}>About this page (guide)</Link>.</>}
            </PageHead>
            {v.stale && <div className="notes" role="alert">The record is {v.age_days} days old (more than {v.stale_days}): run <code>/sector-etfs</code> again
              to check costs, launches and closures.</div>}
            {v.run_scope.mode === "replace" && v.run_scope.marked.length > 0 && <div className="notes">
              {v.run_scope.marked.length === 1 ? "1 sector is" : `${v.run_scope.marked.length} sectors are`} marked for
              replacement ({v.run_scope.marked.map((k, i) => <span key={k}>{i > 0 && ", "}<a href={`#${sectorAnchor(k)}`}>{label[k] ?? k}</a></span>)}): run <code>/sector-etfs</code> in
              Claude Code to pick another go-to there. Nothing else changes.</div>}
            {!v.prices && <div className="notes">No price data yet: returns show as –. Download market data on the Data page.</div>}
            {v.problems.map((p) => <div key={p.id} className="error">Record {p.id}: {p.problem}</div>)}
            {!v.as_of ? (
              <div className="card">
                <p>No sector ETF list yet. Run <code>/sector-etfs</code> in Claude Code: it researches the UCITS candidates for each sector
                  (TER, size, tracking, the positive list), ranks them and picks a go-to for every sector by itself. If you don&apos;t want a
                  pick, mark it for replacement here and run <code>/sector-etfs</code> again.</p>
              </div>
            ) : (
              <>
                <nav className="jump">
                  {gics.filter(shown).map((s) => <a key={s.key} href={`#${sectorAnchor(s.key)}`}>{s.label}</a>)}
                  <label className="muted"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Show sectors not covered yet</label>
                </nav>
                {gics.map((s) => (
                  <div key={s.key}>
                    {shown(s) && <SectorCard s={s} v={v} />}
                    {subs(s.key).filter(shown).map((c) => <SectorCard key={c.key} s={c} v={v} parentLabel={label[s.key]} />)}
                  </div>
                ))}
              </>
            )}
            {v.note && <p className="muted">Note from the last run: {v.note}</p>}
          </>
        );
      }}
    </Loaded>
  );
}
