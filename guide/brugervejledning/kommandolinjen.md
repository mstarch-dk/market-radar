# Kommandolinjen

Alt, hvad appen kan, bygger på kommandoen `radar`, som du også kan bruge direkte i en terminal. Det er praktisk, hvis du vil automatisere en opdatering, arbejde med Claude Code eller bare foretrækker tastaturet. Du behøver den ikke for at bruge Market Radar.

## Sådan kører du kommandoerne

Åbn en terminal i programmappen (den mappe, hvor startscriptet ligger), og skriv kommandoerne med `uv run` foran:

```
uv run radar doctor
```

`uv` er det lille værktøj, startscriptet installerede første gang; det sørger for den rigtige Python og de rigtige pakker. Alle kommandoer har en hjælpetekst:

```
uv run radar --help
uv run radar portfolios --help
uv run radar info --help
```

Kommandoerne og appen deler de samme data. Kører appen, mens du ændrer noget på kommandolinjen, ser appen ændringen næste gang siden indlæses.

Kommandoerne finder selv din datamappe (se [Dine data, backup og opdatering](brugervejledning/dine-data)). To tilvalg gælder for alle kommandoer og skrives før kommandoens navn:

```
uv run radar --version                       # hvilken version af Market Radar du kører
uv run radar --home "D:\Test\Market Radar" portfolios list   # brug en anden datamappe, kun denne gang
```

Er der endnu ikke valgt en datamappe, mangler den, eller er dataene skrevet af en nyere version, nægter kommandoerne at køre og siger hvorfor. Kun `setup`, `paths`, `serve`, `doctor`, `ticker` og `openapi` kører alligevel.

## Data og rapport

