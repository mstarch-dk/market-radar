import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type AbRebalance, type PerfStats, type Portfolio, type PortfolioKind, type TxRow } from "../api/client";
import { PageHead, Pct } from "../components/cells";
import { DataTable, type Col } from "../components/DataTable";
import { LineChart } from "../components/LineChart";
import { usePortfolioSel } from "../components/PortfolioPicker";
import { KINDS, TagChips, usePortfolioActions } from "../components/PortfoliosPanel";
import { describeTx, posCols, txCols } from "../components/portfolioTables";
import { Tabs, useTabParam } from "../components/Tabs";
import { PORTFOLIO_KEYS, TxForm } from "../components/TxForm";
import { Badge } from "../components/ui";
import { date, num } from "../lib/format";
import { formatSel, isDefaultSel, type PortfolioSel } from "../lib/portfolioSel";

type Kind = "ab" | "sim" | "fork" | "manual";
const KIND_LABEL: Record<Kind, string> = { ab: "A/B test", sim: "Simulation", fork: "Fork", manual: "Your own" };
const KIND_HELP: Record<Kind, string> = {
  ab: "One arm of the forward A/B test: rebalanced monthly from its picks; its rows are written by the test.",
  sim: "Written by a simulation run (sim picks, /hindsight, the exit study); a new run replaces its rows.",
  fork: "A copy of one of your accounts at a day's close, to try changes against it from there on.",
  manual: "A virtual portfolio you keep by hand: add its trades like an account's.",
};
const kindOf = (p: Portfolio): Kind => (p.strategy?.startsWith("ab-") ? "ab" : p.origin);
/** Rows a run writes (and a new run replaces) are read-only here. */
const readOnly = (p: Portfolio) => p.origin === "sim";

type Row = { p: Portfolio; kind: Kind; stats?: PerfStats | null };

const listCols: Col<Row>[] = [
  { key: "name", label: "Experiment", align: "l", sort: (r) => r.p.name, search: (r) => `${r.p.name} ${r.p.strategy ?? ""} ${r.p.tags.join(" ")}`,
    render: (r) => <span><Link to={`/experiments?pf=${r.p.id}`}>{r.p.name}</Link>{r.p.archived && <span className="muted small"> archived</span>}<TagChips p={r.p} /></span> },
  { key: "kind", label: "Kind", align: "l", sort: (r) => r.kind, filter: { kind: "enum", value: (r) => KIND_LABEL[r.kind] },
    render: (r) => <Badge title={KIND_HELP[r.kind]}>{KIND_LABEL[r.kind]}</Badge> },
  { key: "strategy", label: "Strategy", align: "l", sort: (r) => r.p.strategy, render: (r) => <span className="muted small">{r.p.strategy ?? "–"}</span>, hidden: true },
  { key: "start", label: "From", align: "l", sort: (r) => r.p.first_date, render: (r) => date(r.p.first_date) },
  { key: "value", label: "Value (DKK)", sort: (r) => r.stats?.value_dkk, render: (r) => num(r.stats?.value_dkk, 0) },
  { key: "twr", label: "Return", help: "twr", sort: (r) => r.stats?.twr_total, render: (r) => <Pct v={r.stats?.twr_total} />, heat: true },
  { key: "acwi", label: "ACWI", help: "acwi_twr", sort: (r) => r.stats?.acwi_twr_total, render: (r) => <Pct v={r.stats?.acwi_twr_total} /> },
  { key: "excess", label: "vs ACWI", help: "excess_twr", sort: (r) => r.stats?.excess_twr, render: (r) => <Pct v={r.stats?.excess_twr} />, heat: true },
  { key: "rows", label: "Rows", sort: (r) => r.p.n_tx, render: (r) => r.p.n_tx },
];

