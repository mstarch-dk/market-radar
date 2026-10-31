# Claude og radarens værktøjer

Når du åbner programmappen i Claude Code, kan Claude bruge radaren direkte, som værktøjer. Det sker gennem en lille server, der følger med radaren: en MCP-server (Model Context Protocol, en standard der lader Claude kalde et programs funktioner). Skills som `/research` og `/market-brief` bruger værktøjerne, når de er der, og kommandolinjen, når de ikke er.

Værktøjerne er valgfrie. Appen og skills virker også uden dem.

> **Bemærk:** Værktøjerne regner ikke noget nyt. De giver Claude de samme tal, som appen og `radar … --json` viser, og alt, hvad Claude skriver ud fra dem, er analyse, ikke rådgivning.

## Hvad du får ud af det

- **Mindre at læse.** Claude henter det, der skal bruges, i stedet for hele filer: fx kun rotationen fra `summary.json` eller kun dine kalenderpunkter for én aktie. Et `/research`-notat læser cirka to tredjedele mindre, og månedsbriefen omkring en fjerdedel mindre.
- **Ingen stier.** Claude skal ikke slå datamappen op og bede om lov til at læse filer der; værktøjerne ved selv, hvor tingene ligger.
- **Alder på svarene.** Et svar fra rapporten siger, hvor gammelt det er (`asof`, `age_days`) og om det er forældet (`stale`), så Claude ikke selv skal regne det ud.
- **Manglende data er `null`**, aldrig 0, og skal skrives som "n/a".
- **Klare tilladelser.** Hvert værktøj er mærket: læser det kun, kan det erstatte en fil, og går det på nettet.

## Sådan slår du det til

1. Åbn programmappen (den mappe, hvor startscriptet ligger) i Claude Code. Filen `.mcp.json` i programmappen fortæller Claude Code, at serveren startes med `uv run radar mcp`.
2. Første gang spørger Claude Code, om du vil bruge serveren `radar` fra projektet. Svar ja.
3. Skriv `/mcp` i Claude Code. Står `radar` som forbundet, er værktøjerne klar.

Serveren skal bruge din datamappe. Er der endnu ikke valgt en, så start appen eller kør `uv run radar setup` først.

Claude Code spørger, før et værktøj bruges første gang. Du kan give lov til de værktøjer, der kun læser, så du ikke bliver spurgt hver gang, og lade dem, der gemmer noget, spørge.

## Værktøjerne

| Gruppe | Værktøjer | Hvad de gør |
|---|---|---|
| Læser | `investor_notes`, `market_views`, `summary`, `discovery`, `ticker_profile`, `portfolios`, `performance`, `portfolio_xray`, `attribution`, `calendar`, `evidence_view`, `study_reports`, `documents`, `journal_entries`, `read_document`, `data_paths`, `trading_rules` | Din investorprofil, dine markedssyn og handelsregler, rapporten i udsnit, Discover-scanningen, en eller flere tickere, dine porteføljer og deres afkast, X-ray, attribution, kalenderen, evidensen, studiernes alder og notesbogen |
| Læser (forslag og scout) | `propose_candidates`, `propose_picks`, `propose_review`, `propose_check`, `sim_picks_candidates`, `scout_review` | Et forslags kandidater, et låst forslags valg, gennemgangen af tidligere forslag og deres exitkriterier, universet som det så ud på en tidligere dag, og hvordan de frosne scout-kandidater er gået |
| Job | `job_start`, `job_status` | Opdatér data, genopbyg rapporten eller kør et studie, og følg med |
| Gemmer | `propose_freeze`, `propose_evaluate`, `propose_shadow`, `sim_picks`, `scout_freeze`, `write_memo`, `add_trade`, `add_view`, `rules_check`, `add_rule`, `rule_decision` | Lås et forslag og regn det igennem, lav virtuelle kopier, simulér en kurv, frys en scout-kandidat, skriv et dokument, registrér en handel, tilføj et markedssyn, test en handling mod dine handelsregler (gemmes kun, når en skill beder om det), tilføj en regel og gem, hvad du gjorde efter et tjek |

Hvert værktøj svarer med det samme som den tilsvarende kommando med `--json`; se [Kommandolinjen](brugervejledning/kommandolinjen).

## Det, der gemmer

