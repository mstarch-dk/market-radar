import type { components } from "./schema";
import { selQuery, type PortfolioSel } from "../lib/portfolioSel";

type S = components["schemas"];
export type Profile = S["Profile"];
export type Series = S["Series"];
export type SearchHit = S["SearchHit"];
export type AppContext = S["AppContext"];
export type Windows = S["Windows"];
export type SectionMeta = Pick<S["Price"], "status" | "source" | "asof">;
export type RegimeView = S["RegimeView"];
export type Quadrant = S["Rotation"]["quadrant"];
export type RegimeLabel = S["Overall"]["label"];
export type Outdated = S["Outdated"];
export type RotationView = S["RotationView"];
export type RotationGroup = S["RotationGroup"];
export type RotationRow = S["RotationRow"];
export type RrgTrail = S["RrgTrail"];
export type MomentumView = S["MomentumView"];
export type MomentumRow = S["MomentumRow"];
export type DiscoveryView = S["DiscoveryView"];
export type DiscoveryMarket = S["DiscoveryMarket"];
export type DiscoveryRow = S["DiscoveryRow"];
export type ViewsPage = S["ViewsPage"];
export type ViewRow = S["ViewRow"];
export type ViewIn = S["ViewIn"];
export type ViewTemplate = S["ViewTemplate"];
export type ViewsCatalogue = S["ViewsCatalogue"];
export type ViewAlignment = S["ViewAlignment"];
export type AlignCompact = S["AlignCompact"];
export type PositioningView = S["PositioningView"];
export type VoteOption = S["VoteOption"];
export type SecContact = S["SecContact"];
export type QualityView = S["QualityView"];
export type QualityRow = S["QualityRow"];
export type QualityCard = S["QualityCard"];
export type AbTest = S["AbTest"];
export type AbStartIn = S["AbStartIn"];
export type CoverageView = S["CoverageView"];
export type LineChartData = S["LineChart"];
export type MeView = S["MeView"];
export type MyRow = S["MyRow"];
export type WatchState = S["WatchState"];
export type TickerSummary = S["TickerSummary"];
export type UpdateStatus = S["UpdateStatus"];
export type ImportResult = S["ImportResult"];
export type TxIn = S["TxIn"];
export type TxRow = S["TxRow"];
export type TxCheck = S["TxCheck"];
export type TxResult = S["TxResult"];
export type Issue = S["Issue"];
export type PositionsView = S["PositionsView"];
export type PositionRow = S["PositionRow"];
export type PriceCheck = S["PriceCheck"];
export type Portfolio = S["Portfolio"];
export type PortfolioIn = S["PortfolioIn"];
export type PortfolioKind = Portfolio["kind"];
export type TagCount = S["TagCount"];
export type FeeRule = S["FeeRule"];
export type FeeSchedule = S["FeeSchedule"];
export type FeePreset = S["FeePreset"];
export type FeeEstimate = S["FeeEstimate"];
export type SimRun = S["SimRun"];
export type AbRebalance = S["AbRebalance"];
export type MoveIn = S["MoveIn"];
export type ForkIn = S["ForkIn"];
export type Comparison = S["Comparison"];
export type CompareRow = S["CompareRow"];
export type PerformanceView = S["Performance"];
export type PerfStats = S["PerfStats"];
export type XrayView = S["XrayView"];
export type AgendaView = S["AgendaView"];
export type AgendaItem = S["AgendaItem"];
export type EvidenceView = S["EvidenceView"];
export type AttributionView = S["AttributionView"];
export type TaxYearView = S["TaxYearView"];
export type TaxPerson = S["TaxPerson"];
export type TaxAccount = S["TaxAccount"];
export type TaxUnknown = S["TaxUnknown"];
export type TaxPersonView = S["TaxPersonView"];
export type TaxPersonIn = S["TaxPersonIn"];
export type InstrumentIn = S["InstrumentIn"];
export type InstrumentView = S["InstrumentView"];
export type TaxOpeningIn = S["TaxOpeningIn"];
export type TaxOpeningView = S["TaxOpeningView"];
export type ReportHead = S["ReportHead"];
export type ScoreCard = S["ScoreCard"];
export type ScoreRow = S["ScoreRow"];
export type LongrunCard = S["LongrunCard"];
export type LongrunRow = S["LongrunRow"];
export type ForwardGroup = S["ForwardGroup"];
export type ImportPreview = S["ImportPreview"];
export type ImportRow = S["ImportRow"];
export type ImportRecord = S["ImportRecord"];
export type ImportCommitResult = S["ImportCommitResult"];
export type Preset = S["Preset"];
export type OpsSummary = S["OpsSummary"];
export type OpsRow = S["OpsRow"];
export type OpsEvent = S["OpsEvent"];
export type OpsJob = S["OpsJob"];
export type OpsJobDetail = S["OpsJobDetail"];
export type OpsRequest = S["OpsRequest"];
export type DoctorCheck = S["DoctorCheck"];
export type GuideTree = S["GuideTree"];
export type GuideChapter = S["GuideChapter"];
export type GuideHit = S["GuideHit"];
export type NotebookListing = S["NotebookListing"];
export type NotebookEntry = S["NotebookEntry"];
export type NotebookDocument = S["NotebookDocument"];
export type HomeStatus = S["HomeStatus"];
export type LegacyFound = S["LegacyFound"];
export type SetupIn = S["SetupIn"];
export type SetupResult = S["SetupResult"];
export type DataHome = S["DataHome"];
export type DataFolder = S["DataFolder"];
export type BackupRow = S["BackupRow"];
export type RestoreResult = S["RestoreResult"];
export type UpdateCheck = S["UpdateCheck"];
export type ImportParams = { filename: string; preset?: string; portfolio?: number; mapping?: Record<string, string>;
  symbols?: Record<string, string>; confirm?: boolean };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** validation issues sent with a 422 (portfolio editor) */
    public issues: Issue[] = [],
  ) {
    super(message);
  }
}