/** The forward A/B test in one card: its arms, the next rebalance and the link to compare them. */
function AbCard() {
  const ab = useQuery({ queryKey: ["abtest"], queryFn: api.abtest, retry: false });
  const d = ab.data;
  if (!d || !d.running) return null;
  const rows = d.comparison?.rows ?? [];
  return (
    <div className="card ab-card">
      <h2 className="plain">Forward A/B test: kvalitet+værdi vs momentum vs 50/50</h2>
      <p className="small muted">Three virtual baskets picked each month by their score and held to the next rebalance, against
        ACWI. {d.next_due && <>Next rebalance: <b>{date(d.next_due)}</b>.</>}</p>
      <ul className="ab-arms">
        {d.portfolios.map((a) => {
          const r = rows.find((x) => x.portfolio?.id === a.id);
          return (
            <li key={a.id}><Link to={`/experiments?pf=${a.id}`}><b>{a.label}</b></Link>{" "}
              <span className="small">return <Pct v={r?.stats?.twr_total} />, vs ACWI <Pct v={r?.stats?.excess_twr} /></span></li>
          );
        })}
      </ul>
      <p className="small"><Link to={`/returns?pf=${d.portfolios.map((a) => a.id).join(",")}`}>Compare them over time on Returns</Link></p>
      {d.notes.length > 0 && <ul className="small muted">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </div>
  );
}

function NewExperiment() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<PortfolioKind>("other");
  const add = useMutation({ mutationFn: api.addPortfolio, onSuccess: () => {
    setName(""); [...PORTFOLIO_KEYS, ["portfolio-tags"]].forEach((k) => qc.invalidateQueries({ queryKey: k }));
  } });
  return (
    <form className="acct-add" onSubmit={(e) => {
      e.preventDefault();
      if (name.trim()) add.mutate({ name: name.trim(), kind, mode: "virtual", dividends: "reinvested", note: null, archived: false, tags: ["virtual"] });
    }}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New virtual portfolio, e.g. Momentum test"
        aria-label="Experiment name" />
      <select value={kind} onChange={(e) => setKind(e.target.value as PortfolioKind)} aria-label="Taxed as">
        {Object.entries(KINDS).map(([k, [label]]) => <option key={k} value={k}>taxed as {label}</option>)}
      </select>
      <button type="submit" className="btn small" disabled={!name.trim() || add.isPending}>Add</button>
      {add.error && <span className="small neg">{add.error.message}</span>}
    </form>
  );
}

function ExperimentList({ portfolios }: { portfolios: Portfolio[] }) {
  const [showArchived, setShowArchived] = useState(false);
  const virtual = portfolios.filter((p) => p.mode === "virtual");
  const shown = virtual.filter((p) => showArchived || !p.archived);
  // each from its own start (a comparison would rebase them all to the latest start)
  const withRows = shown.filter((p) => p.n_tx > 0);
  const perf = useQueries({ queries: withRows.map((p) => ({ queryKey: ["performance", p.id, ""], retry: false,
    queryFn: () => api.performance(p.id), staleTime: 60_000 })) });
  const byId = new Map(withRows.map((p, i) => [p.id, perf[i]?.data?.stats ?? undefined]));
  const failed = perf.find((q) => q.isError)?.error;
  const rows: Row[] = shown.map((p) => ({ p, kind: kindOf(p), stats: byId.get(p.id) }));
  const nArchived = virtual.filter((p) => p.archived).length;
  return (
    <>
      <AbCard />
      <section className="group">
        {rows.length > 0
          ? <div className="card"><DataTable id="xp" csvName="experiments" rows={rows} cols={listCols} rowKey={(r) => String(r.p.id)} /></div>
          : <p className="note">No experiments yet. Fork one of your accounts (Portfolio › Accounts), start a simulation with{" "}
              <code>radar sim picks</code> or <code>/hindsight</code>, or add a virtual portfolio below.</p>}
        {failed && <p className="small neg">Couldn&apos;t work out every return: {failed.message}</p>}
        {nArchived > 0 && (
          <button type="button" className="linkish small" onClick={() => setShowArchived((v) => !v)}>
            {showArchived ? "hide" : "show"} {nArchived} archived</button>
        )}
      </section>
      <section className="group"><NewExperiment /></section>
    </>
  );
}

const DETAIL_TABS = ["holdings", "trades", "rebalances", "returns"] as const;

