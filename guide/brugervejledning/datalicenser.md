# Datakilder og licenser

Market Radars **kode** er frit tilgængelig under MIT-licensen. De **markedsdata**, appen henter, er ikke omfattet af den licens. De tilhører kilderne, og hver kilde har sine egne vilkår. Langt det meste må kun bruges **personligt og ikke-kommercielt**.

Dette kapitel er et kort, letlæst overblik. Den fulde engelske version står i filen `DATA_LICENSE.md` i programmappen. Ingen af dem er juridisk rådgivning, og kilderne kan ændre deres vilkår når som helst. Kildens egne vilkår gælder altid.

## Kort fortalt

**Det må du:**

- Køre Market Radar på din egen computer til din egen investering, analyse og læring.
- Dele **koden**: kopiere, ændre og videregive den under MIT-licensen.
- Vise et skærmbillede eller nævne enkelte tal privat, fx for en ven.
- Skrive dine egne konklusioner (briefs, researchnotater, journal) på grundlag af det, radaren viser.

**Det kræver en særskilt datalicens:**

- **At gøre Market Radar tilgængelig for andre som hjemmeside eller tjeneste.** Så leverer du Yahoo Finance-data og andre licenserede data videre til andre, og det forbyder kildernes vilkår.
- **Kommerciel brug:** betalte produkter, nyhedsbreve, kunderapporter, rådgivning eller andet, du får betaling for, og som bygger på de hentede data.
- **At videregive data:** offentliggøre eller sælge cache-mappen (de hentede markedsdata og rapporterne), historikken i datamappen, eksporterede tabeller eller dashboardets JSON, eller lægge hentede data med i en kopi af appen.
- **At bruge kilderne i et andet produkt**, eller at hente fra en fælles server på vegne af mange brugere.

> **Bemærk:** Den tilsigtede måde at dele Market Radar på er, at hver bruger kører sin egen kopi og selv henter sine data til personlig brug. Sådan fungerer de udgivne versioner.

## Kilde for kilde

