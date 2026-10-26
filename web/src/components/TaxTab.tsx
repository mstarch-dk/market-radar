import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Portfolio, type TaxAccount, type TaxPerson, type TaxUnknown } from "../api/client";
import { num } from "../lib/format";
import { Term } from "./Term";
import { TickerLink } from "./TickerLink";
import { Badge, Card, KV } from "./ui";

const CLASS_LABEL: Record<string, string> = {
  stock: "share", pl_fund: "positive-list fund", fund: "fund off the list", dk_distributing: "Danish distributing fund",
  unknown: "unknown",
};
const POOLS: [string, string][] = [
  ["ask_negative_tax", "ASK: negative tax"], ["pension_negative_tax", "Pension: negative tax"],
  ["listed_loss", "Listed-share loss"], ["negative_share_income", "Negative share income"],
];
const PERSON_POOLS = new Set(["listed_loss", "negative_share_income"]);

const dkk = (v: number | null | undefined) => v == null ? <span className="muted" title="Unknown: see the notes">–</span> : `${num(v, 0)} DKK`;

function Notes({ items, warn }: { items: string[]; warn?: boolean }) {
  if (!items.length) return null;
  return <ul className={`small ${warn ? "warn-text" : "muted"}`}>{items.map((n) => <li key={n}>{n}</li>)}</ul>;
}

/** A person's share income against the progression limit, the tax at each rate, capital income and what carries. */
function PersonCard({ p }: { p: TaxPerson }) {
  const si = p.share_income;
  const b = p.bases;
  const used = si ? Math.min(1, si.net / si.limit) : 0;
  return (
    <Card title={`${p.name}: frie midler`}>
      <p className="small muted">{p.accounts.join(", ")}{!p.complete && <> · <Badge kind="warn" title="Something is unknown or left out: see the notes">incomplete</Badge></>}</p>
      {si && (
        <div className="tax-bar" role="img" aria-label={`Share income ${num(si.net, 0)} of the limit ${num(si.limit, 0)} DKK`}>
          <i style={{ width: `${used * 100}%` }} />
          {si.net > si.limit && <i className="over" style={{ width: "100%" }} />}
        </div>
      )}
      <KV rows={[
        [<Term k="tax_share_income">Share income</Term>, si ? dkk(si.net) : <span className="muted">no tax: see the notes</span>,
          { hint: si ? `of the limit ${num(si.limit, 0)} DKK` : undefined }],
        ["Tax on it", si ? dkk(si.tax) : <span className="muted">–</span>,
          { hint: si ? `${num(si.tax_low, 0)} at the low rate, ${num(si.tax_high, 0)} above the limit` : undefined, hide: !si }],
        ["Realised gains / losses", b ? <>{dkk(b.realised_gains)} / {dkk(b.realised_losses)}</> : "–"],
        ["Dividends", b ? dkk(b.dividends) : "–"],
        [<Term k="tax_lager">Lager, positive-list funds</Term>, b ? dkk(b.pl_gains - b.pl_losses) : "–"],
        ["Listed losses carried out", si ? dkk(si.listed_loss_out) : "–", { hide: !si || si.listed_loss_out === 0 }],
        ["Negative share income carried out", si ? dkk(si.negative_out) : "–", { hide: !si || si.negative_out === 0 }],
        ["Capital income (funds off the list)", p.capital_income ? dkk(p.capital_income.base) : "–",
          { hint: p.capital_income?.tax != null ? `tax ${num(p.capital_income.tax, 0)} DKK`
            : p.capital_income?.base == null ? "unknown: see the notes" : "no tax shown: set the rate below" }],
      ]} />
      <Notes items={p.notes} />
    </Card>
  );
}

