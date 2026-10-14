# Installation og første start

Market Radar kører lokalt på din egen computer (Windows eller Mac). Du behøver ikke installere noget selv: startscriptet sætter alt op første gang. Er du udvikler og vil bygge fra kildekoden, står det længere nede.

## Installation fra en release

1. **Hent** den nyeste `market-radar-….zip` fra projektets *Releases*-side på GitHub (under *Assets*).
2. **Pak den ud** et sted, hvor den skal blive, fx `Dokumenter\Market Radar`. Kør den ikke inde fra zip-filen.
3. **Start den:**
   - **Windows:** dobbeltklik på `Start Market Radar.cmd`. Viser Windows "Windows protected your PC", så klik *More info* → *Run anyway*. Scriptet er almindelig tekst, som du kan åbne i Notesblok og læse.
   - **Mac:** højreklik (eller ctrl-klik) på `Start Market Radar.command` → *Open* → *Open*. Det er kun nødvendigt første gang; derefter er et dobbeltklik nok.
4. Et sort vindue åbner og gør alt klar. Din browser åbner derefter Market Radar på <http://127.0.0.1:8780>.

### Hvad startscriptet gør
Scriptet gør tre ting, i denne rækkefølge:

- **Installerer uv**, hvis det mangler. uv er det lille værktøj, der kører Market Radars Python-kode. Det installeres i din brugermappe og kræver ikke administratorrettigheder. Første gang tager det et par minutter, fordi uv også henter den Python-version, der skal bruges.
- **Kører `uv sync`**, som installerer præcis de pakkeversioner, projektet er låst til.
- **Starter appen** med `radar serve --open`, som starter den lokale server og åbner browseren.

> **Bemærk:** Hold det sorte vindue åbent, mens du bruger Market Radar. Lukker du det, stopper appen. Næste gang dobbeltklikker du bare på startscriptet igen.

Går noget galt undervejs, kører scriptet selv `radar doctor` (se nedenfor) og skriver, hvad der mangler, og hvordan du løser det.

### Opdatering til en ny version
Pak den nye version ud i en ny mappe, og kopier dine personlige mapper over: `userdata/`, `notes/`, `imports/` og, hvis du bruger Claude Code, `briefs/`, `research/` og `journal/`. Markedsdata i `data/` og `reports/` kan du også kopiere, eller du kan hente dem igen. Se [Data og opdatering](brugervejledning/data-og-opdatering#hvor-dine-data-ligger).

## Første start: velkomstsiden

Indtil der er hentet markedsdata, viser alle markedssiderne en velkomstside, *Welcome to Market Radar*, i stedet for en fejl. Den har to trin:

1. **Download the market data.** Klik *Download market data*. Første download dækker omkring 700 aktier og ETF'er og tager typisk et par minutter (afhængigt af din forbindelse). Du kan følge fremskridtet og godt kigge rundt imens; siderne opdaterer sig selv, når det er færdigt.
2. **Optional: add your portfolio.** Du kan indtaste dine handler på siden [Portfolio](/portfolio) eller importere en eksport fra Yahoo Finance direkte på velkomstsiden. Import fra din bank eller mægler (fx Danske Bank, Nordea, Saxo Bank eller Nordnet) og fra regneark sker på *Portfolio*-siden; se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).

Du kan også springe porteføljen over og bare søge på en ticker i søgefeltet øverst. Senere opdateringer henter kun det nye og tager omkring et minut.

> **Tip:** Discover-siden har sin egen, separate scanning. Den køres ikke med første download; du starter den fra siden selv med *Run the first discovery scan*. Se [Discover](brugervejledning/discover).

## Tjek opsætningen med radar doctor

`radar doctor` er et tjek i almindeligt sprog af hele opsætningen. Det fortæller for hvert punkt, om det er i orden, og hvordan du løser det, hvis ikke. Du kører det i en terminal i Market Radar-mappen:

```
uv run radar doctor
```

Tjekket dækker:

