import { describe, expect, it } from "vitest";
import type { SectorEtfsView } from "../api/client";
import { goToIndex, sectorAnchor } from "./sectorEtfs";

const rot = (ticker: string) => ({ ticker }) as SectorEtfsView["sectors"][number]["rotation"][number];
const view = {
  sectors: [
    { key: "Technology", label: "Teknologi", rotation: [rot("XLK"), rot("EXV3.DE")],
      etfs: [{ isin: "A", pick: false }, { isin: "B", pick: true }] },
    { key: "Banks", label: "Banker", rotation: [rot("EXV1.DE")], etfs: [] },
  ],
} as unknown as SectorEtfsView;

describe("sector ETF links", () => {
  it("makes anchors from keys", () => {
    expect(sectorAnchor("Technology")).toBe("technology");
    expect(sectorAnchor("Autos & Parts")).toBe("autos-parts");
    expect(sectorAnchor("Financial Services")).toBe("financial-services");
  });
  it("maps rotation tickers to their sector", () => {
    const { byTicker, byKey } = goToIndex(view);
    expect(byTicker.get("XLK")?.href).toBe("/sectoretfs#technology");
    expect(byTicker.get("EXV1.DE")?.href).toBe("/sectoretfs#banks");
    expect(byKey.get("Technology")?.pick?.isin).toBe("B");
    expect(byKey.get("Banks")?.pick).toBeNull();
    expect(goToIndex(undefined).byKey.size).toBe(0);
  });
});
