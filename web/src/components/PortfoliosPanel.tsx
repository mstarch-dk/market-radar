import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Portfolio, type PortfolioIn, type PortfolioKind } from "../api/client";
import { PORTFOLIO_KEYS } from "./TxForm";
import { Badge } from "./ui";

export const KINDS: Record<PortfolioKind, [string, string]> = {
  ask: ["Aktiesparekonto", "17% lager on everything; stocks and positive-list funds only."],
  frie_midler: ["Frie midler", "Stocks taxed on realisation; positive-list funds lager (as share income)."],
  pension: ["Pension", "PAL tax (15.3% lager) on the return."],
  other: ["Other", ""],
};

const asInput = (p: Portfolio, patch: Partial<PortfolioIn> = {}): PortfolioIn => ({
  name: p.name, mode: p.mode, kind: p.kind, dividends: p.dividends, note: p.note ?? null, archived: p.archived, tags: p.tags, ...patch,
});

/** Your portfolios: real ones (your accounts, each with its tax kind) and virtual ones (simulations, A/B tests)
 *  that never count as yours unless you pick them. Tags group portfolios for comparisons. */
export function PortfoliosPanel() {
  const qc = useQueryClient();
  const { data: portfolios = [] } = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios });
  const [name, setName] = useState("");
  const [kind, setKind] = useState<PortfolioKind>("other");
  const [virtual, setVirtual] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const refresh = () => {
    [...PORTFOLIO_KEYS, ["portfolio-tags"]].forEach((k) => qc.invalidateQueries({ queryKey: k }));
  };
  const add = useMutation({ mutationFn: api.addPortfolio, onSuccess: () => { refresh(); setName(""); } });
  const edit = useMutation({ mutationFn: ({ id, p }: { id: number; p: PortfolioIn }) => api.editPortfolio(id, p), onSuccess: refresh });
  const tag = useMutation({ mutationFn: ({ id, tags }: { id: number; tags: string[] }) => api.setTags(id, tags), onSuccess: refresh });
  const del = useMutation({ mutationFn: api.deletePortfolio, onSuccess: refresh });
  const dflt = useMutation({ mutationFn: api.setDefaultPortfolio, onSuccess: refresh });
  const navigate = useNavigate();
  const fork = useMutation({
    mutationFn: ({ src, name, date }: { src: Portfolio; name: string; date: string }) =>
      api.forkPortfolio(src.id, { name, date, extra_cash_dkk: 0, tags: ["fork"] }),
    onSuccess: (p, v) => { refresh(); navigate(`/returns?pf=${v.src.id},${p.id}&from=${v.date}`); },
  });
  const error = [add, edit, tag, del, dflt, fork].find((m) => m.isError)?.error;
  const forkOf = (p: Portfolio) => {
    const date = window.prompt(`Copy "${p.name}" as it stood at the close of (YYYY-MM-DD):`, new Date().toISOString().slice(0, 10))?.trim();
    if (!date) return;
    const name = window.prompt("Name of the virtual copy:", `${p.name} (copy ${date})`)?.trim();
    if (name) fork.mutate({ src: p, name, date });
  };

  const rename = (p: Portfolio) => {
    const n = window.prompt(`Rename "${p.name}" to:`, p.name)?.trim();
    if (n && n !== p.name) edit.mutate({ id: p.id, p: asInput(p, { name: n }) });
  };
  const addTag = (p: Portfolio) => {
    const t = window.prompt(`Tag "${p.name}" with (e.g. momentum-a):`)?.trim();
    if (t) tag.mutate({ id: p.id, tags: [...p.tags, t] });
  };
  const remove = (p: Portfolio) => {
    const what = p.n_tx ? `${p.name} and its ${p.n_tx} rows (a backup is kept)` : p.name;
    if (window.confirm(`Delete ${what}?`)) del.mutate(p.id);
  };
  const shown = portfolios.filter((p) => showArchived || !p.archived);
  const nArchived = portfolios.filter((p) => p.archived).length;

  return (
    <div className="card accounts portfolios">
      <h2>Portfolios</h2>
      <p className="small muted">Real portfolios are your accounts and count as yours everywhere (holdings, briefs, the
        Claude skills). Virtual ones are for simulations and A/B tests: they only show when you pick them.</p>
      <ul>
        {shown.map((p) => (
          <li key={p.id} className={p.archived ? "muted" : ""}>
            <b>{p.name}</b>{" "}
            <Badge kind={p.mode === "virtual" ? "warn" : undefined}>{p.mode === "virtual" ? "virtual" : "real"}</Badge>{" "}
            <span className="muted small">{KINDS[p.kind][0]} · {p.n_tx} rows{p.is_default ? " · default" : ""}{p.archived ? " · archived" : ""}</span>
            {p.tags.map((t) => (
              <span key={t} className="tag-chip small">#{t}
                <button type="button" className="linkish" aria-label={`Remove tag ${t}`}
                  onClick={() => tag.mutate({ id: p.id, tags: p.tags.filter((x) => x !== t) })}>×</button>
              </span>
            ))}
            <span className="row-actions">
              <button type="button" className="linkish small" onClick={() => addTag(p)}>+ tag</button>
              <button type="button" className="linkish small" onClick={() => rename(p)}>rename</button>
              {p.n_tx > 0 && <button type="button" className="linkish small" onClick={() => forkOf(p)}
                title="A virtual copy at a day's close, to A/B-test changes against it">fork</button>}
              {p.mode === "real" && !p.archived && !p.is_default && (
                <button type="button" className="linkish small" onClick={() => dflt.mutate(p.id)}>make default</button>
              )}
              <button type="button" className="linkish small" onClick={() => edit.mutate({ id: p.id, p: asInput(p, { archived: !p.archived }) })}>
                {p.archived ? "unarchive" : "archive"}</button>
              {(p.mode === "virtual" || p.n_tx === 0) && (
                <button type="button" className="linkish small neg" onClick={() => remove(p)}>delete</button>
              )}
            </span>
            {(p.note || (p.mode === "real" && KINDS[p.kind][1])) && <div className="small muted">{p.note || KINDS[p.kind][1]}</div>}
          </li>
        ))}
      </ul>
      {nArchived > 0 && (
        <button type="button" className="linkish small" onClick={() => setShowArchived((v) => !v)}>
          {showArchived ? "hide" : "show"} {nArchived} archived</button>
      )}
      <form className="acct-add" onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) add.mutate({ name: name.trim(), kind, mode: virtual ? "virtual" : "real", dividends: "reinvested",
          note: null, archived: false, tags: virtual ? ["virtual"] : [] });
      }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New portfolio, e.g. Pension or Momentum test"
          aria-label="Portfolio name" />
        <select value={kind} onChange={(e) => setKind(e.target.value as PortfolioKind)} aria-label="Tax kind">
          {Object.entries(KINDS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <label className="small"><input type="checkbox" checked={virtual} onChange={(e) => setVirtual(e.target.checked)}
          aria-label="Virtual (a simulation or test, not yours)" /> virtual</label>
        <button type="submit" className="btn small" disabled={!name.trim() || add.isPending}>Add</button>
      </form>
      {error && <p className="small neg">{error.message}</p>}
    </div>
  );
}
