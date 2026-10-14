import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Account } from "../api/client";

const KINDS: Record<Account["kind"], [string, string]> = {
  ask: ["Aktiesparekonto", "17% lager on everything; stocks and positive-list funds only."],
  frie_midler: ["Frie midler", "Stocks taxed on realisation; positive-list funds lager (as share income)."],
  pension: ["Pension", "PAL tax (15.3% lager) on the return."],
  other: ["Other", ""],
};

/** Your accounts (e.g. ASK and frie midler) with a one-line tax hint each. Renaming moves its trades along. */
export function AccountsPanel() {
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: api.accounts });
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Account["kind"]>("other");
  const save = useMutation({
    mutationFn: api.saveAccount,
    onSuccess: (a) => { qc.setQueryData(["accounts"], a); qc.invalidateQueries({ queryKey: ["transactions"] }); setName(""); },
  });
  const rename = (a: Account) => {
    const n = window.prompt(`Rename "${a.name}" to:`, a.name)?.trim();
    if (n && n !== a.name) save.mutate({ name: n, kind: a.kind, note: a.note ?? null, old_name: a.name });
  };
  return (
    <div className="card accounts">
      <h2>Accounts</h2>
      <ul>
        {accounts.map((a) => (
          <li key={a.name}>
            <b>{a.name}</b> <span className="muted small">{KINDS[a.kind][0]}</span>
            <button type="button" className="linkish small" onClick={() => rename(a)}>rename</button>
            {KINDS[a.kind][1] && <div className="small muted">{KINDS[a.kind][1]}</div>}
          </li>
        ))}
      </ul>
      <form className="acct-add" onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate({ name: name.trim(), kind, note: null, old_name: null }); }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New account, e.g. Pension" aria-label="Account name" />
        <select value={kind} onChange={(e) => setKind(e.target.value as Account["kind"])} aria-label="Account kind">
          {Object.entries(KINDS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <button type="submit" className="btn small" disabled={!name.trim() || save.isPending}>Add</button>
      </form>
      {save.isError && <p className="small neg">{save.error.message}</p>}
    </div>
  );
}
