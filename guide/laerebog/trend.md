# Glidende gennemsnit og trend

Et glidende gennemsnit er det enkleste værktøj i teknisk analyse og et af de mest brugte: gennemsnittet af de seneste $n$ kurser, genberegnet hver dag. Det glatter støjen ud og viser retningen. Radaren bruger 50- og 200-dages gennemsnit til at afgøre, om trenden for verdensmarkedet og for den enkelte aktie er intakt. Dette kapitel forklarer teorien, evidensen og prisen: de falske signaler, der kaldes *whipsaws*.

## Intuition

Dagligdags kursbevægelser er for det meste støj. Et gennemsnit over mange dage udligner de tilfældige op- og nedture og lader den langsomme bevægelse stå tilbage. Ligger kursen over sit 200-dages gennemsnit, har den i gennemsnit været stigende det seneste år; ligger den under, har den været faldende.

Ideen bag at følge trenden er enkel: markeder har tendens til at fortsætte i samme retning i måneder, og de største tab sker oftest i langvarige faldperioder. En regel, der holder sig ude, når kursen er under sit lange gennemsnit, undgår en del af de store fald. Prisen er, at den også sælger ved mange midlertidige dyk, der vender igen. Den kommer altid lidt for sent ind og lidt for sent ud.

Glidende gennemsnit er derfor ikke en forudsigelse. De er et filter, der beskriver tilstanden *nu* og med en kendt forsinkelse.

## Teori

### Simpelt glidende gennemsnit (SMA)

$$
SMA_n(t) = \frac{1}{n} \sum_{i=0}^{n-1} P_{t-i}
$$

Alle $n$ kurser vægtes ens. Gennemsnittet halter efter kursen: tyngdepunktet af vinduet ligger $(n-1)/2$ dage tilbage, så et 200-dages gennemsnit afspejler i gennemsnit kursen for omkring 100 handelsdage siden.

### Eksponentielt glidende gennemsnit (EMA)

$$
EMA_t = \alpha P_t + (1 - \alpha) EMA_{t-1}, \qquad \alpha = \frac{2}{n + 1}
$$

Nyere kurser vægtes mest, og vægten aftager geometrisk bagud. Med $\alpha = 2/(n+1)$ har en EMA samme gennemsnitlige forsinkelse som en SMA med samme $n$, men reagerer hurtigere på et pludseligt skift. EMA'en skal startes et sted; en almindelig konvention er at sætte den første værdi lig den første kurs. EMA bruges blandt andet i MACD, se [Tekniske indikatorer](laerebog/tekniske-indikatorer).

### 50 og 200 dage, golden cross og death cross

De mest brugte vinduer for aktier er 50 dage (ca. et kvartal, mellemlang trend) og 200 dage (ca. et handelsår minus en måned, lang trend). Når 50-dages gennemsnittet krydser op over 200-dages, kaldes det et *golden cross*; krydser det ned under, et *death cross*. Begreberne er populære i medierne, men krydset er bare en langsommere version af det samme signal som kursen mod 200-dages gennemsnittet, og det kommer typisk endnu senere.

En mere robust beskrivelse er at se på *tilstanden* frem for krydset:

| Kurs mod SMA200 | SMA50 mod SMA200 | Tolkning |
|---|---|---|
| over | over | stigende trend, intakt |
| under | under | faldende trend |
| over | under | mulig vending op (kursen er steget, gennemsnittet halter) |
| under | over | mulig svækkelse (et dyk i en stigende trend) |

### Trendfiltre

Et trendfilter bruger trenden som en betingelse: "hold kun aktivet, når kursen er over sit lange gennemsnit", eller "kig kun på momentumkandidater, hvis trenden er intakt". Filteret skal ikke selv finde vindere; det skal holde dig ude af de værste perioder.

### Evidensen

- **Brock, Lakonishok og LeBaron (1992)** testede simple regler med glidende gennemsnit på Dow Jones-indekset 1897–1986 og fandt, at afkastet efter købssignaler var højere og mindre volatilt end efter salgssignaler. Sullivan, Timmermann og White (1999) viste senere, at effekten var svagere efter 1986, når man korrigerer for, at mange regler er afprøvet (*data snooping*).
- **Faber (2007)** foreslog en simpel regel for aktivallokering: hold et aktiv, når månedens slutkurs er over sit 10-måneders gennemsnit (ca. 200 handelsdage), ellers statsobligationer med kort løbetid. I hans test over mere end et århundrede gav reglen et afkast på niveau med at købe og holde, men med lavere volatilitet og markant mindre drawdowns. Fordelen kom næsten udelukkende fra at undgå store, langvarige bjørnemarkeder.
- **Tidsseriemomentum.** Moskowitz, Ooi og Pedersen (2012) fandt i 58 likvide futures-markeder (aktieindeks, valuta, råvarer, obligationer), at et aktivs eget afkast over de seneste 12 måneder forudsiger dets afkast den næste måned positivt. Effekten varer op til ca. et år og vender delvist derefter. Hurst, Ooi og Pedersen (2017) fandt positive afkast af trendfølgning i hvert årti siden 1880. Kursen over et langt gennemsnit er en nær slægtning af et positivt 12-måneders afkast. Se [Momentumeffekten](laerebog/momentumeffekten).

