# Fejlfinding og spørgsmål

Dette kapitel samler de problemer, du oftest møder, og hvad du gør ved dem. Det første sted at kigge er næsten altid sundhedstjekket.

## Sundhedstjekket (radar doctor)

Sundhedstjekket ser efter, om alt det, Market Radar har brug for, er på plads, og siger med almindelige ord, hvordan du retter det, der mangler. Du kan køre det tre steder:

- På siden [Operations](/ops) under *Health checks*: *Check the setup* eller *Check + contact every source*.
- I terminalen: `uv run radar doctor` (eller `uv run radar doctor --offline` uden netværkstjek).
- Startscriptet kører det selv, når noget går galt.

Hver linje har en status:

| Status | I terminalen | Betyder |
|---|---|---|
| ok | `[OK  ]` | I orden |
| warn | `[WARN]` | Virker, men bør ses på |
| fail | `[FAIL]` | Skal rettes; kommandoen slutter med en fejlkode |
| info | `[info]` | Kun oplysning |

Ved *warn* og *fail* står der en linje med `→` og hvad du kan gøre. Tjekket ser på:

- **Python**: version 3.11 eller nyere.
- **Web app**: om den byggede app (`web/dist`) findes.
- **Market data**: hvornår kurserne sidst blev hentet (advarsel efter 7 dage).
- **Dashboard**: hvornår rapporten sidst blev bygget (advarsel efter 7 dage).
- **SKAT positive list**: om positivlisten findes og har årets ark.
- **Your portfolio**: antal handler, og om flytningen af gamle CSV-filer gik godt.
- **Investor profile for Claude**: om `notes/investor.md` findes (valgfri).
- **Internet: …**: én linje pr. datakilde (kun uden `--offline`). Ethvert svar under HTTP 500 regnes for "oppe". Et websted på pause vises som advarsel.

## "Welcome to Market Radar" i stedet for data

Siderne viser velkomstsiden, så længe der ikke er bygget en rapport (`reports/dashboard.json`). Det er normalt første gang. Klik *Download market data*. Første hentning dækker omkring 700 aktier og ETF'er og tager nogle minutter; senere opdateringer henter kun det nye. Du kan også importere en portefølje fra Yahoo Finance på samme side.

Ser du velkomstsiden efter at have haft data, er `reports/` blevet slettet eller rapporten er ikke blevet bygget. Kør *Update data* (eller `uv run radar run`) igen.

## En kilde fejler

En kilde, der fejler, beholder sine seneste data, og resten af opdateringen fortsætter. Du ser det tre steder:

- På [Data & coverage](/data) i kolonnen *Last update*, med rød tekst og tidspunktet for sidste succes.
- På [Operations](/ops) som en hændelse af typen *source* eller *parse*, ofte med et teknisk spor.
- I loggen for opdateringen (*What it did* under *Update data*).

Hvad du gør:

1. Vent til næste opdatering. Gratis kilder er nogle gange nede et øjeblik.
2. Kør *Check + contact every source* under *Health checks*. Svarer kilden slet ikke, er det forbindelsen, en firewall eller kilden selv.
3. Er typen *parse*, svarede kilden, men i en ny form. Det kræver en rettelse i koden og retter sig ikke af sig selv.

Så længe kilden er inden for sin aldersgrænse, tæller dens seneste data stadig. Bliver den for gammel, får den status *stale* og holder op med at stemme i regimet. Se [Data og dækning](brugervejledning/data-og-daekning).

## Gult banner: "This data is N days old"

Øverst på dashboard-siderne står et gult banner, når rapporten er ældre end {{settings:coverage.max_age.prices}} dage. Klik *Update data* i banneret. Opdateringen tager typisk et par minutter, og siderne genindlæses, når den er færdig.

Kommer banneret igen lige efter en opdatering, er kurshentningen fejlet. Se loggen og siden [Operations](/ops).

## Et websted er sat på pause

Har et websted svaret "for mange forespørgsler" (HTTP 429) flere gange på kort tid, sætter radaren det på pause i en periode. Det ses som en gul boks på [Operations](/ops) og som `PAUSED` i `uv run radar ops`. Imens beholder de berørte kilder deres data.

Pausen ophører af sig selv. Du kan ophæve den med *Resume now*, men gentager problemet sig, bliver næste pause længere. Se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift#pauser-efter-for-mange-forespørgsler).

> **Tip:** Den hyppigste årsag er mange opslag på kort tid, fx en Discover-scanning lige efter en fuld opdatering. Vent, og prøv igen senere.

## Positivlisten mangler eller er gammel

Positivlisten (SKATs liste over aktiebaserede investeringsselskaber) bruges til at vise, om en ETF er på listen. Radaren henter den ikke selv:

1. Hent den aktuelle liste som Excel-fil fra skat.dk.
2. Gem den som `imports/positivliste.xlsx` (erstat den gamle).
3. Kør en opdatering.

