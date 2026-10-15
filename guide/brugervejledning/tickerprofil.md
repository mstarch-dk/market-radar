# Tickerprofilen

Tickerprofilen er radarens side om ét enkelt værdipapir: en aktie, en ETF eller et andet symbol, som Yahoo Finance kender. Du når den ved at søge i søgefeltet øverst (tast `/` for at hoppe derhen), ved at klikke på et tickersymbol i en hvilken som helst tabel, eller direkte på adressen `/ticker/<SYMBOL>`, fx `/ticker/NOVO-B.CO`.

Siden samler det, du ellers skulle hente fra mange faner: kursgraf, momentum, tekniske indikatorer, et regelbaseret stop og kursmål, risiko mod verdensindekset, analytikernes konsensus, værdiansættelse, fondsgennemlysning, peers og hvordan navnet passer med dine egne markedssyn.

## Sidehovedet

Øverst står navn, symbol, børs, type, sektor og branche. Mærkerne under navnet fortæller, hvor navnet står i forhold til radaren og dig:

| Mærke | Betyder |
|---|---|
| *You hold this* / *On your watchlist* / *Sold earlier* | Din status: beholdning, watchlist eller solgt tidligere |
| *tracked by the radar* | Navnet er med i den daglige opdatering |
| *not tracked* | Kurserne hentes ved opslag, ikke i den daglige opdatering |
| *… stock group* / *ETF group: …* | Hvilken aktiegruppe eller ETF-gruppe i `config/universe.yaml` navnet hører til |
| *positive list: yes/no* | Status på positivlisten (SKATs liste over aktiebaserede investeringsselskaber) |
| *regime …* | Radarens aktuelle regime (risk-on, risk-off eller blandet) |

Til højre står seneste kurs, dagens ændring og datoen for den seneste lukkekurs. Knappen *Add to watchlist* (☆) sætter navnet på din watchlist, og *Remove from watchlist* (★) tager det af igen. En beholdning har ingen knap: den kommer fra dine handler. Knappen *Refresh Yahoo data* henter nøgletal og estimater fra Yahoo med det samme i stedet for at bruge den gemte kopi.

## Overblikket

Lige under sidehovedet står en række felter med de tal, du typisk vil læse først. Feltets farve følger aflæsningen: grøn trækker i den gunstige retning, orange til rød er en advarsel, og gråt er neutralt.

| Felt | Viser |
|---|---|
| *Momentum score* | Momentumscoren (0–100) i stort, med ord, en skala med tærsklerne og rangen i aktiegruppen. Se [Radarens momentumscore](laerebog/momentumscore) |
| *Trend* | Om trenden er intakt (*intact* / *not intact*), og om kursen ligger over eller under 50- og 200-dages gennemsnittet |
| *3M vs ACWI* | Afkastet over 3 måneder minus ACWI's, i procentpoint, og selve 3-måneders afkastet |
| *From 52w high* | Afstanden til 52-ugers højeste lukkekurs |
| *RSI 14* | RSI med ord (fx overkøbt) |
| *Analyst upside* | Afstanden fra kursen op til analytikernes middelkursmål (kun aktier, og kun når konsensus ikke er for gammel) |
| *Next earnings* | Antal dage til næste regnskab, når datoen kendes |

Mangler et tal, står der en tankestreg, aldrig 0. Detaljerne står i kortene længere nede.

### Watch-outs og noter

Under overblikket kan der stå en linje *Watch-outs:*. Det er de graderede aflæsninger, der står på et af de to mest advarende trin (orange til rød), fx et RSI i overkøbt område eller en kurs tæt på stoppet. Karaktertræk som beta og det daglige udsving (ATR %) kommer aldrig med, og det hypotetiske stop og kursmål for et navn, du ikke ejer, heller ikke. Under watch-outs står eventuelle noter om manglende data.

## Kursgrafen

Grafen har op til tre ruder, der følger hinanden:

- **Kurs** med 50- og 200-dages glidende gennemsnit, Bollinger-bånd (prikket) og handelsvolumen nederst. Vandrette linjer viser *Stop* (rød, stiplet), *Take-profit* (grøn, stiplet) og analytikernes middelkursmål, *Analyst mean* (prikket), når det ikke allerede er kursmålet.
- **RSI 14** med de prikkede linjer ved 30 og 70.
- **Relativ styrke mod ACWI**, hvor 100 er starten af den valgte periode. En stigende linje betyder, at navnet klarer sig bedre end verdensindekset i perioden.

