import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Portfolio, type PortfolioIn, type PortfolioKind } from "../api/client";
import { FeeScheduleEditor, feeSummary } from "./FeeSchedule";
import { PORTFOLIO_KEYS } from "./TxForm";

export const KINDS: Record<PortfolioKind, [string, string]> = {
  ask: ["Aktiesparekonto", "17% lager on everything; stocks and positive-list funds only."],
  frie_midler: ["Frie midler", "Stocks taxed on realisation; positive-list funds lager (as share income)."],
  pension: ["Pension", "PAL tax (15.3% lager) on the return."],
  other: ["Other", ""],
};

export const asInput = (p: Portfolio, patch: Partial<PortfolioIn> = {}): PortfolioIn => ({
  name: p.name, mode: p.mode, kind: p.kind, dividends: p.dividends, note: p.note ?? null, archived: p.archived, tags: p.tags,
  fee_schedule: p.fee_schedule ?? null, ...patch,
});

/** The edits a portfolio's row offers (rename, tags, archive, delete, fork, make default), shared by your accounts
 *  and the experiments. */
export function usePortfolioActions() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const refresh = () => {
    [...PORTFOLIO_KEYS, ["portfolio-tags"]].forEach((k) => qc.invalidateQueries({ queryKey: k }));
  };
  const edit = useMutation({ mutationFn: ({ id, p }: { id: number; p: PortfolioIn }) => api.editPortfolio(id, p), onSuccess: refresh });
  const tag = useMutation({ mutationFn: ({ id, tags }: { id: number; tags: string[] }) => api.setTags(id, tags), onSuccess: refresh });
  const del = useMutation({ mutationFn: api.deletePortfolio, onSuccess: refresh });
  const dflt = useMutation({ mutationFn: api.setDefaultPortfolio, onSuccess: refresh });
  const fork = useMutation({
    mutationFn: ({ src, name, date }: { src: Portfolio; name: string; date: string }) =>
      api.forkPortfolio(src.id, { name, date, extra_cash_dkk: 0, tags: ["fork"] }),
    onSuccess: (p) => { refresh(); navigate(`/experiments?pf=${p.id}`); },
  });
  return {
    error: [edit, tag, del, dflt, fork].find((m) => m.isError)?.error,
    refresh,
    save: (p: Portfolio, patch: Partial<PortfolioIn>, onSaved?: () => void) =>
      edit.mutate({ id: p.id, p: asInput(p, patch) }, { onSuccess: () => onSaved?.() }),
    saving: edit.isPending,
    rename: (p: Portfolio) => {
      const n = window.prompt(`Rename "${p.name}" to:`, p.name)?.trim();
      if (n && n !== p.name) edit.mutate({ id: p.id, p: asInput(p, { name: n }) });
    },
    addTag: (p: Portfolio) => {
      const t = window.prompt(`Tag "${p.name}" with (e.g. momentum-a):`)?.trim();
      if (t) tag.mutate({ id: p.id, tags: [...p.tags, t] });
    },
    removeTag: (p: Portfolio, t: string) => tag.mutate({ id: p.id, tags: p.tags.filter((x) => x !== t) }),
    toggleArchived: (p: Portfolio) => edit.mutate({ id: p.id, p: asInput(p, { archived: !p.archived }) }),
    remove: (p: Portfolio, onDone?: () => void) => {
      const what = p.n_tx ? `${p.name} and its ${p.n_tx} rows (a backup is kept)` : p.name;
      if (window.confirm(`Delete ${what}?`)) del.mutate(p.id, { onSuccess: () => onDone?.() });
    },
    makeDefault: (p: Portfolio) => dflt.mutate(p.id),
    fork: (p: Portfolio) => {
      const date = window.prompt(`Copy "${p.name}" as it stood at the close of (YYYY-MM-DD):`, new Date().toISOString().slice(0, 10))?.trim();
      if (!date) return;
      const name = window.prompt("Name of the experiment (a virtual copy):", `${p.name} (copy ${date})`)?.trim();
      if (name) fork.mutate({ src: p, name, date });
    },
  };
}