### Whipsaws

Når et marked bevæger sig sidelæns omkring sit gennemsnit, krydser kursen frem og tilbage. Hvert kryds udløser et signal, og hvert signal kommer efter, at bevægelsen er sket: man sælger efter et fald og køber igen efter en stigning. Det kaldes *whipsaws* (piskeslag). I sidelæns markeder er trendfiltre derfor dyre, og i hurtige V-formede vendinger (som i marts–april 2020) kommer de for sent både ud og ind. Trendfølgning tjener sine penge i lange trends og taber dem i korte, hakkede perioder. Et bånd omkring gennemsnittet (fx kun handle ved ±2–5 % afstand) eller et krav om, at både kurs og 50-dages gennemsnit skal være på samme side, reducerer antallet af falske signaler, men gør reaktionen langsommere.

## Sådan gør radaren

### Den globale trend (ACWI) på Regime-siden

Første række på [Regime](/regime), *Global trend (ACWI)*, bruger ACWI's justerede lukkekurs (USA-noteret, i USD) og to simple gennemsnit (`signals/regime.py`):

- **risk-on**, hvis kursen er over SMA200 **og** SMA50 er over SMA200 (*Price and 50d above 200d average*),
- **risk-off**, hvis kursen er under SMA200 **og** SMA50 er under SMA200 (*Below 200d average*),
- **neutral** ellers (*Mixed trend*).

Aflæsningen (*Reading*) viser afstanden til 200-dages gennemsnittet, fx *+3.0% vs 200d*. Kravet om, at både kurs og SMA50 skal være på samme side, er netop et filter mod whipsaws: et kort dyk under SMA200 i en stigende trend giver *neutral*, ikke *risk-off*. Rækken er én stemme i risk-on/risk-off-afstemningen; se [Radarens afstemningsmodel](laerebog/afstemningsmodellen).

Rækken har også en gradueret måler for afstanden $d = P / SMA_{200} - 1$. Måleren er bygget i koden med tærsklerne −5 % og +5 % (`gauges.band(-0.05, 0.05)`):

| $d$ | Ord |
|---|---|
| under −5 % | *downtrend* |
| −5 % til −2,5 % | *near downtrend* |
| −2,5 % til +2,5 % | *flat* |
| +2,5 % til +5 % | *near uptrend* |
| fra +5 % | *uptrend* |

Farven går lineært fra 0 ved $d = 0$ til ±0,6 ved ±5 % og ±1 ved ±15 %. Bemærk, at måleren kun ser på afstanden, mens stemmen også kræver SMA50 på samme side. De kan derfor være uenige: kursen kan være 3 % over SMA200 (*near uptrend*), mens stemmen er *neutral*, fordi SMA50 stadig er under.

### Trend for den enkelte aktie

For alle aktier, ETF'er og beholdninger beregner `signals/momentum.py`:

- `sma50` og `sma200`: gennemsnittet af de seneste 50 og 200 rækker i prismatricen (i praksis hverdage; se [Afkast og renters rente](laerebog/afkast)),
- `above50`: kurs over SMA50,
- `above200`: kurs over SMA200,
- `trend_ok`: kurs over SMA200 **og** SMA50 over SMA200.

Har en ticker færre end {{settings:momentum.min_history_days}} dages historik (`momentum.min_history_days`), sættes SMA200 til manglende, og så er `above200` og `trend_ok` også manglende, ikke "nej". Krydsene (golden/death cross) vises som mærker under *Flags* på [Mine beholdninger](brugervejledning/beholdninger), når 50-dages gennemsnittet er krydset 200-dages inden for de seneste 20 handelsdage (grænsen ligger i koden). De bruges ikke i scoren eller i afstemningen.

`trend_ok` vises som kolonnen *Trend* (✓) på [Momentum](/momentum) og i [Mine beholdninger](/me). Der er ingen tilsvarende "nedtrend"-markering: et manglende flueben betyder bare, at mindst én af de to betingelser ikke er opfyldt.

### Flag i dine beholdninger

I [Mine beholdninger](/me) laver `mine.py` regelbaserede flag ud fra de samme tal. Tærsklerne står i koden:

| Flag | Gælder | Betingelse |
|---|---|---|
| *trend intact* | alle | `trend_ok` |
| *losing momentum* | beholdninger | kurs under SMA50 og 1-måneds afkast negativt |
| *below 200d* | beholdninger | kurs under SMA200 |
| *turning up* | watchlist og solgte | kurs over SMA50, 1-måneds afkast positivt og 3-måneders afkast over ACWI's |
| *near 52w high* | alle | under 3 % fra højeste lukkekurs de seneste 252 rækker |