| Kilde | Bruges til | Personlig brug | Hosting eller videregivelse |
|---|---|---|---|
| **Yahoo Finance** (via det uofficielle bibliotek `yfinance`) | Alle kurser (historik fra før din første handel; også de sektor- og lande-ETF'er, der står i stedet for ACWI's segmenter i attributionen), tickerdetaljer, analytikerestimater, regnskabs- og udbyttedatoer for beholdninger og watchlist (gemt som læst, så flyttede datoer kan ses), screener (*Discover* og værdiansættelse), fonddata (også til fondsklasserne i porteføljens røntgen), regnskaber (resultatopgørelse, pengestrøm, balance), søgning | Ja | **Nej.** Kun personlig, ikke-kommerciel brug; Yahoo licenserer selv data fra børser og dataleverandører |
| **FactSet** Earnings Insight (offentlig PDF) | Forward P/E, yield gap | Ja | **Nej.** Ophavsretligt beskyttet analyse |
| **State Street (SSGA)**, SPY-beholdninger | S&P 500-medlemmer | Ja | **Nej.** Indeksmedlemmer tilhører S&P Dow Jones Indices |
| **iShares (BlackRock)**, fondsbeholdninger | ETF-gennemsyn, *Discover*-universet (medlemmerne af STOXX Europe 600 og S&P 500), MSCI ACWI's vægte på sektor, region og valuta til porteføljeforslag og porteføljens røntgen (via MSCI ACWI UCITS-fonden, SSAC), og en ugentlig optegnelse af de vægte (kun summer, aldrig aktielisten) til attributionen, da iShares ikke viser tidligere beholdninger | Ja | **Nej.** Indeksmedlemmer tilhører indeksudbyderne (MSCI, STOXX, S&P Dow Jones Indices m.fl.) |
| **AAII** Sentiment Survey | Sentiment | Ja | **Nej.** Ophavsret hos AAII |
| **Cboe**, put/call-forhold | Sentiment | Ja | **Nej.** Cboes markedsdata |
| **FRED**, serier fra tredjeparter (fx `BAMLH0A0HYM2`, ICE BofA high yield-spænd) | Kreditspænd | Ja | **Nej.** Ophavsret hos seriens ejer; ICE begrænser videregivelse |
| **FRED**, amerikanske offentlige serier (fx `DGS10`, `T10Y2Y`, `DGS3MO`, `DEXDNUS`, `USREC`) | Renter, rentekurve, dollar; dollarkursen i kroner siden 1971 og amerikanske recessionsmåneder (NBER's datering) til testen over årtier | Ja | Som regel ja, med kildeangivelse |
| **multpl.com** | Shiller CAPE | Ja | Uklart: spørg, eller beregn CAPE selv |
| **Aswath Damodaran** (NYU Stern) | Implicit risikopræmie | Ja | Ja, med kildeangivelse |
| **Kenneth R. French Data Library** (Dartmouth) | Lange månedsserier til `radar study longrun`: amerikanske brancheporteføljer (49 brancher) og momentumdeciler, Fama-French- og momentumfaktorerne (USA siden 1926, udviklede markeder og Europa siden 1990); daglige udviklede fem faktorer og momentum til faktorregressionen af dine porteføljer (attribution); resultaterne af den lange test vises på siden *Evidence* | Ja | **Nej** (selve dataene). Frit delte forskningsdata med ophavsret hos Fama og French; henvis til biblioteket i stedet |
| **JKP Global Factor Data** (Jensen, Kelly og Pedersen, jkpfactors.com) | Lange månedsserier til `radar study longrun`: markedsafkastet pr. land (udviklede markeder siden 1986) og faktortemaer (momentum, værdi, kvalitet); porteføljer af aktier i tredjedele efter momentum, FCF yield, EBITDA/EV, nettoudlodning og kvalitet, som porteføljeforslagenes forventede merafkast trækkes mod; testens resultater på siden *Evidence* | Ja | Kun ikke-kommercielt og med kildeangivelse (CC BY-NC 4.0): Jensen, Kelly og Pedersen, "Is There a Replication Crisis in Finance?", *Journal of Finance*, 2023 |
| **ECB Data Portal** | Euroområdets renter | Ja | Ja, med kildeangivelse |
| **OECD** | Ledende indikatorer (CLI) | Ja | Ja, med kildeangivelse (CC BY 4.0) |
| **CFTC** | Futurespositionering (COT) | Ja | Ja (offentligt amerikansk data) |
| **SEC EDGAR** (XBRL company facts) | Amerikanske selskabers regnskaber fra 10-K og 10-Q, med indleveringsdato; testene af kvalitets- og værdiscoren, hvis resultater siden *Evidence* viser | Ja | Ja (offentligt amerikansk data). SEC beder om højst 10 forespørgsler i sekundet og en kontakt-e-mail i hver forespørgsel, som du selv angiver på siden *Data* |
| **SKAT**, positivlisten | Positivliste-status | Ja | Ja (offentlige danske data) |
| **Saxo, Danske Bank**, offentlige prislister (skrevet af i hånden i `config/fee_presets.yaml` med dato og kilde; intet hentes) | Skabeloner til kurtage-estimatet | Ja | Ja, med kilde og dato |

Testdataene i `tests/fixtures/` er små prøver i hver kildes format, så programmets læsere kan testes uden net. Fra de åbne kilder er det beskårne, ægte svar; fra de andre kun en håndfuld tal i kildens opstilling, og al tekst (FactSets rapporttekst, Yahoos virksomhedsbeskrivelser) er opdigtet. De er ikke en kopi af kildernes data og skal ikke bruges som data.

Benchmarket bygger på kurserne for iShares MSCI ACWI-ETF'en fra Yahoo, ikke på MSCI's egne indeksdata. "MSCI" og "ACWI" er MSCI's varemærker. Market Radar er hverken tilknyttet eller godkendt af MSCI eller af nogen anden kilde i tabellen.

## Praktiske regler for din kopi

- Hold cache-mappen, `history/` og `exports/` i datamappen og dine backupper for dig selv. De kommer aldrig med i git; læg dem heller ikke ud andre steder. En backup indeholder historikken, som er bygget af hentede data.
- En eksport fra *Export my data* eller `radar export` indeholder kun dine egne data (porteføljer, handler, markedssyn, watchlist og dokumenter), ingen markedsdata. Den indeholder til gengæld dine beholdninger, så del den kun med nogen, du stoler på.
- Tjekket for nye versioner (slået fra, til du slår det til; se [Dine data, backup og opdatering](brugervejledning/dine-data#tjek-for-nye-versioner)) spørger GitHub (`api.github.com`) om den nyeste udgivelse. Det er ikke en datakilde: svaret er kun et versionsnummer og et link, og der sendes intet om dig.
- Gør ikke `radar serve` tilgængelig på internettet eller dit netværk, så andre kan bruge den. Den lytter med vilje kun på `127.0.0.1`, altså din egen computer.
- Respekter kildernes grænser. Radaren doserer sine forespørgsler og holder pause med en kilde, der beder om det (se [Drift](brugervejledning/drift)). Fjern ikke den begrænsning.
- Angiv kilden, når du nævner et tal i noget, du offentliggør.
- Briefens lytteversion (`/market-brief podcast`) er til din egen NotebookLM-notesbog, så du selv kan lytte til den. Teksten sendes til Google, så hold notesbogen og den lydfil, NotebookLM laver, private. Deler eller offentliggør du dem, videregiver du de data, de bygger på (se [Månedsbriefen](brugervejledning/maanedsbrief#som-podcast-notebooklm)).

## Hvis du vil tilbyde radaren til andre

En hostet udgave, som andre logger ind på, kræver som minimum:

1. **En licenseret dataleverandør** i stedet for Yahoo, med et abonnement, der udtrykkeligt tillader visning for tredjepart eller videregivelse for de børser, du har brug for (USA, Norden, Europa, Asien). Dagslukkekurser er overkommelige. Analytikerestimater, revisioner, nøgletal til screeneren og fondsbeholdninger er de dyre dele og må måske udelades.
2. **Tilladelse eller erstatning** for FactSet, SSGA, iShares og indeksmedlemmer, AAII, Cboe og FRED-serier fra tredjeparter. Ellers må de funktioner udelades.
3. **Kildeangivelse** for de åbne kilder (ECB, OECD, FRED, Damodaran).

Det rejser også spørgsmål, der ligger uden for datalicenser: **finansiel regulering** (scorer og vurderinger vist til andre kan tælle som investeringsanbefalinger efter EU's markedsmisbrugsforordning (MAR) eller som rådgivning, der kræver tilladelse fra Finanstilsynet) og **GDPR**, fordi du ville opbevare andres porteføljer.
