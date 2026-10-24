import type { Quadrant, RegimeLabel } from "../api/client";

/** Badge kind and chart colour per rotation quadrant: every quadrant must have one (the type says which exist). */
export const QUAD_KIND: Record<Quadrant, string> = { Leading: "pos", Weakening: "warn", Lagging: "neg", Improving: "accent", "n/a": "" };
export const QUAD_COLOR: Record<Quadrant, string> = {
  Leading: "var(--pos)", Weakening: "var(--warn)", Lagging: "var(--neg)", Improving: "var(--accent)", "n/a": "var(--muted)",
};

/** Badge kind per overall regime label. */
export const REGIME_KIND: Record<RegimeLabel, string> = { "Risk-on": "pos", "Risk-off": "neg", Mixed: "warn" };
