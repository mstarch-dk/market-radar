import { ImportPortfolio } from "../components/ImportPortfolio";
import { UpdatePanel } from "../components/UpdatePanel";

/** Shown instead of an error until the first market data has been downloaded. */
export function Welcome() {
  return (
    <div className="welcome">
      <h1>Welcome to Market Radar</h1>
      <p className="lead">
        Market Radar watches sector and theme rotation, momentum leaders and the market regime, and shows how your own
        holdings fit in. Everything runs on this computer, from free public data (Yahoo Finance, FRED, OECD, CFTC,
        FactSet). It is analysis, not investment advice.
      </p>
      <h2>1. Download the market data</h2>
      <p className="small muted">The first download covers about 700 stocks and ETFs and takes a few minutes. Later updates
        only fetch what's new and take about a minute.</p>
      <UpdatePanel label="Download market data" />
      <h2>2. Optional: add your portfolio</h2>
      <ImportPortfolio />
      <p className="small muted">You can also just look up any ticker with the search box at the top, and star names to
        build a watchlist.</p>
    </div>
  );
}