| Kommando | Gør |
|---|---|
| `radar run` | Henter nye data og bygger rapporten. Det samme som *Update data* i appen |
| `radar update` | Kun den første halvdel: henter kurser, makroserier og de øvrige kilder |
| `radar report` | Kun den anden halvdel: bygger `dashboard.json` og `summary.json` i cache-mappens `reports/` fra de data, der er |
| `radar discover` | Den separate Discover-scanning (nordiske og europæiske aktier, S&P 500, ETF'er fra positivlisten) |
| `radar doctor` | Sundhedstjekket |
| `radar ops` | Driftsloggen: forespørgsler, fejl og pauser |
| `radar fundamentals` | Selskabernes regnskaber: hent, vis og tjek dem, og angiv kontakten til SEC |

### radar run, update og report

`radar run` henter kun det nye (kurser siden sidste gang), henter de ikke-kursbaserede kilder (FRED, CFTC, OECD, FactSet, analytikerkonsensus, værdiansættelse, sentiment) og bygger rapporten. Først tager den dagens backup af dine data, hvis der ikke er taget en i dag. En kilde, der fejler, skriver en advarsel og beholder sine data. Hver kilde logges i `sources.json` i cache-mappen, som siden [Data & coverage](/data) viser.

```
uv run radar run
uv run radar run --refresh-constituents     # hent også listen over S&P 500-aktier igen
uv run radar update                          # kun data
uv run radar report                          # kun rapporten
```

Listen over S&P 500-aktier hentes ellers igen, når den er ældre end {{settings:constituents_max_age_days}} dage.

### radar discover

```
uv run radar discover
uv run radar discover --refresh-universe     # byg navnelisten igen nu (ellers månedligt)
```

Scanningen skriver `discovery.json` i cache-mappens `reports/` til siden *Discover* og rører ikke resten af radarens data. Kør den cirka ugentligt. Knappen *Scan again* på siden gør det samme. Se [Discover](brugervejledning/discover).

### radar doctor

```
uv run radar doctor
uv run radar doctor --offline                # uden at kontakte datakilderne
```

Tjekker Python, den byggede app, datamappen, markedsdata, rapporten, positivlisten, din portefølje, investorprofilen og hver datakilde, og siger, hvordan du retter det, der mangler. Se [Fejlfinding og spørgsmål](brugervejledning/fejlfinding#sundhedstjekket-radar-doctor).

### radar ops

```
uv run radar ops                             # de seneste 7 dage
uv run radar ops --days 30
uv run radar ops --errors                    # også de seneste fejlhændelser
```

Se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift).

### radar fundamentals

```
uv run radar fundamentals contact din@mail.dk     # kontakten, SEC beder om (ellers kun Yahoo for USA)
uv run radar fundamentals update                  # hent de selskaber, der står for tur
uv run radar fundamentals update AAPL NOVO-B.CO   # kun disse
uv run radar fundamentals update --all            # alle på én gang (tager et stykke tid)
uv run radar fundamentals show AAPL               # hvad der er gemt, og hvordan de seneste 12 måneder er regnet
uv run radar fundamentals check                   # EDGAR mod Yahoo for amerikanske selskaber
```

`radar update` henter selv de selskaber, der står for tur. Se [Regnskaber](brugervejledning/data-og-daekning#regnskaber).

## Appen

| Kommando | Gør |
|---|---|
| `radar serve` | Starter appen på http://127.0.0.1:8780 |
| `radar serve --open` | Starter appen og åbner browseren |
| `radar serve --port 8781` | Bruger en anden port |
| `radar ticker NOVO-B.CO` | Åbner tickerprofilen i browseren og starter appen, hvis den ikke kører |

Appen kan kun nås fra din egen computer. Kører den allerede, siger `serve` det og åbner blot browseren. Luk den med Ctrl+C i terminalen.

## Et eller flere navne

`radar info` skriver alt, hvad radaren ved om et navn, som JSON. Følger radaren ikke navnet, hentes kurserne først.

```
uv run radar info NOVO-B.CO
uv run radar info NOVO-B.CO --refresh        # hent Yahoos nøgletal og estimater på ny
```

Med flere navne får du en sammenligning side om side, med ACWI som benchmark, ugentlige korrelationer i DKK og en tabel med den bedste værdi pr. række. Det er det, `/compare` bruger:

```
uv run radar info NVDA AMD MU
uv run radar info NVDA AMD MU --out chips.json
uv run radar info NVDA AMD --personal        # med dine positioner, beholdninger og markedssyn
uv run radar info NVDA AMD --personal --portfolio ASK
```

Uden `--personal` er sammenligningen anonym. Med `--personal` er dine rigtige porteføljer "dine beholdninger"; `--portfolio` og `--tag` vælger andre. Et ukendt symbol bliver en `error`-post i stedet for at stoppe det hele. Se [Tickerprofilen](brugervejledning/tickerprofil).

## Dine markedssyn

```
uv run radar views                           # aktive syn med evidens
uv run radar views --archived                # også arkiverede
uv run radar views --json                    # til Claude-skills
```

Se [Mine markedssyn](brugervejledning/markedssyn).

## Porteføljer

`radar portfolios` styrer selve porteføljerne:

```
uv run radar portfolios list
uv run radar portfolios list --json --archived
uv run radar portfolios add "ASK" --kind ask
uv run radar portfolios add "Momentum test" --virtual --tag momentum-a
uv run radar portfolios edit "ASK" --dividends cash
uv run radar portfolios edit "Main" --rename "Frie midler" --kind frie_midler
uv run radar portfolios tag "Momentum test" sim
uv run radar portfolios untag "Momentum test" sim
uv run radar portfolios default "ASK"
uv run radar portfolios move "Main" --to "ASK" --symbol NOVO-B.CO
uv run radar portfolios fork "ASK" "ASK test" --date 2026-06-30 --cash 10000 --tag test
uv run radar portfolios archive "Gammel konto"
uv run radar portfolios archive "Gammel konto" --undo
uv run radar portfolios delete "Momentum test"
```

Navne med mellemrum skal i anførselstegn. Skattetyperne er `ask`, `frie_midler`, `pension` og `other`; udbyttepolitikken `reinvested` eller `cash`. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

## Handler

`radar portfolio` (uden s) arbejder med de enkelte rækker:

```
uv run radar portfolio list
uv run radar portfolio list --symbol NOVO-B.CO --portfolio ASK
uv run radar portfolio list --tag momentum-a
uv run radar portfolio add BUY NOVO-B.CO 10 612.40 --date 2026-01-05 --fee 29 --portfolio ASK
uv run radar portfolio add SELL NOVO-B.CO 5 640 --portfolio ASK --yes
uv run radar portfolio export --out backup.csv
uv run radar portfolio export --all --out alt.csv
```

- `list` viser rækkerne, ældste først. Standard er dine rigtige porteføljer.
- `add` tilføjer et køb eller salg med samme kontrol som i appen. Fejl blokerer altid; advarsler kræver `--yes`. Uden `--portfolio` havner handlen i standardporteføljen, og uden `--date` er datoen i dag. Kurtage (`--fee`) er i papirets valuta. Brug punktum som decimaltegn.
- `export` skriver rækkerne som CSV, fx som backup. `--all` tager også virtuelle porteføljer med.

Kontantrækker (indbetalinger, udbytte osv.) og import fra banker sker i appen. Se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).

### Import fra Yahoo Finance

```
uv run radar import-yahoo imports/yahoo_portfolio.csv
```

Importerer en Yahoo Finance-eksport. Den erstatter den forrige Yahoo-import; handler fra andre kilder bevares. Ukendte transaktionstyper springes over med en advarsel. Kør `radar run` bagefter for at hente kurser for nye navne.

## Afkast

```
uv run radar performance                     # hver af dine rigtige porteføljer
uv run radar performance "ASK" "ASK test"    # bestemte porteføljer, også virtuelle
uv run radar performance --tag momentum-a --tag momentum-b
uv run radar performance --start 2026-01-01
uv run radar performance --json
```

### Simulér stop og take-profit

`radar sim exits` afspiller dine rigtige handler med radarens stop og take-profit fulgt, dag for dag, ind i virtuelle porteføljer. Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering).