Kun det seneste års ark tæller. Mangler filen, viser kolonnen "?" i stedet for yes/no. Sundhedstjekket og [Data & coverage](/data) advarer, når et nyt år er begyndt uden årets ark.

## Problemer med import af handler

| Problem | Hvad du gør |
|---|---|
| Formatet genkendes ikke | Vælg selv kolonnerne under *Columns*. Gem evt. filen som CSV fra Excel |
| *unverified format* | Bankens format (fx Danske Bank, Nordea, Saxo Bank eller Nordnet) er ikke afprøvet mod en rigtig eksport. Gennemse rækkerne grundigt |
| Symbol *not found* eller *please check* | Vælg det rigtige Yahoo-symbol eller skriv det med *other…*. Nordiske symboler har suffiks: `NOVO-B.CO`, `VOLV-B.ST` |
| *No Yahoo price data for …* | Symbolet findes ikke hos Yahoo. Ret det |
| Advarsel om kurs omkring 100 gange lukkekursen | Typisk pence mod pund (GBp/GBP) på London-børsen. Ret kursen, eller bekræft hvis den er rigtig |
| *This would sell more than was held* | Et salg uden tilsvarende køb i samme portefølje. Importér købet først, eller tjek portefølje og antal |
| *skipped: not a buy or sell* | Rækken er hverken køb eller salg (fx en overførsel). Kontantrækker kræver, at kolonnen *Cash amount (DKK)* er valgt |
| Rækker er *already stored* | De findes allerede; de springes over |
| Importen var forkert | Fortryd den under *Past imports* med *Undo* |

Se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).

## "Market Radar is already running"

Startscriptet eller `uv run radar serve` tjekker, om porten (8780) allerede er i brug. Er den det, antager radaren, at den allerede kører i et andet vindue, og åbner blot browseren. Brug den fane, der allerede er åben.

Bruger et andet program port 8780, vil appen ikke kunne åbne. Start så radaren på en anden port: `uv run radar serve --port 8781 --open`.

## Siden er tom: web/dist mangler

Appen er en bygget webside i `web/dist`. Mangler den, skriver `radar serve` *web/dist is missing* og kører kun API'et, og sundhedstjekket melder *Web app: fail*.

- Har du hentet en udgivelse (zip-fil), så pak den ud igen; den indeholder den byggede app.
- Arbejder du fra kildekoden, så byg den: `pnpm -C web install` og derefter `pnpm -C web build` (kræver Node 22 og pnpm).

## Browseren åbnede ikke

Gå selv til http://127.0.0.1:8780, mens det sorte vindue er åbent. Lukker du vinduet, stopper appen.

## Hvor ligger mine data?

Alt ligger i mappen, du pakkede Market Radar ud i, og intet sendes til andre end datakilderne:

| Mappe | Indhold | Kan genskabes? |
|---|---|---|
| `userdata/` | Dine handler, porteføljer, watchlist-ændringer og markedssyn (`radar.db`) | Nej. Tag backup |
| `userdata/backups/` | Automatiske sikkerhedskopier før hver import, fortrydelse, flytning og opgradering af databasen | – |
| `data/` | Hentede markedsdata, opdateringsloggen (`sources.json`) og driftsloggen (`ops.db`) | Ja, hentes igen |
| `reports/` | Rapporten til appen (`dashboard.json`) og `summary.json` til Claude-skills | Ja, bygges igen |
| `imports/` | Positivlisten og gamle Yahoo-importfiler | Positivlisten kan hentes igen |
| `notes/` | Din investorprofil og egne noter | Nej |
| `briefs/`, `research/`, `journal/` | Det, Claude-skills skriver | Nej |

> **Bemærk:** Vil du starte forfra med markedsdata, så slet `data/` og `reports/` og hent data igen. Dine handler og din watchlist i `userdata/` bliver liggende. Opdaterer du til en ny udgave af Market Radar, så kopiér de personlige mapper over i den nye.

### Gendan fra en sikkerhedskopi

Sikkerhedskopierne i `userdata/backups/` er kopier af databasen. Vil du gendanne én, så luk appen, kopiér den ønskede fil over `userdata/radar.db`, og start appen igen. Tag en kopi af den nuværende fil først.

## Ofte stillede spørgsmål

**Hvorfor er et tal tomt i stedet for 0?**
Fordi radaren ikke har data. Et manglende tal vises altid som manglende (–), aldrig som 0 eller et gæt.

**Hvorfor passer kursen ikke med min bank?**
Radaren bruger udbyttejusterede lukkekurser. Efter et udbytte ligger ældre kurser lavere end de handlede. Se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).

**Hvorfor følger radaren ikke en aktie, jeg slog op?**
Opslag henter kurser, men tilføjer ikke navnet til den daglige opdatering. Sæt det på watchlisten, så følger radaren det. Se [Tickerprofilen](brugervejledning/tickerprofil).

**Taler radaren med andre end datakilderne?**
Nej. Appen kan kun nås fra din egen computer, og forespørgslerne går til de kilder, du kan se på [Operations](/ops).
