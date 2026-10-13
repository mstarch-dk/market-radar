import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { Search } from "./components/Search";
import { Home } from "./pages/Home";
import { Ticker } from "./pages/Ticker";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

function Shell() {
  const home = useLocation().pathname === "/";
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
      <Routes>
        <Route path="/" element={<Home />} />
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