```
uv run radar sim exits
uv run radar sim exits "ASK" --variant overlay --fill same
```

Viser værdi, tidsvægtet afkast (TWR, også pr. år), pengevægtet afkast (MWR pr. år), ACWI, forskellen til ACWI og største fald i DKK fra en fælles startdato, med noter om huller. Se [Afkast over tid](brugervejledning/afkast).

### Test momentumscoren

`radar study score` tester scoren på hver månedsafslutning i historikken; `radar sim picks` simulerer en kurv valgt på en dag i fortiden. Se [Test momentumscoren på historikken](brugervejledning/scoretest).

```
uv run radar study score
uv run radar study score --exits 6 --json
uv run radar study exits
uv run radar study redeploy
uv run radar sim picks-candidates --asof 6M
uv run radar sim picks --asof 6M --rule top-n --n 15 --max-per-sector 3 --name test-6m
uv run radar sim picks --rerun tag:picks-live
```

## Datamappe, backup og eksport

| Kommando | Gør |
|---|---|
| `radar paths` | Viser, hvor datamappen, historikken, backupperne og cache-mappen ligger, og hvordan de blev fundet (`--json` til skills) |
| `radar setup` | Vælger datamappen: kopierer dine data fra en ældre version, starter tomt (`--fresh`) eller bruger en mappe, der findes (`--use STI`) |
| `radar backup` | Tager en backup nu. `--reason ord` sætter et ord i filnavnet; `--mirror STI` kopierer fremover hver backup til en anden mappe, `--mirror off` stopper det |
| `radar backups` | Lister backupperne i datamappen og i den anden mappe |
| `radar restore FIL` | Gendanner en backup; det, der er der nu, tages backup af først. `--yes` spørger ikke |
| `radar export` | Skriver dine data i åbne formater (CSV, JSON, Markdown) som zip i `exports/` i datamappen; `--out FIL` vælger et andet sted |
| `radar import-export FIL` | Indlæser en eksport: porteføljerne i den får præcis dens rækker, og dokumenter, der ikke findes, bliver lagt ind |
| `radar updates` | Viser, om der er en ny version; `--on` og `--off` slår det daglige tjek til og fra |

