import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Search } from "./components/Search";
import { Data } from "./pages/Data";
import { Home } from "./pages/Home";
import { Me } from "./pages/Me";
import { Momentum } from "./pages/Momentum";
import { Positioning } from "./pages/Positioning";
import { Regime } from "./pages/Regime";
import { Rotation } from "./pages/Rotation";
import { Themes } from "./pages/Themes";
import { Ticker } from "./pages/Ticker";
import "./styles.css";

const PAGES = [
  ["/regime", "Regime", <Regime />],
  ["/rotation", "Sector rotation", <Rotation />],
  ["/themes", "Themes & factors", <Themes />],
  ["/momentum", "Momentum", <Momentum />],
  ["/positioning", "Positioning & cycle", <Positioning />],
  ["/me", "My holdings & watchlist", <Me />],
  ["/data", "Data & coverage", <Data />],
] as const;

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

function Shell() {
  const { pathname } = useLocation();
  const home = pathname === "/";
  // a link from deep in a long table opens the next page at its top
  useEffect(() => {
    window.scrollTo(0, 0);   // block body: newer browsers return a Promise here, which React would take as a cleanup
  }, [pathname]);
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
      </header>
      <nav className="tabs" aria-label="Dashboard">
        {PAGES.map(([path, label]) => <NavLink key={path} to={path}>{label}</NavLink>)}
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        {PAGES.map(([path, , el]) => <Route key={path} path={path} element={el} />)}
        <Route path="/ticker/:symbol" element={<Ticker />} />
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