async function get<T>(url: string, method = "GET", body?: BodyInit, contentType?: string): Promise<T> {
  const r = await fetch(url, { method, body, headers: contentType ? { "Content-Type": contentType } : undefined });
  if (!r.ok) {
    let detail = r.statusText;
    let issues: Issue[] = [];
    try {
      // every error is {"detail": {"message", "issues"}} (api/app.py, one handler)
      const body = (await r.json()) as { detail?: { message?: string; issues?: Issue[] } };
      detail = body.detail?.message || detail;
      issues = body.detail?.issues ?? [];
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, detail, issues);
  }
  return (await r.json()) as T;
}

const enc = encodeURIComponent;
const withSel = (url: string, sel?: PortfolioSel) => {
  const q = sel ? selQuery(sel) : "";
  return q ? `${url}${url.includes("?") ? "&" : "?"}${q}` : url;
};
const json = (v: unknown) => JSON.stringify(v);

function importQuery(p: ImportParams): string {
  const q = new URLSearchParams({ filename: p.filename });
  if (p.preset) q.set("preset", p.preset);
  if (p.portfolio != null) q.set("portfolio", String(p.portfolio));
  if (p.mapping) q.set("mapping", JSON.stringify(p.mapping));
  if (p.symbols && Object.keys(p.symbols).length) q.set("symbols", JSON.stringify(p.symbols));
  if (p.confirm) q.set("confirm", "true");
  return q.toString();
}