- **Dokumenter** (`write_memo`) skrives kun i notesbogens mapper i datamappen: `briefs/`, `research/`, `journal/` og deres undermapper. En fil skrives helt eller slet ikke, og et dokument, der findes i forvejen, erstattes kun, når Claude beder om det; det gør en skill først efter at have læst det og beholdt det gamle indhold. Se [Notesbogen](brugervejledning/notesbog).
- **En handelsregel** (`add_rule`) vises først, præcis som den ville blive gemt, og gemmes kun, når du har sagt ja. Se [Mine handelsregler](brugervejledning/handelsregler).
- **Et markedssyn** (`add_view`) vises først, præcis som det ville blive gemt, med radarens evidens for det og de syn, det overlapper eller modsiger. Det gemmes kun, når du har sagt ja. Et syn fra `/scout` husker, hvilken kandidat det kom fra. Se [Mine markedssyn](brugervejledning/markedssyn).
- **En scout-kandidat** (`scout_freeze`) gemmes i `exports/scout/` med dato, stadie, dit valg og proxy-kurven, og overskrives aldrig. Har radaren ikke kurser for et papir, hentes de først. Se [Scout](brugervejledning/scout#resultaterne).
- **En handel** (`add_trade`) tjekkes på samme måde som i appen, også mod dine handelsregler. Første gang gemmes intet: Claude får tjekkenes advarsler og din position før og efter, og viser dig dem. Først når du siger ja, gemmes handlen. En fejl i tjekket stopper den altid.
- **Forslag og simuleringer** gemmer et låst forslag i `exports/proposals/`, dets beregning ved siden af og virtuelle porteføljer, som du ser under *Experiments* og på [Returns](/returns). De rører aldrig dine rigtige porteføljer.
- **En opdatering** (`job_start` med `update`) henter data fra nettet, som knappen *Update data*.

## Job: opdatering og studier

`job_start` starter et langt job i baggrunden, og `job_status` viser, hvor langt det er:

- **update** henter nye data og bygger rapporten bagefter (nogle minutter);
- **report** bygger rapporten igen ud fra de data, der allerede er hentet;
- **study** kører et af studierne fra siden *Evidence* (fra nogle minutter til en time).

`job_status` siger, hvilket trin der kører (fx trin 4 af 20), hvor langt det er, og hvilke problemer der er opstået indtil nu: kilder der fejlede, tickers uden data og websteder på pause. Claude fortæller dig det undervejs, fx under månedsbriefen.

Der kører kun ét job af hver slags ad gangen, på tværs af appen, terminalen og Claude. Kører et allerede et andet sted, siger værktøjet det i stedet for at starte et til, og `job_status` viser så den opdatering, der kører. Et job, Claude starter, vises live på siden *Operations* (se [Drift](brugervejledning/drift#kører-nu)), og en opdatering også i panelet *Update data*.

Lukker du Claude Code, mens et job kører, stopper jobbet. Dine data tager ikke skade, fordi hver fil skrives helt eller slet ikke; start jobbet igen.

## Når værktøjerne ikke er der

Hver skill har én linje om, hvad den gør uden værktøjerne: så bruger den kommandolinjen (`uv run radar …`) som før. Det sker, hvis du har sagt nej til serveren, eller hvis Claude kører et sted, der ikke indlæser projektets `.mcp.json`. Månedsbriefen, der kører som planlagt opgave den første i hver måned, virker på begge måder; se [Månedsbriefen](brugervejledning/maanedsbrief).

## Dine data og privatliv

Serveren kører på din computer og taler kun med den Claude Code, der har startet den. Den lytter ikke på nogen port og kan ikke nås fra netværket. Det, et værktøj svarer, læser Claude som en del af jeres samtale, ligesom når en skill læser en fil. Det gælder også dine personlige data, når en skill bruger dem. Se [Datakilder og licenser](brugervejledning/datalicenser#praktiske-regler-for-din-kopi).

## Fejlfinding

- **`/mcp` viser `radar` som fejlet.** Kør `uv run radar doctor` i programmappen; det siger, om Python, datamappen og dataene er i orden. Uden datamappe starter serveren ikke.
- **Et svar siger `stale`.** Rapporten er ældre end grænsen for kurser i indstillingerne. Bed Claude om at opdatere (det bruger `job_start`), eller tryk *Update data* i appen.
- **"Not started: an update is already running".** En opdatering kører allerede i appen eller en terminal. Vent, til den er færdig.