function AccountCard({ a }: { a: TaxAccount }) {
  const pool = a.pool;
  return (
    <Card title={a.name}>
      <p className="small muted">{a.kind === "ask" ? "Aktiesparekonto" : a.kind === "pension" ? "Pension" : a.kind === "frie_midler" ? "Frie midler" : "Other"}
        {(a.kind === "ask" || a.kind === "pension") && !a.complete && <> · <Badge kind="warn">no estimate</Badge></>}</p>
      {pool && (
        <KV rows={[
          ["Value at the start", dkk(pool.v_start)],
          ["Value at the end", dkk(pool.v_end)],
          ["Deposits / withdrawals", <>{dkk(pool.deposits)} / {dkk(pool.withdrawals)}</>],
          [<Term k="tax_pool">Return</Term>, dkk(pool.ret)],
          ["Negative tax carried in", dkk(pool.carried_in), { hide: !pool.carried_in }],
          ["Tax", dkk(pool.tax), { hint: pool.rate != null ? `${num(pool.rate * 100, 1)} % of the return` : undefined }],
          ["Negative tax carried out", dkk(pool.carried_out), { hide: !pool.carried_out }],
        ]} />
      )}
      {a.realised.length > 0 && (
        <table className="t"><thead><tr><th>Sold</th><th>Qty</th><th>Proceeds</th><th>Cost</th><th>Gain</th></tr></thead>
          <tbody>{a.realised.map((s) => (
            <tr key={`${s.symbol}${s.date}`}><td><TickerLink symbol={s.symbol} /> {s.date}</td><td>{num(s.quantity, 2)}</td>
              <td>{dkk(s.proceeds)}</td><td>{dkk(s.basis)}</td><td><b>{dkk(s.gain)}</b></td></tr>))}</tbody></table>
      )}
      {a.lager.length > 0 && (
        <table className="t"><thead><tr><th>Lager</th><th>Start</th><th>End</th><th>Bought</th><th>Sold</th><th>Gain</th></tr></thead>
          <tbody>{a.lager.map((x) => (
            <tr key={x.symbol}><td><TickerLink symbol={x.symbol} /> <span className="muted">{CLASS_LABEL[x.tax_class]}</span></td>
              <td>{dkk(x.v_start)}</td><td>{dkk(x.v_end)}</td><td>{dkk(x.buys)}</td><td>{dkk(x.sales)}</td><td><b>{dkk(x.gain)}</b></td></tr>))}</tbody></table>
      )}
      {a.dividends.length > 0 && (
        <p className="small">Dividends: {a.dividends.map((d, i) => <span key={`${d.symbol}${d.date}`}>{i > 0 && " · "}{d.symbol} {num(d.amount, 0)}</span>)}
          <span className="muted"> (as booked)</span></p>
      )}
      <Notes items={a.warnings} warn />
      <Notes items={a.notes} />
    </Card>
  );
}

/** A holding the radar can't classify, with the fix: its ISIN, or its class. */
function UnknownRow({ u, onSaved }: { u: TaxUnknown; onSaved: () => void }) {
  const [isin, setIsin] = useState("");
  const [cls, setCls] = useState("");
  const save = useMutation({
    mutationFn: () => api.setInstrument(u.symbol, { isin: isin || null, tax_class: (cls || null) as never }),
    onSuccess: onSaved,
  });
  return (
    <li>
      <b><TickerLink symbol={u.symbol} /></b> in {u.portfolio}, {dkk(u.value_dkk)}: {u.reason}{" "}
      <input value={isin} onChange={(e) => setIsin(e.target.value)} placeholder="ISIN" aria-label={`ISIN of ${u.symbol}`} size={14} />
      <select value={cls} onChange={(e) => setCls(e.target.value)} aria-label={`Class of ${u.symbol}`}>
        <option value="">class: from the ISIN</option>
        {["stock", "pl_fund", "fund", "dk_distributing"].map((c) => <option key={c} value={c}>{CLASS_LABEL[c]}</option>)}
      </select>
      <button type="button" className="btn small" disabled={(!isin && !cls) || save.isPending} onClick={() => save.mutate()}>Save</button>
      {save.isError && <span className="small neg"> {save.error.message}</span>}
    </li>
  );
}

