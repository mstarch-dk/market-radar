import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Search } from "./components/Search";
import { Data } from "./pages/Data";
import { Discover } from "./pages/Discover";
import { Home } from "./pages/Home";
import { Me } from "./pages/Me";
import { Momentum } from "./pages/Momentum";
import { Ops } from "./pages/Ops";
import { Performance } from "./pages/Performance";
import { Portfolio } from "./pages/Portfolio";
import { Positioning } from "./pages/Positioning";
import { Regime } from "./pages/Regime";
import { Rotation } from "./pages/Rotation";
import { Themes } from "./pages/Themes";
import { Views } from "./pages/Views";
import { Ticker } from "./pages/Ticker";
import { pageChapter, useGuideTree } from "./lib/guide";
import "./styles.css";

const Guide = lazy(() => import("./pages/Guide"));   // Markdown + KaTeX load only when the guide is opened

const PAGES = [
  ["/regime", "Regime", <Regime />],
  ["/rotation", "Sector rotation", <Rotation />],
  ["/themes", "Themes & factors", <Themes />],
  ["/momentum", "Momentum", <Momentum />],
  ["/discover", "Discover", <Discover />],
  ["/positioning", "Positioning & cycle", <Positioning />],
  ["/me", "My holdings & watchlist", <Me />],
  ["/views", "My market views", <Views />],
  ["/portfolio", "Portfolio", <Portfolio />],
  ["/returns", "Returns", <Performance />],
  ["/data", "Data & coverage", <Data />],
  ["/ops", "Operations", <Ops />],
] as const;

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

function Shell() {
  const { pathname, hash } = useLocation();
  const home = pathname === "/";
  const guide = useGuideTree();
  const about = guide.data ? pageChapter(guide.data.page_links, pathname) : null;
  // a link from deep in a long table opens the next page at its top (a link to a #heading scrolls there instead)
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0);   // block body: newer browsers return a Promise here, which React would take as a cleanup
  }, [pathname]);   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden="true">
            <circle cx="16" cy="16" r="13" fill="none" stroke="var(--accent)" strokeWidth="3" />
            <circle cx="16" cy="16" r="4" fill="var(--accent)" />
          </svg>
          Market Radar
        </Link>
        {!home && <div className="search"><Search /></div>}
        <Link to="/guide" className={`guide-link ${pathname.startsWith("/guide") ? "on" : ""}`} title="Brugervejledning og lærebog (dansk)">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"><path d="M2 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H2z" /><path d="M22 4h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8z" /></svg>
          Guide
        </Link>
      </header>
      <nav className="tabs" aria-label="Dashboard">
        {PAGES.map(([path, label]) => <NavLink key={path} to={path}>{label}</NavLink>)}
        {about && <Link to={`/guide/${about}`} className="about-page" title="Kapitlet om denne side i brugervejledningen">? Om denne side</Link>}
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        {PAGES.map(([path, , el]) => <Route key={path} path={path} element={el} />)}
        <Route path="/ticker/:symbol" element={<Ticker />} />
        <Route path="/guide/*" element={<Suspense fallback={<div className="skeleton" style={{ height: 400 }} aria-busy="true" />}><Guide /></Suspense>} />
        <Route path="*" element={<p>Not found. <Link to="/">Back to search</Link></p>} />
      </Routes>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