```
uv run radar setup                           # spørger, hvilken gammel mappe der skal kopieres fra
uv run radar setup --from "C:\Users\dig\Downloads\market-radar-v0.1" --to "D:\Market Radar"
uv run radar setup --use "D:\Market Radar"    # mappen er flyttet eller kopieret fra en anden computer
uv run radar backup --mirror "C:\Users\dig\OneDrive\Market Radar backups"
uv run radar restore "C:\Users\dig\Market Radar\backups\market-radar-20261015-091500-daily-daily.zip"
```

Alt om datamappen, backup, eksport og opdatering står i [Dine data, backup og opdatering](brugervejledning/dine-data).

## Flyt dine data til en anden computer

Den nemmeste vej er at kopiere hele datamappen og køre `uv run radar setup --use STI` på den nye computer; se [Flyt datamappen](brugervejledning/dine-data#flyt-datamappen). En eksport (`radar export` og `radar import-export`) tager porteføljer, markedssyn og dokumenter med, men ikke historikken. Vil du kun have porteføljedelen med som én tekstfil, findes også:

```
uv run radar bundle-holdings --out min-radar.bundle
uv run radar bundle-holdings --out min-radar.bundle --include-virtual
uv run radar unbundle-holdings --file min-radar.bundle     # på den nye computer
```

`bundle-holdings` pakker dine rigtige porteføljer (med `--include-virtual` også de virtuelle) med handler, kontotype og tags, dine ændringer til watchlist, dine markedssyn og dit valg af regimeafstemning i én tekstfil. Uden `--out` skrives bundtet i terminalen.

`unbundle-holdings` på den anden computer tager først en sikkerhedskopi af databasen og giver derefter hver portefølje i bundtet præcis dens handler. Markedsdata følger ikke med; dem henter radaren selv ved næste opdatering.

> **Bemærk:** Bundtet indeholder dine beholdninger. Behandl filen som personlig, og slet den, når flytningen er gjort.

## Til udviklere

| Kommando | Gør |
|---|---|
| `radar openapi` | Skriver appens API-skema (bruges til at generere TypeScript-typerne) |
| `uv run pytest -q` | Kører Python-testene |
| `pnpm -C web install` og `pnpm -C web build` | Bygger webappen til `web/dist` |
| `pnpm -C web test` | Kører webappens tests |
| `.\scripts\restart.ps1` | Genstarter appen efter en `git pull`: bygger webappen, synkroniserer pakkerne og starter serveren igen (Windows) |

## Hurtig reference

| Jeg vil … | Kommando |
|---|---|
| opdatere alt | `uv run radar run` |
| starte appen | `uv run radar serve --open` |
| se ét navn | `uv run radar ticker NOVO-B.CO` |
| tjekke opsætningen | `uv run radar doctor` |
| se om noget fejler | `uv run radar ops --errors` |
| se mine porteføljer | `uv run radar portfolios list` |
| se mit afkast mod ACWI | `uv run radar performance` |
| teste momentumscoren | `uv run radar study score` |
| teste varianter af stopreglen | `uv run radar study exits` |
| teste stopreglen med pengene i en ny aktie | `uv run radar study redeploy` |
| simulere en kurv fra for 6 måneder siden | `uv run radar sim picks --asof 6M --rule top-n --name test-6m` |
| se hvor mine data ligger | `uv run radar paths` |
| tage backup af alle mine data | `uv run radar backup` |
| eksportere mine data til CSV, JSON og Markdown | `uv run radar export` |
| gemme mine handler som CSV | `uv run radar portfolio export --all --out handler.csv` |
| se hvilken version jeg har | `uv run radar --version` |
