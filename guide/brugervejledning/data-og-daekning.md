# Data og dækning

Siden [Data & coverage](/data) er radarens varedeklaration. Den siger, hvor hver aflæsning kommer fra, hvor gamle data er, om den seneste opdatering lykkedes, og hvad radaren slet ikke ser. Brug den, når et tal ser mærkeligt ud, når du vil vide, hvor meget du kan stole på regimet i dag, eller når en opdatering er gået galt.

Øverst på siden står knappen *Update data*, som henter nye data og bygger rapporten igen, præcis som `uv run radar run`. Mens den kører, ser du fremskridt og en log; du kan bruge appen imens, og siderne genindlæses, når den er færdig. Se [Data og opdatering](brugervejledning/data-og-opdatering).

## Kildetabellen

Tabellen *Sources* har én række pr. datakilde:

| Kolonne | Indhold |
|---|---|
| *Source* | Kildens navn, udbyder, om den er officiel (*official*) eller uofficiel (*unofficial*), og hvor tit den opdateres |
| *Feeds* | Hvilke dele af radaren den fodrer, fx *Regime, Rotation, Momentum* |
| *Coverage* | Hvor meget af det konfigurerede den dækker, fx hvor mange af de konfigurerede tickere der har kurser, med detaljer under |
| *As of* | Datoen for kildens seneste datapunkt |
| *Age (days)* | Alder i dage / grænsen for, hvornår den er forældet |
| *Status* | *ok*, *stale* (for gammel), *missing* (ingen data) eller *info* (kun oplysning, ingen grænse) |
| *Last update* | Tidspunktet for seneste vellykkede opdatering, eller i rødt: hvornår den fejlede og hvorfor, med seneste succes under |

Kolonnen *Last update* læses direkte fra opdateringsloggen (`data/sources.json`), hver gang du åbner siden. En kilde, der fejlede efter den seneste rapport, vises derfor med det samme, også selvom resten af tabellen stammer fra den seneste kørsel.

### Alder og grænser

Alderen tælles fra rapportens datadato (ACWI's seneste handelsdag), så en weekend ikke får alt til at se gammelt ud. For kurserne tælles fra i dag, fordi en opdatering, der bliver ved med at fejle, gør hele rapporten gammel.

Grænserne står i `config/settings.yaml` under `coverage.max_age`. Med de nuværende indstillinger:

| Kilde | Grænse (dage) |
|---|---|
| Kurser (Yahoo) | {{settings:coverage.max_age.prices}} |
| Amerikanske makroserier (FRED) | {{settings:coverage.max_age.fred}} |
| Futurespositionering (CFTC) | {{settings:coverage.max_age.cftc}} |
| Indtjeningsrevisioner (FactSet) | {{settings:coverage.max_age.factset}} |
| OECD's ledende indikatorer | {{settings:coverage.max_age.oecd}} |
| Analytikerkonsensus (Yahoo) | {{settings:coverage.max_age.analyst}} |
| Værdiansættelse, aktier og ETF'er | {{settings:coverage.max_age.valuation_stocks}} og {{settings:coverage.max_age.valuation_etfs}} |
| Shiller CAPE og risikopræmie (ERP) | {{settings:coverage.max_age.cape}} og {{settings:coverage.max_age.erp}} |
| Euroområdets renter (ECB) | {{settings:coverage.max_age.ecb}} |
| Put/call (CBOE) og AAII | {{settings:coverage.max_age.putcall}} og {{settings:coverage.max_age.aaii}} |
| Discover: navneliste og kurser | {{settings:coverage.max_age.discovery_universe}} og {{settings:coverage.max_age.discovery_prices}} |

En kilde, der er ældre end sin grænse, får status *stale* og holder op med at stemme i regimet. Den vises stadig, så du kan se, hvad den sidst sagde. Positivlisten er *stale*, når et nyt kalenderår er begyndt uden årets ark. Se [Indstillinger](brugervejledning/indstillinger).

### Når en kilde fejler

En kilde, der fejler eller svarer med noget, radaren ikke kan læse, beholder sine seneste data. Radaren gemmer aldrig et tomt resultat som en succes: et svar uden indhold er en fejl. Fejlen står i *Last update* og som en hændelse på siden [Operations](/ops); se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift). Næste opdatering prøver igen.

