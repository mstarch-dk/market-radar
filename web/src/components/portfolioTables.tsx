import type { PositionRow, TxRow } from "../api/client";
import { date, num, price } from "../lib/format";
import { Pct } from "./cells";
import type { Col } from "./DataTable";
import { TickerLink } from "./TickerLink";

// the positions and transactions tables, shared by the Portfolio page (your accounts) and Experiments

export const TYPE_LABEL: Record<TxRow["type"], string> = { BUY: "Buy", SELL: "Sell", DEPOSIT: "Deposit", WITHDRAW: "Withdrawal",
  DIVIDEND: "Dividend", FEE: "Fee", INTEREST: "Interest" };
const IN_TYPES = new Set(["BUY", "DEPOSIT", "DIVIDEND", "INTEREST"]);

export const describeTx = (t: TxRow) => t.quantity != null
  ? `${TYPE_LABEL[t.type].toLowerCase()} of ${t.quantity} ${t.symbol} on ${t.date}`
  : `${TYPE_LABEL[t.type].toLowerCase()} of ${t.amount} ${t.currency ?? "DKK"} on ${t.date}`;

export const posCols = (byPortfolio: boolean, portfolioLabel = "Portfolio"): Col<PositionRow>[] => [
  { key: "symbol", label: "Holding", align: "l", sort: (p) => p.name ?? p.symbol, search: (p) => `${p.symbol} ${p.name ?? ""}`,
    csv: (p) => p.symbol, csvHeader: "Ticker", render: (p) => <TickerLink symbol={p.symbol} name={p.name} nameFirst marker={false} /> },
  ...(byPortfolio ? [{ key: "portfolio", label: portfolioLabel, align: "l" as const, sort: (p: PositionRow) => p.portfolio,
    filter: { kind: "enum" as const }, render: (p: PositionRow) => p.portfolio ?? <span className="muted">–</span> }] : []),
  { key: "qty", label: "Shares", sort: (p) => p.quantity, render: (p) => num(p.quantity, p.quantity % 1 ? 4 : 0) },
  { key: "avg", label: "Average cost", sort: (p) => p.avg_price, render: (p) => price(p.avg_price, p.currency) },
  { key: "last", label: "Last", sort: (p) => p.last, render: (p) => price(p.last, p.currency) },
  { key: "value", label: "Value", sort: (p) => p.value, render: (p) => price(p.value, p.currency) },
  { key: "unreal", label: "Unrealised", sort: (p) => p.unrealized, render: (p) => <Pct v={p.unrealized} />, heat: true },
  { key: "first", label: "Since", sort: (p) => p.first_trade, render: (p) => date(p.first_trade) },
];

/** The transactions table; Edit/Delete only when handlers are given (a simulation's rows are read-only). */
export const txCols = ({ portfolioLabel = "Portfolio", showPortfolio = true, onEdit, onDelete, busy }: {
  portfolioLabel?: string;
  showPortfolio?: boolean;
  onEdit?: (t: TxRow) => void;
  onDelete?: (t: TxRow) => void;
  busy?: boolean;
} = {}): Col<TxRow>[] => [
  { key: "date", label: "Date", align: "l", sort: (t) => t.date, render: (t) => date(t.date) },
  { key: "type", label: "Type", align: "l", sort: (t) => t.type, filter: { kind: "enum" },
    render: (t) => <span className={IN_TYPES.has(t.type) ? "pos" : "neg"}>{TYPE_LABEL[t.type]}</span> },
  { key: "symbol", label: "Ticker", align: "l", sort: (t) => t.symbol, search: (t) => `${t.symbol ?? ""} ${t.note ?? ""}`,
    filter: { kind: "enum" }, render: (t) => (t.symbol ? <TickerLink symbol={t.symbol} marker={false} /> : <span className="muted">–</span>) },
  { key: "qty", label: "Shares", sort: (t) => t.quantity,
    render: (t) => (t.quantity != null ? num(t.quantity, t.quantity % 1 ? 4 : 0) : <span className="muted">–</span>) },
  { key: "price", label: "Price", sort: (t) => t.price ?? t.amount,
    render: (t) => (t.price != null ? num(t.price, 2) : t.amount != null ? `${num(t.amount, 2)} ${t.currency ?? "DKK"}` : "–") },
  { key: "fee", label: "Fee", sort: (t) => t.fee, render: (t) => (t.fee ? num(t.fee, 2) : <span className="muted">–</span>) },
  ...(showPortfolio ? [{ key: "portfolio", label: portfolioLabel, align: "l" as const, sort: (t: TxRow) => t.portfolio,
    filter: { kind: "enum" as const }, render: (t: TxRow) => t.portfolio }] : []),
  { key: "source", label: "From", align: "l", sort: (t) => t.source, filter: { kind: "enum" }, render: (t) => <span className="muted small">{t.source}</span> },
  { key: "note", label: "Note", align: "l", render: (t) => <span className="muted small">{t.note}</span>, hidden: true },
  ...(onEdit || onDelete ? [{ key: "actions", label: "", csv: false as const, render: (t: TxRow) => (
    <span className="row-actions">
      {onEdit && <button type="button" className="linkish small" onClick={() => onEdit(t)}>Edit</button>}
      {onDelete && (
        <button type="button" className="linkish small neg" disabled={busy}
          onClick={() => { if (window.confirm(`Delete this ${describeTx(t)}?`)) onDelete(t); }}>
          Delete
        </button>
      )}
    </span>
  ) }] : []),
];