| Punkt | Hvad det ser efter |
|---|---|
| *Python* | Python-versionen (3.11 eller nyere) |
| *Web app* | At webappen er bygget |
| *Market data* og *Dashboard* | Om der er hentet data, og hvor gamle de er |
| *SKAT positive list* | Om `imports/positivliste.xlsx` findes, kan læses og er fra i år |
| *Your portfolio* | Om dine handler kan læses |
| *Investor profile for Claude* | Om `notes/investor.md` findes (kun relevant for Claude Code) |
| *Internet: …* | Om hver datakilde kan nås |

Med `--offline` springes netværkstjekkene over. Det samme tjek findes i appen på siden [Operations](/ops); se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift).

## SKATs positivliste

Radaren markerer for hver ETF, om den står på SKATs positivliste over aktiebaserede investeringsselskaber. Det har betydning for beskatningen i frie midler og for, om fonden kan ligge på en aktiesparekonto. For at det virker, skal listen ligge lokalt:

1. Hent den aktuelle positivliste (Excel-filen) fra skat.dk.
2. Gem den som `imports/positivliste.xlsx` i Market Radar-mappen.
3. Opdater data, så tabellerne bliver bygget igen.

Radaren bruger kun det nyeste års ark i filen; ældre ark er historik. SKAT udgiver en ny liste hvert år, og `radar doctor` advarer, når filens nyeste ark er fra et tidligere år. Uden filen viser kolonnen *Positive list* et "?" for alle fonde, og Discover kan ikke bygge sit marked for UCITS-ETF'er.

> **Bemærk:** Positivliste-status er en hjælp, ikke skatterådgivning. Tjek de aktuelle regler på skat.dk. Baggrunden står i [Dansk skat for investorer](laerebog/skat).

## Til Claude Code: din investorprofil

Bruger du Claude Code-kommandoerne (`/market-brief`, `/research`, `/compare`, `/journal`), skal de vide lidt om dig: dine konti, din horisont og dine grænser. Det står i en lille fil, du selv udfylder:

1. Kopier `investor.example.md` til `notes/investor.md`.
2. Udfyld dine konti (fx aktiesparekonto og frie midler, med de samme navne som dine porteføljer i appen), din typiske holdeperiode, maksimal positionsstørrelse og hvad du undgår.

Mappen `notes/` bliver på din computer og deles aldrig. Dine markedssyn skal ikke stå i filen; de hører hjemme på siden *Market views*. Se [Claude Code-skills](brugervejledning/claude-code).

## Udvikleropsætning

Vil du køre fra kildekoden i stedet for en release, skal du have [uv](https://docs.astral.sh/uv/), Node 22 eller nyere og pnpm:

```
uv sync
pnpm -C web install
pnpm -C web build
uv run radar serve --open
```

- `pnpm -C web build` bygger webappen til `web/dist`. Det skal gøres igen, når frontend-koden ændrer sig.
- `uv run radar run` henter data og bygger dashboardet fra terminalen (samme som knappen *Update data*).
- Til frontend-arbejde kører du `pnpm -C web dev` (port 5173) ved siden af `radar serve`; den sender API-kald videre til port 8780.
- Testene køres med `uv run pytest -q` og `pnpm -C web test`.

Alle kommandoer er beskrevet i [Kommandolinjen](brugervejledning/kommandolinjen).

## Hvis noget ikke virker

- **Browseren åbnede ikke:** gå selv til <http://127.0.0.1:8780>, mens det sorte vindue er åbent.
- **"Market Radar is already running":** appen kører allerede i et andet vindue. Brug bare browserfanen.
- **Noget fejlede i det sorte vindue:** læs, hvad `radar doctor` skriver nederst i vinduet.
- **Firewall eller antivirus spørger:** Market Radar henter kun offentlige data (Yahoo Finance, FRED, OECD, CFTC, FactSet m.fl.), og appen kan kun nås fra din egen computer.

Flere problemer og løsninger står i [Fejlfinding og spørgsmål](brugervejledning/fejlfinding).
