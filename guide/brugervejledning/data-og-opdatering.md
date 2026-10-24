# Data og opdatering

Market Radar regner alt ud fra data, der ligger lokalt på din computer. De bliver ikke opdateret af sig selv: du beder om en opdatering, når du vil have friske tal. Dette kapitel forklarer, hvordan du gør det, hvad der sker undervejs, og hvad radaren gør, når en kilde fejler.

## Opdater med knappen Update data

Den nemmeste vej er knappen *Update data*. Den findes tre steder:

- På siden [Data & coverage](/data), øverst under sideoverskriften.
- I det gule banner, der dukker op på markedssiderne, når data er for gamle (se [Advarsler om gamle data](brugervejledning/data-og-opdatering#advarsler-om-gamle-data)).
- På velkomstsiden ved første start, hvor den hedder *Download market data*.

Når du klikker, starter den samme opdatering som `radar run` i terminalen. Undervejs viser panelet:

- Knappen skifter til *Updating…*, og ved siden af står fremskridtet, fx "Downloading prices: 350 of 700 tickers (50%)".
- En bjælke viser, hvor langt kursdownloaden er.
- *What it did (N lines)* folder loggen ud: én linje pr. trin, med hvad der blev hentet, eller hvad der fejlede.

Du kan bruge appen imens. Når opdateringen er færdig, står der *Updated* med tidspunktet, og alle sider henter deres data igen af sig selv. Der kan kun køre én opdatering ad gangen, også på tværs af appen og terminalen: starter du `radar update` eller `radar run`, mens appen opdaterer (eller omvendt), stopper den nye med det samme med beskeden *an update is already running*. Det samme gælder Discover-scanningen. At slå en ticker op i appen virker hele tiden.

Stopper opdateringen helt, står der *Update stopped:* efterfulgt af fejlen. Det sker sjældent, fordi de enkelte kilder fejler hver for sig uden at stoppe resten (se [Når en kilde fejler](brugervejledning/data-og-opdatering#når-en-kilde-fejler)).

## Hvad en opdatering henter

En opdatering har to halvdele: først hentes data, derefter bygges dashboardet (`dashboard.json` i cache-mappen), som siderne viser.

### Hentning
Trinene køres i denne rækkefølge, og hvert trin logges for sig:

| Trin | Kilde | Hyppighed hos kilden |
|---|---|---|
| Kurser | Yahoo Finance (justeret for udbytter og splits) | Dagligt, dagslukkekurser |
| Navne og sektorer | Yahoo Finance | Hentes én gang og gemmes |
| Makro | FRED (renter, kreditspænd, dollar) | Dagligt til ugentligt |
| CFTC-positionering | CFTC Commitments of Traders | Ugentligt |
| Ledende indikatorer | OECD CLI | Månedligt, ca. 2 måneders forsinkelse |
| Indtjeningsrevisioner | FactSet Earnings Insight | Ugentligt |
| Analytikerkursmål | Yahoo (kun beholdninger og watchlist) | Hentes igen efter {{settings:analyst.max_age_days}} dage |
| Euroområdets renter | ECB | Dagligt |
| CAPE og risikopræmie | multpl.com og Damodaran | Månedligt |
| Put/call og AAII | CBOE og AAII | Dagligt og ugentligt |
| Værdiansættelse | Yahoo (screener og fonddata) | Et nyt øjebliksbillede, når det seneste er over {{settings:valuation.snapshot_days}} dage gammelt |

Kurserne hentes inkrementelt: kun de nye dage. Første gang hentes {{settings:history_years}} års historik for hver ticker. Opdager radaren, at et udbytte eller en split har ændret den justerede historik, henter den hele historikken for den ticker igen. En ny, fuld historik erstatter aldrig mere, end den bringer: starter den senere eller slutter den tidligere end den, radaren allerede havde, beholdes de gemte dage uden for den. Er historikken justeret på ny (et udbytte eller en split), flyttes de gemte dage over på den nye justering. Starter Yahoos historik senere end den gemte, står det i loggen, og næste opdatering spørger igen.

Efter kurserne tjekker radaren, om hver ticker har en kurs for benchmarkets seneste handelsdag. De tickere, der mangler den, hentes én gang til. Mangler de den stadig, står de i loggen, fx "Prices: … 3 without a bar for 2026-10-14 (exchange holiday, or not on Yahoo yet): …". De står også på siden [Operations](/ops) og under *Without the last session* på *Data & coverage*.

### Rapporten
Derefter regner radaren regime, rotation, momentum, positionering og dækning ud og skriver resultatet til `dashboard.json` (som siderne læser) og `summary.json` (som Claude Code-kommandoerne læser) i cache-mappens `reports/`. Samtidig gemmes et øjebliksbillede af rangeringerne i `history/snapshots/` i datamappen. Det er dem, der gør det muligt at vise ændring i rang og nye navne siden sidst. Et øjebliksbillede får datoen for de data, det bygger på (ACWI's seneste handelsdag), ikke datoen for kørslen. En kørsel lørdag gemmes altså under fredag, og en kørsel på uændrede data (fx når opdateringen er fejlet) gemmer ikke et nyt.

Rapporten bygges én gang pr. opdatering og ikke hver gang, du åbner en side. Den tager omkring et halvt minut, og øjebliksbillederne og A/B-testen skal kun køre én gang pr. opdatering. Det, der afhænger af dine egne ændringer, regnes til gengæld ud med det samme: *Holdings & watchlist*, dine valg i regimeafstemningen, markedssyn og datakildernes seneste status.

## Byg aflæsningerne igen

Rapporten husker, hvilke filer den blev bygget af, og hvilken version af appen der byggede den. Ændrer en af filerne sig bagefter, viser markedssiderne et banner: *Data has changed since these readings were built* med de ændrede kilder i parentes og knappen *Rebuild the readings*. Det sker fx, når du har kørt `radar update` i terminalen uden `radar report`, har hentet regnskaber med `radar fundamentals`, eller har ændret `config/settings.yaml` eller `config/universe.yaml`. Knappen bygger rapporten igen ud fra de data, der allerede ligger lokalt. Den henter intet og tager omkring et halvt minut. Knappen findes også altid på siden [Data & coverage](/data), under *Update data*.

Er rapporten bygget af en ældre version af appen, bygger appen den selv igen, når den starter. Imens viser siderne den gamle rapport med beskeden *These readings were built by an older version of the app* og *Rebuilding…* ved knappen.

Du behøver ikke bygge igen efter ændringer i dine porteføljer, din watchlist, dine markedssyn eller dine valg i regimeafstemningen: dem viser siderne med det samme. Mens *Update data* kører, vises banneret ikke, fordi opdateringen selv bygger rapporten til sidst.

Der kan kun bygges én rapport ad gangen, også på tværs af appen og terminalen. Starter du `radar report`, mens appen bygger (eller omvendt), stopper den nye med beskeden *the readings are already being built*. En opdatering, der er færdig med at hente, venter i stedet på, at den igangværende bygning bliver færdig.

## Fra terminalen

Foretrækker du terminalen, gør disse kommandoer det samme som knappen:

```
uv run radar run       # hent data og byg dashboardet
uv run radar update    # kun hentningen
uv run radar report    # kun rapporten, ud fra de data, der allerede ligger lokalt
```

`radar report` er nyttig, hvis du har ændret en indstilling i `config/settings.yaml` og vil se virkningen uden at hente noget nyt. Den gør det samme som knappen *Rebuild the readings* (se [Byg aflæsningerne igen](brugervejledning/data-og-opdatering#byg-aflæsningerne-igen)). `radar update --refresh-constituents` henter desuden listen over S&P 500-selskaber igen (ellers sker det automatisk efter {{settings:constituents_max_age_days}} dage). Se [Kommandolinjen](brugervejledning/kommandolinjen).

## Discover-scanningen er separat

Siden [Discover](/discover) bygger på en meget bredere liste af navne (nordiske og europæiske aktier, aktierne i S&P 500 og UCITS-ETF'er fra positivlisten, i alt flere tusinde). Den scanning ville gøre den daglige opdatering langsom, så den kører for sig:

- Første gang starter du den på Discover-siden med *Run the first discovery scan*. Den slår omkring 3.500 navne op og tager et stykke tid.
- Senere starter du den med *Scan again* på samme side, eller med `uv run radar discover` i terminalen. Den tager nogle minutter.
- Listen over navne bygges igen cirka månedligt; kurserne hentes ved hver scanning.
- Scanningen rører ikke radarens øvrige data, og *Update data* kører ikke scanningen.

Kør den cirka en gang om ugen. Scanningen regnes for forældet efter {{settings:coverage.max_age.discovery_prices}} dage. Se [Discover](brugervejledning/discover).

## Hvor ofte skal du opdatere?

Det afhænger af, hvordan du bruger radaren:

- **Ugentligt overblik:** opdater, før du sætter dig, fx en gang om ugen. Det passer med, at rotationsgrafen bygger på ugedata, og at flere kilder kun opdateres ugentligt.
- **Aktiv opfølgning på beholdninger:** opdater dagligt eller et par gange om ugen, så stop og kursmål regnes ud fra friske kurser.
- **Discover:** cirka ugentligt.

Det giver ikke mening at opdatere flere gange samme dag: kurserne er dagslukkekurser, og de fleste andre kilder ændrer sig langsommere. Opdaterer du om formiddagen dansk tid, har du gårsdagens amerikanske lukkekurser.

## Advarsler om gamle data

Hver side viser øverst, hvilken dato data er fra ("Data as of …"), og hvornår dashboardet blev bygget ("built …"). Er kursdata mere end {{settings:coverage.max_age.prices}} dage gamle, viser siderne et gult banner: *This data is N days old. Update it before acting on it.* med en *Update data*-knap ved siden af.

Det samme princip gælder for hver enkelt kilde. Hver kilde har en maksimal alder i `config/settings.yaml` (afsnittet `coverage.max_age`), fx:

| Kilde | Maksimal alder (dage) |
|---|---|
| Kurser | {{settings:coverage.max_age.prices}} |
| FRED | {{settings:coverage.max_age.fred}} |
| CFTC | {{settings:coverage.max_age.cftc}} |
| FactSet | {{settings:coverage.max_age.factset}} |
| OECD CLI | {{settings:coverage.max_age.oecd}} |
| CAPE | {{settings:coverage.max_age.cape}} |

Alderen tælles fra datadatoen for dashboardet. En kilde, der er ældre end sin grænse, får status *stale*. Dens aflæsning vises stadig, men en indikator med *stale* data tæller ikke med i regimeafstemningen. Siden *Data & coverage* viser alder og grænse for hver kilde i kolonnen *Age (days)*, fx "9 / 14". Se [Data og dækning](brugervejledning/data-og-daekning).

## Når en kilde fejler

Gratis kilder fejler af og til: en side ændrer layout, en server svarer ikke, eller Yahoo beder om en pause. Radaren håndterer det sådan:

- **Kilden beholder sine seneste data.** En fejl overskriver aldrig det, der allerede ligger i cachen. Resten af opdateringen fortsætter.
- **Fejlen bliver vist.** I loggen står fx "CFTC positioning: FAILED (…); using cached data." På *Data & coverage* viser kolonnen *Last update* "failed" med dato og fejl samt den seneste vellykkede opdatering. På *Regime* står "last update failed" i dækningslinjen under afstemningen.
- **En kilde, der svarer med noget tomt, fejler højlydt.** Hvis en kilde svarer, men svaret ikke kan læses til noget brugbart, regnes det som en fejl, og cachen bevares. Radaren erstatter aldrig data med nuller.
- **Et svar med mindre end det gemte erstatter det ikke.** Mangler en serie i svaret, beholdes de gemte værdier, og loggen siger det (fx "kept the stored USA"). Slutter en serie tidligere end den gemte, beholdes hele den gemte fil. Får et nyt ETF-snapshot fonddata for for få ETF'er (under {{settings:valuation.etf_min_share}} af det seneste snapshots), beholdes det seneste.
- **En kilde, der fejler midtvejs, beholder det, den nåede.** Put/call hentes dag for dag. Fejler en dag, gemmes dagene før den, og opdateringen meldes som fejlet med det, der blev gemt. En dag, CBOE ikke havde endnu, hentes igen ved de næste opdateringer.
- **Bliver fejlen ved, ældes data.** Efter kildens maksimale alder bliver den *stale* og holder op med at tælle.

Gentagne fejl og sider, der er sat på pause, kan du følge på siden [Operations](/ops); se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift).

> **Tip:** Mangler en enkelt ticker kurser, er det oftest Yahoo, der har et hul den dag. Næste opdatering løser det som regel. *Data & coverage* lister tickers uden kurser (*Missing tickers*), tickers uden nye kurser (*Stale tickers*) og tickers, der mangler den seneste handelsdag (*Without the last session*).

### Tickers uden for radarens lister
Søger du på en ticker, som radaren ikke følger, hentes den første gang, du åbner den (det tager omkring 10 sekunder). Den gemmes, men kommer ikke med i den daglige opdatering. Sætter du den på din watchlist, eller køber du den, kommer den med.

## Hvor dine data ligger

Market Radar skelner skarpt mellem data, der kan hentes igen, og data, der kun findes hos dig. De ligger i hver sin mappe, uden for programmappen:

- **Datamappen** (standard `Market Radar` i din brugermappe) holder dine data: porteføljer, handler, markedssyn og watchlist (`radar.db`), noter, briefs, research, journal, eksporter og filer fra din bank. Undermappen `history/` holder det, radaren har samlet op over tid og ikke kan hente igen, fx rangsnapshots og ugentlige P/E-snapshots. Datamappen tages der automatisk backup af.
- **Cache-mappen** holder de hentede markedsdata og de byggede rapporter. Den kan altid hentes igen.

Hvor mapperne ligger på Windows, Mac og Linux, og hvordan backup, eksport og opdatering virker, står i [Dine data, backup og opdatering](brugervejledning/dine-data). Siden [Data & coverage](/data) viser det under *Your data*, og `uv run radar paths` i terminalen.

Vil du starte forfra med markedsdata, så luk appen, slet cache-mappen og hent igen. Dine data og historikken bliver liggende.