## Sådan bygges aflæsningerne

Afsnittet *How the readings are built* forklarer kort, hvad hver del af radaren bygger på:

- **Regime**: en afstemning blandt indikatorerne (trend, markedsbredde, volatilitet, kredit, renter, dollar, råvarer, OECD-cyklus, FactSet-revisioner). Kun risk-on- og risk-off-stemmer tæller: netto = (on − off) / (on + off); over +0,33 er risk-on, under −0,33 risk-off. Linjen siger også, hvor mange indikatorer der har friske data i dag. Se [Regime](brugervejledning/regime) og [Radarens afstemningsmodel](laerebog/afstemningsmodellen).
- **Rotation**: rotationsgrafen (RRG) af ugentlig relativ styrke mod ACWI, kun fra kurser.
- **Momentum**: gennemsnittet af percentilerne for 12-1-måneders, 6-måneders og 3-måneders afkast inden for hver regions aktieliste, kun fra kurser.
- **Levels**: et trailing stop på udbyttejusterede kurser plus Yahoos analytikerkursmål; konsensus ældre end {{settings:coverage.max_age.analyst}} dage bruges ikke.
- **Holdings returns**: samlet afkast i DKK (udbytte brutto, geninvesteret) mod en skyggeposition i ACWI med de samme pengestrømme.

## Farverne

Mange tal i radaren er graderede: de farves efter, hvor tæt de er på deres tærskler, i ni trin fra advarsel til gunstig.

| Trin | Farve | Betyder |
|---|---|---|
| −4 til −1 | Rød til lys orange | Advarsel, stærkest ved −4 |
| 0 | Grå | Neutral |
| +1 til +4 | Lysegrøn til grøn | Gunstig, stærkest ved +4 |

Ordet står altid ved siden af farven (fx *near overbought* eller *room to stop*), så farven aldrig er det eneste signal. Hold musen over et farvet ord for at se værdien og afstanden til nærmeste tærskel.

Envejs-risikomål som VIX, volatilitet (ATR %), beta og trængsel i positioneringen bruger kun den grå til røde halvdel: lav risiko er neutral, ikke "godt".

Tærsklerne står i `config/settings.yaml` under `gauges:` (og `regime:` for regimets rækker). En manglende værdi graderes ikke; den vises som manglende, aldrig som 0. Se [Indstillinger](brugervejledning/indstillinger#gauges-graderede-aflæsninger).

## Det, radaren ikke ser

Afsnittet *What the radar doesn't see* lister radarens blinde vinkler, så et "risk-on" aldrig læses som mere, end det er. Listen står i `config/settings.yaml` under `coverage.blind_spots` og kommer også med i `summary.json`, så Claude-skills tager højde for den. Lige nu handler den om:

- Værdiansættelse fra Yahoos uofficielle konsensus, og at radarens egen historik først bygges op fra første snapshot.
- Indtjeningsrevisioner: FactSet for S&P 500, ellers kun ændringer i Yahoos konsensus.
- Ingen fondsstrømme, fund manager-undersøgelse, short interest eller insiderhandler; sentiment er kun amerikansk.
- Makro og kredit er mest amerikansk; Europa ses gennem få serier.
- Selskabernes regnskaber ud over Yahoos opsummering modelleres ikke.
- Universet er et udsnit med overlevelsesbias.
- Discover er stadig Yahoo-data med støj blandt små selskaber.
- Nyheder og politik kommer kun ind via webresearch i `/market-brief`.
- Yahoo-data er uofficielle, og alle kurser er dagsluk.

## Manglende og forældede tickere

Nederst står to lister:

- **Missing tickers**: symboler i `config/universe.yaml`, som radaren slet ikke har kurser for. Symbolet kan være forkert eller ikke findes på Yahoo. Ret det i `universe.yaml`.
- **Stale tickers**: symboler uden ny kurs i mere end {{settings:coverage.max_age.prices}} dage. Papiret kan være afnoteret eller suspenderet.

Klik på et symbol for at åbne dets [tickerprofil](brugervejledning/tickerprofil).

> **Tip:** Mangler et enkelt symbol en dag, er det oftest Yahoo, der har et hul. Næste opdatering retter det normalt. Bliver det ved, så tjek symbolet på finance.yahoo.com.