export function TagChips({ p, onRemove }: { p: Portfolio; onRemove?: (t: string) => void }) {
  return (
    <>
      {p.tags.map((t) => (
        <span key={t} className="tag-chip small">#{t}
          {onRemove && <button type="button" className="linkish" aria-label={`Remove tag ${t}`} onClick={() => onRemove(t)}>×</button>}
        </span>
      ))}
    </>
  );
}

/** Your accounts (the real portfolios), each with its tax kind and broker fee schedule. They count as yours
 *  everywhere (holdings, briefs, the Claude skills). Experiments (virtual portfolios) live on their own page. */
export function AccountsPanel() {
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const a = usePortfolioActions();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<PortfolioKind>("other");
  const [showArchived, setShowArchived] = useState(false);
  const [fees, setFees] = useState<number | null>(null);
  const add = useMutation({ mutationFn: api.addPortfolio, onSuccess: () => { a.refresh(); setName(""); } });
  const real = portfolios.filter((p) => p.mode === "real");
  const shown = real.filter((p) => showArchived || !p.archived);
  const nArchived = real.filter((p) => p.archived).length;
  const error = add.error ?? a.error;

  return (
    <div className="card accounts portfolios">
      <h2>Your accounts</h2>
      <p className="small muted">Each account is a real portfolio: its trades count as yours everywhere. The tax kind
        is noted for the briefs and skills; the fee schedule estimates a trade&apos;s commission while you type it.</p>
      <ul>
        {shown.map((p) => (
          <li key={p.id} className={p.archived ? "muted" : ""}>
            <b>{p.name}</b>{" "}
            <span className="muted small">{KINDS[p.kind][0]} · {p.n_tx} rows{p.is_default ? " · default" : ""}{p.archived ? " · archived" : ""}</span>
            <TagChips p={p} onRemove={(t) => a.removeTag(p, t)} />
            <span className="row-actions">
              <button type="button" className="linkish small" onClick={() => setFees(fees === p.id ? null : p.id)}
                aria-expanded={fees === p.id}>fees: {feeSummary(p.fee_schedule)}</button>
              <button type="button" className="linkish small" onClick={() => a.addTag(p)}>+ tag</button>
              <button type="button" className="linkish small" onClick={() => a.rename(p)}>rename</button>
              {p.n_tx > 0 && <button type="button" className="linkish small" onClick={() => a.fork(p)}
                title="A virtual copy at a day's close, on the Experiments page, to A/B-test changes against it">fork into an experiment</button>}
              {!p.archived && !p.is_default && (
                <button type="button" className="linkish small" onClick={() => a.makeDefault(p)}>make default</button>
              )}
              <button type="button" className="linkish small" onClick={() => a.toggleArchived(p)}>{p.archived ? "unarchive" : "archive"}</button>
              {p.n_tx === 0 && <button type="button" className="linkish small neg" onClick={() => a.remove(p)}>delete</button>}
            </span>
            {(p.note || KINDS[p.kind][1]) && <div className="small muted">{p.note || KINDS[p.kind][1]}</div>}
            {fees === p.id && <FeeScheduleEditor portfolio={p} onDone={() => setFees(null)} />}
          </li>
        ))}
      </ul>
      {nArchived > 0 && (
        <button type="button" className="linkish small" onClick={() => setShowArchived((v) => !v)}>
          {showArchived ? "hide" : "show"} {nArchived} archived</button>
      )}
      <form className="acct-add" onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) add.mutate({ name: name.trim(), kind, mode: "real", dividends: "reinvested", note: null, archived: false, tags: [] });
      }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New account, e.g. Pension at Nordnet"
          aria-label="Account name" />
        <select value={kind} onChange={(e) => setKind(e.target.value as PortfolioKind)} aria-label="Tax kind">
          {Object.entries(KINDS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <button type="submit" className="btn small" disabled={!name.trim() || add.isPending}>Add account</button>
      </form>
      {error && <p className="small neg">{error.message}</p>}
    </div>
  );
}