Knapperne *1W*, *1M*, *3M*, *6M*, *YTD*, *1Y*, *3Y* og *5Y* skifter periode, og grafen husker dit valg. *YTD* regnes fra sidste lukkekurs i det forrige år. Radaren gemmer {{settings:history_years}} års kurser, så *5Y* også har 200-dages gennemsnittet med fra første dag. Er historikken kortere end perioden, vises det hele, og linjen over grafen siger, hvor mange år der er gemt.

Linjen over grafen opsummerer perioden: afkastet, ACWI's afkast over de samme handelsdage, forskellen i procentpoint, laveste og højeste lukkekurs og startdatoen. Tallene regnes på samme måde som i *Price development*, så 1M, YTD og 1Y stemmer med tabellen.

Klik på en post i forklaringen (50d, 200d, Bollinger, Volume, stop- og kursmålslinjerne, *RSI pane*, *vs ACWI pane*) for at skjule eller vise den; en skjult post er overstreget. Bollinger-båndene er skjult fra start. Knappen *log* skifter til logaritmisk kursakse, hvor lige store procentvise udsving fylder lige meget; det gør lange perioder med store stigninger lettere at læse. Valgene huskes i din browser.

Musehjulet ruller siden, ikke grafen; du zoomer med knapperne, ved at trække eller med to fingre. Holder du musen over en dag, viser aflæsningen over grafen lukkekurs, 50- og 200-dages gennemsnit, RSI, relativ styrke og volumen for netop den handelsdag. Kurserne er udbyttejusterede, og en dag uden data fra Yahoo vises som et hul, ikke som en flad dag. Se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).

## Kortene

### Price development

Tabellen viser afkast over 1 uge, 1, 3 og 6 måneder, år til dato og 1 år: i handelsvalutaen, i DKK (når valutaen ikke er DKK), og som forskel i procentpoint mod ACWI og mod navnets sektor-ETF. Sektor-ETF'en vælges efter Yahoos sektor og radarens region i `config/universe.yaml`; mangler der en, står det under tabellen. 3M og 6M står med fed, fordi det er momentumhorisonten. Nederst står 52-ugers høj og lav på lukkekurser (ikke intradag) og afstanden til dem.

### Momentum & trend

Momentumscoren (0–100) med rang i gruppen, afkast over 3 og 6 måneder, 12-1-måneders afkast (springer den seneste måned over), kursen mod 50- og 200-dages gennemsnit, om trenden er intakt (50-dages over et stigende 200-dages), afstanden til 52-ugers høj og volumen de seneste 20 dage mod de seneste 6 måneder. Linjen under kortet siger, hvad scoren er beregnet mod. Se [Radarens momentumscore](laerebog/momentumscore).

### Technicals

RSI 14, MACD-histogrammet (12/26/9), Bollinger %B, ATR 14 (det typiske daglige udsving, også som procent af kursen), volatilitet over 3 måneder (annualiseret), største fald det seneste år og beta/korrelation mod ACWI på ugedata over et år. Hver aflæsning har et farvet ord; hold musen over det for at se tærsklen. Se [Tekniske indikatorer](laerebog/tekniske-indikatorer).

### Stop / take-profit (rule)

Et mekanisk trailing stop (glidende stop) og en take-profit (kursmål), beregnet efter en fast regel:

- **Stop** = højeste lukkekurs siden køb − k × ATR({{settings:stops.atr_days}}). For et navn, du ikke ejer, bruges den højeste lukkekurs over de seneste {{settings:stops.info_anchor_days}} handelsdage. Er stoppet blevet brudt siden, glider det fra den højeste kurs efter bruddet.
- **k** starter på {{settings:stops.k_base}} og flyttes ±{{settings:stops.k_step}} af hvert signal (stærk momentum, brudt trend, tabt momentum, en kurs mere end {{settings:stops.extended_vs_sma50|pct}} over 50-dages gennemsnittet, regimet og analytikerne), inden for {{settings:stops.k_min}}–{{settings:stops.k_max}}.
- **Take-profit** er den laveste af kursen + {{settings:stops.reward_risk}} × stopbredden og analytikernes middelkursmål (kræver mindst {{settings:stops.min_analysts}} analytikere). Ligger kursen over det højeste analytikerkursmål, gives der intet kursmål.

Listen under tallene forklarer hvert signal linje for linje (+ giver mere plads, − strammer). Mærket *near stop* eller *near target* betyder, at kursen er inden for {{settings:stops.near_atr}} ATR af niveauet; *stop hit* betyder, at den har lukket på eller under stoppet. Det er en regel til eftertanke, ikke et råd. Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

### Risk vs ACWI (DKK, weekly)

