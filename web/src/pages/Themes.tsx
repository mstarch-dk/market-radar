import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Loaded, PageHead } from "../components/cells";
import { GroupSection, THEME_GROUPS } from "./Rotation";

export function Themes() {
  const q = useQuery({ queryKey: ["rotation"], queryFn: api.rotation, retry: false, staleTime: 5 * 60_000 });
  return (
    <Loaded q={q} title="Themes & factors">
      {(d) => {
        const groups = d.groups.filter((g) => THEME_GROUPS.includes(g.key));
        const year = d.positive_list_year;
        return (
          <>
            <PageHead title="Themes & factors" asof={d.asof} generated={d.generated} ageDays={d.age_days} stale={d.stale}>
              Themes are measured with liquid US-listed ETFs. Use the <b>UCITS</b> column for something you can actually buy as
              a Danish investor, and verify it on justETF. <b>Positive list</b> (SKAT): <i>yes</i> means lager taxation as share
              income in frie midler, and the ETF can be held on an aktiesparekonto (17% lager). <i>no</i> means it&apos;s taxed as
              capital income in frie midler, which is usually less favourable, and it isn&apos;t eligible for the ASK. Prefer a
              positive-list alternative. Confirm current rules on skat.dk.{" "}
              {year
                ? <span className="muted">Checked against SKAT&apos;s {year} list. Search Saxo or Danske by ISIN to find the exact share class.</span>
                : <span className="muted">Positive list not loaded. Put SKAT&apos;s list in imports/positivliste.xlsx and add <code>isin:</code> to ETFs in universe.yaml.</span>}
            </PageHead>
            {groups.length > 1 && <nav className="jump">{groups.map((g) => <a key={g.key} href={`#${g.key}`}>{g.label}</a>)}</nav>}
            {groups.map((g) => <GroupSection key={g.key} g={g} tail={d.tail_weeks} themes plYear={year} />)}
          </>
        );
      }}
    </Loaded>
  );
}