function Rebalances({ rows }: { rows: AbRebalance[] }) {
  if (!rows.length) return <p className="note">No rebalances recorded yet.</p>;
  return (
    <div className="card">
      <table className="t">
        <thead><tr><th className="l">Picked</th><th className="l">Basket</th><th>Turnover</th></tr></thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.date}>
              <td className="l">{date(r.date)}</td>
              <td className="l small">{r.picks.map((p) => `${p.ticker} ${num(p.weight * 100, 0)}%`).join(" · ")}</td>
              <td><Pct v={r.turnover} digits={0} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One experiment (or a set of them, from an old link): its header, then holdings, trades, rebalances and returns. */
function ExperimentView({ sel, portfolios, onBack }: { sel: PortfolioSel; portfolios: Portfolio[]; onBack: () => void }) {
  const qc = useQueryClient();
  const key = formatSel(sel);
  const ids = "ids" in sel ? sel.ids : [];
  const one = ids.length === 1 && "tags" in sel && sel.tags.length === 0 ? portfolios.find((p) => p.id === ids[0]) : undefined;
  const members = "ids" in sel ? portfolios.filter((p) => ids.includes(p.id) || p.tags.some((t) => sel.tags.includes(t))) : [];
  const kind = one ? kindOf(one) : null;
  const a = usePortfolioActions();
  const pos = useQuery({ queryKey: ["positions", key], queryFn: () => api.positions(sel) });
  const tx = useQuery({ queryKey: ["transactions", key], queryFn: () => api.transactions(sel) });
  const cmp = useQuery({ queryKey: ["comparison", key, "experiment"], queryFn: () => api.compare("ids" in sel ? sel : undefined), retry: false });
  const ab = useQuery({ queryKey: ["abtest"], queryFn: api.abtest, enabled: kind === "ab", retry: false });
  const runs = useQuery({ queryKey: ["sim-runs", one?.id], queryFn: () => api.simRuns(one!.id), enabled: one?.origin === "sim" });
  const tabs = kind === "ab" ? DETAIL_TABS : DETAIL_TABS.filter((t) => t !== "rebalances");
  const [tab, setTab] = useTabParam(tabs, "holdings");
  const [form, setForm] = useState<{ edit: TxRow | null } | null>(null);
  const [undo, setUndo] = useState<TxRow | null>(null);
  const refresh = () => PORTFOLIO_KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const del = useMutation({ mutationFn: api.deleteTx, onSuccess: (row) => { setUndo(row); refresh(); } });
  const restore = useMutation({ mutationFn: api.restoreTx, onSuccess: () => { setUndo(null); refresh(); } });
  const editable = !!one && !readOnly(one);
  const run = runs.data?.at(-1);
  const parent = one?.parent_id ? portfolios.find((p) => p.id === one.parent_id) : undefined;
  const p = pos.data;
  const stats = cmp.data?.rows.length === 1 ? cmp.data.rows[0]!.stats : null;

  return (
    <>
      <p className="crumb small muted"><button type="button" className="linkish" onClick={onBack}>Experiments</button> › {one?.name ?? key}</p>
      <div className="page-head">
        <h1>{one?.name ?? `${members.length} experiments`} {kind && <Badge title={KIND_HELP[kind]}>{KIND_LABEL[kind]}</Badge>}
          {one?.archived && <Badge>archived</Badge>}</h1>
        {one && (
          <div className="note">
            {KIND_HELP[kindOf(one)]}{" "}
            {one.strategy && <>Strategy <code>{one.strategy}</code>. </>}
            {parent && <>Forked from <Link to={`/portfolio?pf=${parent.id}`}>{parent.name}</Link>{one.forked_at && <> at the close of {date(one.forked_at)}</>}. </>}
            {one.first_date && <>Rows from {date(one.first_date)} to {date(one.last_date)}. </>}
            {run && <>Last run {run.at.replace("T", " ").slice(0, 16)} ({run.status}, {run.rows} rows{run.data_asof ? `, data as of ${date(run.data_asof)}` : ""}). </>}
            Taxed as {KINDS[one.kind][0]}.
          </div>
        )}
        {!one && <div className="note">{members.map((m) => m.name).join(", ") || "Nothing matches this link."}</div>}
        {one && (
          <div className="head-actions small">
            <TagChips p={one} onRemove={(t) => a.removeTag(one, t)} />
            <button type="button" className="linkish small" onClick={() => a.addTag(one)}>+ tag</button>
            <button type="button" className="linkish small" onClick={() => a.rename(one)}>rename</button>
            <button type="button" className="linkish small" onClick={() => a.toggleArchived(one)}>{one.archived ? "unarchive" : "archive"}</button>
            <button type="button" className="linkish small neg" onClick={() => a.remove(one, onBack)}>delete</button>
          </div>
        )}
        {a.error && <p className="small neg">{a.error.message}</p>}
      </div>
      {stats && (
        <p className="small xp-stats">Value <b>{num(stats.value_dkk, 0)} DKK</b> · return <Pct v={stats.twr_total} /> · ACWI{" "}
          <Pct v={stats.acwi_twr_total} /> · vs ACWI <b><Pct v={stats.excess_twr} /></b>{stats.start && <> · since {date(stats.start)}</>}</p>
      )}

      <Tabs label="Experiment" value={tab} onChange={setTab} tabs={tabs.map((t) => [t, {
        holdings: <>Holdings{p && <span className="muted"> {p.total.length}</span>}</>,
        trades: <>Trades{tx.data && <span className="muted"> {tx.data.length}</span>}</>,
        rebalances: "Rebalances",
        returns: "Returns",
      }[t]])} />

      {tab === "holdings" && (
        <section className="group">
          {p && p.total.length === 0 && <p className="note">Nothing held{one?.n_tx ? " right now" : " yet"}.</p>}
          {p && p.total.length > 0 && (
            <div className="card"><DataTable id="xh" csvName="holdings" rows={members.length > 1 ? p.by_portfolio : p.total}
              cols={posCols(members.length > 1)} rowKey={(r) => `${r.symbol}|${r.portfolio_id ?? ""}`} /></div>
          )}
          {p && p.cash.filter((c) => c.funding === "ledger").length > 0 && (
            <p className="small">Cash: {p.cash.filter((c) => c.funding === "ledger").map((c, i) => (
              <span key={c.portfolio_id}>{i > 0 && " · "}{members.length > 1 && `${c.portfolio} `}<b>{c.cash_dkk != null ? `${num(c.cash_dkk, 0)} DKK` : "unknown"}</b></span>
            ))}</p>
          )}
        </section>
      )}

      {tab === "trades" && (
        <section className="group">
          {editable && (
            <div className="tab-bar">
              <button type="button" className="btn primary" onClick={() => setForm({ edit: null })}>Add a trade</button>
              <a className="btn" href={api.exportUrl(sel)}>Download (CSV)</a>
            </div>
          )}
          {one && !editable && <p className="small muted">Written by a run: a new run replaces these rows, so they can&apos;t be edited here.</p>}
          {undo && (
            <div className="notes undo" role="status">
              Deleted the {describeTx(undo)}.{" "}
              <button type="button" className="btn small" onClick={() => restore.mutate(undo)} disabled={restore.isPending}>Undo</button>
            </div>
          )}
          {form && one && <TxForm key={form.edit?.id ?? "new"} edit={form.edit} portfolio={one.id} lock onDone={() => setForm(null)} />}
          {tx.data && tx.data.length > 0 && (
            <div className="card"><DataTable id="xt" csvName="trades" rows={[...tx.data].reverse()} rowKey={(t) => String(t.id)}
              cols={txCols({ showPortfolio: members.length > 1, ...(editable ? { onEdit: (t: TxRow) => setForm({ edit: t }),
                onDelete: (t: TxRow) => del.mutate(t.id), busy: del.isPending } : {}) })} /></div>
          )}
        </section>
      )}

      {tab === "rebalances" && kind === "ab" && one && (
        <section className="group"><Rebalances rows={(ab.data?.rebalances ?? []).filter((r) => r.kind === one.strategy)} /></section>
      )}

      {tab === "returns" && (
        <section className="group">
          {cmp.isError && <p className="small neg">{cmp.error.message}</p>}
          {cmp.data && cmp.data.rows.length > 0 && <LineChart chart={cmp.data.chart} height={300} />}
          {cmp.data && cmp.data.rows.length === 0 && <p className="note">No returns yet: there are no rows to work them out from.</p>}
          {cmp.data && (
            <ul className="small muted perf-notes">
              {cmp.data.rows.flatMap((r) => [...r.notes, ...r.missing].map((n) => <li key={r.label + n}>{n}</li>))}
            </ul>
          )}
          <p className="small"><Link to={`/returns?pf=${key}`}>Open on Returns</Link> to compare with your accounts or other experiments.</p>
        </section>
      )}
    </>
  );
}

/** Virtual portfolios: the A/B test's arms, simulations, forks of your accounts and your own test portfolios. They
 *  never count as yours; open one to see what it holds, its trades and its return against ACWI. */
export function Experiments() {
  const [sel] = usePortfolioSel();
  const navigate = useNavigate();
  const { data: portfolios } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const list = isDefaultSel(sel) || ("scope" in sel);
  return (
    <>
      {list && (
        <PageHead title="Experiments">
          Virtual portfolios: the forward A/B test, simulations, forks of your accounts and test portfolios you keep by
          hand. They never count as yours (holdings, briefs, the skills); open one to see what it holds, its trades and
          its return against ACWI. Analysis, not advice.
        </PageHead>
      )}
      {portfolios && (list
        ? <ExperimentList portfolios={portfolios} />
        : <ExperimentView key={formatSel(sel)} sel={sel} portfolios={portfolios} onBack={() => navigate("/experiments")} />)}
    </>
  );
}