/** Who owns which account, each person's rate on capital income, and the losses carried in. */
function TaxSettings({ portfolios, onSaved }: { portfolios: Portfolio[]; onSaved: () => void }) {
  const persons = useQuery({ queryKey: ["tax-persons"], queryFn: api.taxPersons });
  const openings = useQuery({ queryKey: ["tax-openings"], queryFn: api.taxOpenings });
  const done = () => { persons.refetch(); openings.refetch(); onSaved(); };
  const owner = useMutation({
    mutationFn: ({ p, person }: { p: Portfolio; person: number | null }) => api.editPortfolio(p.id, {
      name: p.name, mode: p.mode, kind: p.kind, dividends: p.dividends, note: p.note, archived: p.archived, tags: p.tags,
      tax_person_id: person }),
    onSuccess: done,
  });
  const rate = useMutation({
    mutationFn: ({ id, name, r }: { id: number; name: string; r: number | null }) =>
      api.editTaxPerson(id, { name, capital_income_rate: r }),
    onSuccess: done,
  });
  const [o, setO] = useState({ year: new Date().getFullYear(), pool: "listed_loss", amount: "", owner: "" });
  const add = useMutation({
    mutationFn: () => api.addTaxOpening({ year: o.year, pool: o.pool as never, amount: Number(o.amount),
      ...(PERSON_POOLS.has(o.pool) ? { tax_person_id: Number(o.owner) } : { portfolio_id: Number(o.owner) }) }),
    onSuccess: () => { setO({ ...o, amount: "" }); done(); },
  });
  const del = useMutation({ mutationFn: api.deleteTaxOpening, onSuccess: done });
  const real = portfolios.filter((p) => p.mode === "real");
  const owners = PERSON_POOLS.has(o.pool) ? (persons.data ?? []).map((p) => [p.id, p.name] as const)
    : real.filter((p) => p.kind === (o.pool.startsWith("ask") ? "ask" : "pension")).map((p) => [p.id, p.name] as const);
  return (
    <details className="card">
      <summary><b>Who owns what, rates and losses carried in</b></summary>
      <h3>Accounts</h3>
      <ul className="small">{real.map((p) => (
        <li key={p.id}>{p.name}{" "}
          <select value={p.tax_person_id ?? ""} aria-label={`Owner of ${p.name}`}
            onChange={(e) => owner.mutate({ p, person: e.target.value ? Number(e.target.value) : null })}>
            <option value="">nobody (no estimate)</option>
            {(persons.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select></li>))}</ul>
      <h3>Rate on capital income</h3>
      <p className="small muted">Your marginal rate on capital income depends on the rest of your income, so the radar
        doesn&apos;t guess it. Leave it empty and capital income is shown without a tax.</p>
      <ul className="small">{(persons.data ?? []).map((x) => (
        <li key={x.id}>{x.name}{" "}
          <input type="number" min={0} max={100} step={0.1} defaultValue={x.capital_income_rate != null ? x.capital_income_rate * 100 : ""}
            aria-label={`${x.name}'s rate on capital income, %`} onBlur={(e) => rate.mutate({ id: x.id, name: x.name,
              r: e.target.value === "" ? null : Number(e.target.value) / 100 })} /> %</li>))}</ul>
      <h3>Losses carried in</h3>
      <p className="small muted">What your årsopgørelse for the year before carries into a year. It replaces the radar&apos;s
        own count from that year, so your latest årsopgørelse is enough; enter 0 if nothing is carried.</p>
      <ul className="small">{(openings.data ?? []).map((x) => (
        <li key={x.id}>{x.year} {POOLS.find(([k]) => k === x.pool)?.[1]}: {num(x.amount, 0)} DKK{" "}
          <button type="button" className="linkish" onClick={() => del.mutate(x.id)}>remove</button></li>))}</ul>
      <div className="tab-bar small">
        <input type="number" value={o.year} aria-label="Carried into year" onChange={(e) => setO({ ...o, year: Number(e.target.value) })} />
        <select value={o.pool} aria-label="Pool" onChange={(e) => setO({ ...o, pool: e.target.value, owner: "" })}>
          {POOLS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select value={o.owner} aria-label="Whose" onChange={(e) => setO({ ...o, owner: e.target.value })}>
          <option value="">choose…</option>
          {owners.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <input type="number" min={0} value={o.amount} placeholder="DKK" aria-label="Amount in DKK" onChange={(e) => setO({ ...o, amount: e.target.value })} />
        <button type="button" className="btn small" disabled={!o.owner || o.amount === "" || !(Number(o.amount) >= 0) || add.isPending} onClick={() => add.mutate()}>Add</button>
        {add.isError && <span className="neg">{add.error.message}</span>}
      </div>
    </details>
  );
}

/** The tax estimate for an income year: per person (frie midler) and per account (ASK, pension), the holdings it
 *  can't classify with their fix, and its inputs. An estimate, not tax advice. */
export function TaxTab({ portfolios }: { portfolios: Portfolio[] }) {
  const qc = useQueryClient();
  const now = new Date().getFullYear();
  const first = Math.min(now, ...portfolios.filter((p) => p.first_date).map((p) => Number(p.first_date!.slice(0, 4))));
  const [year, setYear] = useState(now);
  const q = useQuery({ queryKey: ["tax", year], queryFn: () => api.tax(year), retry: false });
  const refresh = () => qc.invalidateQueries({ queryKey: ["tax"] });
  const v = q.data;
  return (
    <section className="group">
      <div className="tab-bar">
        <label className="small">Income year{" "}
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {Array.from({ length: now - first + 1 }, (_, i) => now - i).map((y) => <option key={y} value={y}>{y}</option>)}
          </select></label>
      </div>
      {q.isError && <p className="neg">{q.error.message}</p>}
      {v && (
        <>
          <div className="notes" role="note">
            <b>{v.disclaimer}</b>{" "}
            {v.rules ? <>Rules for {v.year} checked {v.rules.verified} against {v.rules.sources.map((s, i) => (
              <span key={s}>{i > 0 && ", "}<a href={s} target="_blank" rel="noreferrer">{new URL(s).hostname}</a></span>))}.</>
              : <span className="warn-text">No rules for {v.year}: the amounts are shown, no tax.</span>}
            {!v.complete_year && <> Values as of {v.asof}: the year isn&apos;t over.</>}
          </div>
          <Notes items={v.notes} />
          <div className="grid">
            {v.persons.map((p) => <PersonCard key={p.id} p={p} />)}
            {v.accounts.filter((a) => a.kind !== "frie_midler" || a.realised.length + a.lager.length + a.dividends.length > 0)
              .map((a) => <AccountCard key={a.id} a={a} />)}
          </div>
          {v.unknown.length > 0 && (
            <div className="card">
              <h2>Not in the estimate</h2>
              <p className="small muted">The radar can&apos;t tell how these are taxed, so they are left out rather than guessed.</p>
              <ul className="small">{v.unknown.map((u) => <UnknownRow key={`${u.symbol}${u.portfolio_id}`} u={u} onSaved={refresh} />)}</ul>
            </div>
          )}
        </>
      )}
      <TaxSettings portfolios={portfolios} onSaved={refresh} />
    </section>
  );
}