Trenden indgår også i de regelbaserede stop: en aktie med intakt trend og høj momentumscore får mere plads, mens en aktie under sit 200-dages gennemsnit eller med tabt momentum får et strammere stop. Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

### Andre steder

- **Sektor- og tema-ETF'er** har kolonnen *>200d* på rotationssiderne: kurs over gennemsnittet af de seneste 200 rækker.
- **Markedsbredde** måler andelen af aktier over deres eget 200-dages gennemsnit; se [Markedsbredde](laerebog/markedsbredde).
- **Discover** markerer *trend turn*: kursen har krydset op over 200-dages gennemsnittet inden for de seneste 20 handelsdage, mens 50-dages gennemsnittet stiger.

## Regneeksempel

### SMA og EMA

Fem dages lukkekurser: 100, 102, 101, 105, 110.

SMA(5) = (100 + 102 + 101 + 105 + 110) / 5 = 518 / 5 = **103,6**.

EMA(5) med $\alpha = 2/6 = 1/3$, startet i den første kurs:

| Dag | Kurs | EMA |
|---|---|---|
| 1 | 100 | 100,00 |
| 2 | 102 | 100 + (102 − 100)/3 = 100,67 |
| 3 | 101 | 100,67 + (101 − 100,67)/3 = 100,78 |
| 4 | 105 | 100,78 + (105 − 100,78)/3 = 102,19 |
| 5 | 110 | 102,19 + (110 − 102,19)/3 = **104,79** |

EMA'en ligger tættere på den seneste kurs (110) end SMA'en, fordi den vægter de nyeste dage mest.

### ACWI-trendens tre tilstande

| Kurs | SMA50 | SMA200 | Stemme | Afstand $d$ | Måler |
|---|---|---|---|---|---|
| 105 | 102 | 100 | risk-on | +5,0 % | *uptrend* |
| 103 | 99 | 100 | neutral | +3,0 % | *near uptrend* |
| 99 | 101 | 100 | neutral | −1,0 % | *flat* |
| 94 | 97 | 100 | risk-off | −6,0 % | *downtrend* |

For rækken med +3,0 % er målerens score $0.6 \cdot 0.03 / 0.05 = 0.36$. Scoren deles i ni niveauer (−4 til 4) ved at runde $0.36 \cdot 4 = 1.44$ til nærmeste heltal: niveau 1, en svag grøn. Se [Tekniske indikatorer](laerebog/tekniske-indikatorer#graderede-målere) for, hvordan målerne virker.

### Whipsaw

ACWI ligger i tre måneder mellem 98 og 103 med SMA200 på 100. En regel "hold kun over SMA200" sælger ved 99,5, køber ved 100,5, sælger ved 99,5 igen og så videre. Hver rundtur koster omkring 1 % plus handelsomkostninger. Seks rundture er ca. 6 % tabt i et marked, der står stille. Radarens regel med både kurs og SMA50 ville i samme periode for det meste vise *neutral*, fordi SMA50 kun langsomt krydser SMA200.

## Faldgruber og begrænsninger

- **Forsinkelse.** Et 200-dages gennemsnit afspejler kurser fra omkring 100 dage siden. Trendsignaler bekræfter, de forudsiger ikke.
- **Whipsaws i sidelæns markeder.** De fleste falske signaler kommer, når kursen ligger tæt på gennemsnittet. Se derfor på afstanden, ikke kun på siden.
- **V-formede vendinger** straffer trendfiltre dobbelt: ude efter faldet, inde efter stigningen.
- **Valuta.** ACWI-trenden er målt i USD. En dansk investors oplevelse i DKK kan afvige, når dollaren bevæger sig meget.
- **Fælles kalender.** Radarens 200 dage er 200 rækker i en kalender med alle hverdage; børsers helligdage tæller som flade dage. Forskellen til en børsgraf er lille, men kan flytte et kryds en dag eller to.
- **Trend er ikke værdi.** En aktie kan være i en intakt trend og samtidig meget dyr. Se [P/E og indtjening pr. aktie](laerebog/pe-og-eps).

## Videre læsning

- William Brock, Josef Lakonishok og Blake LeBaron: "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns", *Journal of Finance*, 47(5), 1992.
- Ryan Sullivan, Allan Timmermann og Halbert White: "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", *Journal of Finance*, 54(5), 1999.
- Mebane T. Faber: "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth Management*, 9(4), 2007.
- Tobias J. Moskowitz, Yao Hua Ooi og Lasse Heje Pedersen: "Time Series Momentum", *Journal of Financial Economics*, 104(2), 2012.
- Brian Hurst, Yao Hua Ooi og Lasse Heje Pedersen: "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management*, 44(1), 2017.
- Valeriy Zakamulin: *Market Timing with Moving Averages: The Anatomy and Performance of Trading Rules*, Palgrave Macmillan, 2017.