export const api = {
  profile: (symbol: string, refresh = false) =>
    get<Profile>(`/api/ticker/${enc(symbol)}${refresh ? "?refresh=true" : ""}`),
  series: (symbol: string, days = 756) => get<Series>(`/api/ticker/${enc(symbol)}/series?days=${days}`),
  search: (q: string) => get<SearchHit[]>(`/api/search?q=${enc(q)}`),
  context: () => get<AppContext>("/api/context"),
  regime: () => get<RegimeView>("/api/regime"),
  rotation: () => get<RotationView>("/api/rotation"),
  momentum: () => get<MomentumView>("/api/momentum"),
  quality: () => get<QualityView>("/api/quality"),
  abtest: () => get<AbTest>("/api/abtest"),
  startAbtest: (b: AbStartIn) => get<AbTest>("/api/abtest", "POST", json(b), "application/json"),
  positioning: () => get<PositioningView>("/api/positioning"),
  setRegimeVotes: (votes: Record<string, boolean>) =>
    get<VoteOption[]>("/api/settings/regime-votes", "PUT", JSON.stringify({ votes }), "application/json"),
  coverage: () => get<CoverageView>("/api/coverage"),
  guideTree: () => get<GuideTree>("/api/guide"),
  notebook: () => get<NotebookListing>("/api/notebook"),
  notebookDocument: (kind: string, name: string) => get<NotebookDocument>(`/api/notebook/${enc(kind)}/${enc(name)}`),
  guideChapter: (book: string, slug: string) => get<GuideChapter>(`/api/guide/${enc(book)}/${enc(slug)}`),
  guideSearch: (q: string) => get<GuideHit[]>(`/api/guide/search?q=${enc(q)}`),
  opsSummary: (days: number) => get<OpsSummary>(`/api/ops/summary?days=${days}`),
  opsEvents: () => get<OpsEvent[]>("/api/ops/events?limit=500"),
  opsRequests: () => get<OpsRequest[]>("/api/ops/requests?limit=300"),
  opsJobs: () => get<OpsJob[]>("/api/ops/jobs"),
  opsJob: (id: number) => get<OpsJobDetail>(`/api/ops/jobs/${id}`),
  opsDoctor: (probe: boolean) => get<DoctorCheck[]>(`/api/ops/doctor?probe=${probe}`),
  clearCooldown: (host: string) => get<boolean>(`/api/ops/cooldown/${enc(host)}`, "DELETE"),
  discover: () => get<DiscoveryView>("/api/discover"),
  discoverStatus: () => get<UpdateStatus>("/api/discover/scan"),
  startDiscover: () => get<UpdateStatus>("/api/discover/scan", "POST"),
  views: () => get<ViewsPage>("/api/views"),
  addView: (v: ViewIn) => get<ViewsPage>("/api/views", "POST", JSON.stringify(v), "application/json"),
  editView: (id: number, v: ViewIn) => get<ViewsPage>(`/api/views/${id}`, "PUT", JSON.stringify(v), "application/json"),
  deleteView: (id: number) => get<ViewRow>(`/api/views/${id}`, "DELETE"),
  restoreView: (v: ViewRow) => get<ViewsPage>("/api/views/restore", "POST", JSON.stringify(v), "application/json"),
  alignViews: (tickers: string[], store: "main" | "discovery") =>
    get<Record<string, AlignCompact>>("/api/views/align", "POST", JSON.stringify({ tickers, store }), "application/json"),
  me: (sel?: PortfolioSel) => get<MeView>(withSel("/api/me", sel)),
  tickers: () => get<TickerSummary[]>("/api/tickers"),
  updateStatus: () => get<UpdateStatus>("/api/update"),
  startUpdate: () => get<UpdateStatus>("/api/update", "POST"),
  reportStatus: () => get<UpdateStatus>("/api/report"),
  startReport: () => get<UpdateStatus>("/api/report", "POST"),
  importPortfolio: (csv: string) => get<ImportResult>("/api/import", "POST", csv, "text/csv"),
  transactions: (sel?: PortfolioSel) => get<TxRow[]>(withSel("/api/portfolio/transactions", sel)),
  validateTx: (tx: TxIn, id?: number) =>
    get<TxCheck>(`/api/portfolio/validate${id ? `?id=${id}` : ""}`, "POST", JSON.stringify(tx), "application/json"),
  addTx: (tx: TxIn) => get<TxResult>("/api/portfolio/transactions", "POST", JSON.stringify(tx), "application/json"),
  editTx: (id: number, tx: TxIn) => get<TxResult>(`/api/portfolio/transactions/${id}`, "PUT", JSON.stringify(tx), "application/json"),
  deleteTx: (id: number) => get<TxRow>(`/api/portfolio/transactions/${id}`, "DELETE"),
  restoreTx: (row: TxRow) => get<TxRow>("/api/portfolio/transactions/restore", "POST", JSON.stringify(row), "application/json"),
  positions: (sel?: PortfolioSel) => get<PositionsView>(withSel("/api/portfolio/positions", sel)),
  exportUrl: (sel?: PortfolioSel) => withSel("/api/portfolio/export.csv", sel),
  xray: (sel?: PortfolioSel) => get<XrayView>(withSel("/api/xray", sel)),
  calendar: (sel?: PortfolioSel, days?: number) =>
    get<AgendaView>(withSel(days ? `/api/calendar?days=${days}` : "/api/calendar", sel)),
  evidence: () => get<EvidenceView>("/api/evidence"),
  attribution: (sel?: PortfolioSel, start?: string) =>
    get<AttributionView>(withSel(start ? `/api/attribution?start=${enc(start)}` : "/api/attribution", sel)),
  priceCheck: (symbol: string, date: string) =>
    get<PriceCheck>(`/api/portfolio/price-check?symbol=${enc(symbol)}&date=${enc(date)}`),
  tax: (year: number) => get<TaxYearView>(`/api/tax?year=${year}`),
  taxPersons: () => get<TaxPersonView[]>("/api/tax/persons"),
  editTaxPerson: (id: number, p: TaxPersonIn) => get<TaxPersonView>(`/api/tax/persons/${id}`, "PUT", json(p), "application/json"),
  setInstrument: (symbol: string, i: InstrumentIn) =>
    get<InstrumentView>(`/api/tax/instruments/${enc(symbol)}`, "PUT", json(i), "application/json"),
  taxOpenings: () => get<TaxOpeningView[]>("/api/tax/openings"),
  addTaxOpening: (o: TaxOpeningIn) => get<TaxOpeningView>("/api/tax/openings", "POST", json(o), "application/json"),
  deleteTaxOpening: (id: number) => get<number>(`/api/tax/openings/${id}`, "DELETE"),
  portfolios: () => get<Portfolio[]>("/api/portfolios"),
  addPortfolio: (p: PortfolioIn) => get<Portfolio>("/api/portfolios", "POST", json(p), "application/json"),
  editPortfolio: (id: number, p: PortfolioIn) => get<Portfolio>(`/api/portfolios/${id}`, "PUT", json(p), "application/json"),
  deletePortfolio: (id: number) => get<Portfolio>(`/api/portfolios/${id}`, "DELETE"),
  setTags: (id: number, tags: string[]) => get<Portfolio>(`/api/portfolios/${id}/tags`, "PUT", json({ tags }), "application/json"),
  setDefaultPortfolio: (id: number) => get<Portfolio[]>(`/api/portfolios/${id}/default`, "POST"),
  moveRows: (from: number, m: MoveIn) => get<{ moved: number }>(`/api/portfolios/${from}/move`, "POST", json(m), "application/json"),
  tags: () => get<TagCount[]>("/api/portfolios/tags"),
  feePresets: () => get<FeePreset[]>("/api/portfolios/fee-presets"),
  simRuns: (id: number) => get<SimRun[]>(`/api/portfolios/${id}/runs`),
  forkPortfolio: (id: number, f: ForkIn) => get<Portfolio>(`/api/portfolios/${id}/fork`, "POST", json(f), "application/json"),
  compare: (sel?: PortfolioSel, start?: string) =>
    get<Comparison>(withSel(`/api/portfolios/compare${start ? `?start=${enc(start)}` : ""}`, sel)),
  performance: (id: number, start?: string) =>
    get<PerformanceView>(`/api/portfolios/${id}/performance${start ? `?start=${enc(start)}` : ""}`),
  importPresets: () => get<Preset[]>("/api/portfolio/import/presets"),
  importPreview: (file: ArrayBuffer, p: ImportParams) =>
    get<ImportPreview>(`/api/portfolio/import/preview?${importQuery(p)}`, "POST", file, "application/octet-stream"),
  importCommit: (file: ArrayBuffer, p: ImportParams) =>
    get<ImportCommitResult>(`/api/portfolio/import/commit?${importQuery(p)}`, "POST", file, "application/octet-stream"),
  imports: () => get<ImportRecord[]>("/api/portfolio/imports"),
  undoImport: (id: number) => get<number>(`/api/portfolio/imports/${id}`, "DELETE"),
  setupStatus: () => get<HomeStatus>("/api/setup"),
  setupScan: (path: string) => get<LegacyFound>(`/api/setup/scan?path=${enc(path)}`),
  setup: (s: SetupIn) => get<SetupResult>("/api/setup", "POST", json(s), "application/json"),
  dataHome: () => get<DataHome>("/api/data-home"),
  backupNow: () => get<BackupRow>("/api/data-home/backup", "POST"),
  setMirror: (path: string | null) => get<DataHome>("/api/data-home/mirror", "PUT", json({ path }), "application/json"),
  restoreBackup: (name: string) => get<RestoreResult>("/api/data-home/restore", "POST", json({ name }), "application/json"),
  openFolder: (key: string) => get<boolean>("/api/data-home/open", "POST", json({ key }), "application/json"),
  dataExportUrl: "/api/data-home/export",
  updates: () => get<UpdateCheck>("/api/updates"),
  setUpdates: (enabled: boolean) => get<UpdateCheck>("/api/updates", "PUT", json({ enabled }), "application/json"),
  secContact: () => get<SecContact>("/api/settings/sec-contact"),
  setSecContact: (email: string | null) =>
    get<SecContact>("/api/settings/sec-contact", "PUT", json({ email }), "application/json"),
  watch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "PUT"),
  unwatch: (symbol: string) => get<WatchState>(`/api/watchlist/${enc(symbol)}`, "DELETE"),
};