Risikostatistik på hele uger i DKK over 1 og 3 år (antallet af uger står i overskriften): annualiseret afkast, volatilitet, beta med standardfejl og R², downside-beta, alfa med t-værdi, aktiespecifik volatilitet, Sharpe/Sortino og største fald med antal uger under toppen. Med færre end {{settings:risk.min_weeks}} uger vises intet tal, aldrig et gæt.

*Factor tilts* viser, hvor meget af bevægelserne der forklares af faktor-ETF'er ({{settings:risk.factors}}) ud over markedet; fremhævede mærker har |t| ≥ 2. Linjen *Size at 1% risk* er den andel af porteføljen, hvor et fald til regelstoppet koster {{settings:risk.budget|pct}} af porteføljen.

> **Bemærk:** Etårs-beta er støjende. Sammenlign 1 og 3 år, og læs standardfejlen, før du stoler på nogen af dem. Se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

### Analysts & estimates (aktier)

Øverst den aktuelle kurs med dagens ændring, så du kan holde den op mod middelkursmålet, med afstanden fra kursen, konsensus (1 = strong buy, 5 = strong sell) med antal analytikere, ændringen i middelkursmålet over 30 dage og et bånd fra laveste til højeste kursmål, hvor kursen er markeret med *now*. Derunder næste regnskabsdato, eventuel ex-udbyttedag, anbefalinger pr. måned og EPS-estimater med ændringer over 30 og 90 dage og antal op- og nedjusteringer. Er konsensus ældre end grænsen, står det, og kursmålene bruges ikke.

### Valuation & fundamentals (aktier)

Øverst radarens ugentlige snapshot: P/E på næste års forventede indtjening, P/E mod sektorens median blandt navnets peers, ændringen i EPS-estimatet over 4 og 12 uger og P/E over de gemte uger. Revisioner kræver, at historikken er bygget op. Under det Yahoos profil: markedsværdi, P/E, PEG, EV/EBITDA, kurs/indre værdi, marginer, vækst, egenkapitalforrentning, gæld, udbytte, beta og short interest. Usandsynlige tal smides væk med en note. Se [Relativ værdiansættelse](laerebog/relativ-vaerdiansaettelse).

### Fund look-through (ETF'er)

For en fond vises i stedet omkostninger, fondsstørrelse, udbyder, positivliste-status med ISIN, en UCITS-version (hvis radaren kender en), fondens P/E mod ACWI, sektorfordeling og de største beholdninger. Ejer du en af de største beholdninger direkte, står der *you hold* ved den.

### Sector & peers

Sektor-ETF'ens kvadrant på rotationsgrafen (RRG) og det relative 3-måneders afkast, plus de aktier i samme branche, som radaren følger, med score, afkast og trend. Navnet selv står fremhævet i tabellen (*this stock*), så du kan sammenligne direkte.

### Your market views

Hvordan navnet passer med dine [markedssyn](brugervejledning/markedssyn): et samlet mærke (*fits your views*, *against your views*, *mixed* eller *unrelated*), de syn der gælder, hvorfor, og hvad radarens data siger om hvert syn.

### Last 20 sessions og About

De seneste 20 handelsdage med justeret lukkekurs, ændring og volumen, og Yahoos beskrivelse af selskabet. Nederst på siden står kilderne med status og dato, eventuelle fejl fra Yahoo og hvornår profilen blev bygget.

## Tickere, radaren ikke følger

Du kan slå ethvert Yahoo-symbol op. Følger radaren det ikke, henter den kurshistorikken første gang, hvilket tager omkring 10 sekunder. Kurserne gemmes, så næste opslag er hurtigt, men symbolet kommer ikke med i den daglige opdatering; i stedet hentes nye kurser ved næste opslag. Sætter du navnet på watchlisten eller handler det, følger radaren det fremover.

Findes symbolet ikke på Yahoo, siger siden det. Nordiske og europæiske symboler har et suffiks: `.CO` København, `.ST` Stockholm, `.OL` Oslo, `.HE` Helsinki, `.DE` Xetra, `.L` London.

## Den samme profil på kommandolinjen

`uv run radar info NOVO-B.CO` skriver hele profilen som JSON, og `--refresh` henter Yahoos nøgletal på ny. Med flere symboler (`uv run radar info NVDA AMD`) får du en sammenligning side om side med ACWI som benchmark; dine egne data er udeladt, medmindre du tilføjer `--personal`. `uv run radar ticker NOVO-B.CO` åbner siden i browseren og starter appen, hvis den ikke kører. Se [Kommandolinjen](brugervejledning/kommandolinjen).
