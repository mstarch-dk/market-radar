# Benchmark og relativt afkast

Et afkast på 12 % lyder godt, men er det godt? Det afhænger af, hvad du kunne have fået i stedet. Et benchmark er svaret på "i stedet for hvad?". Radaren bruger MSCI ACWI, hele verdens aktiemarked i ét indeks, og næsten alle dens sammenligninger handler om ét spørgsmål: *Kan jeg gøre det bedre end at eje ACWI?*

## Intuition

Et benchmark er et alternativ, du realistisk kunne have valgt uden at gøre dig umage. For en dansk aktieinvestor er det mest oplagte alternativ en billig, global indeksfond. Den kræver ingen analyse, ingen timing og næsten ingen omkostninger. Al aktiv investering, at vælge enkeltaktier, sektorer eller temaer, er et væddemål om at slå dette alternativ.

Derfor er et afkast i sig selv ikke et mål for dygtighed. Stiger markedet 20 %, og din portefølje stiger 15 %, har du tjent penge, men tabt 5 procentpoint på dine valg. Falder markedet 20 % og du kun 10 %, har du tabt penge, men dine valg har tilført værdi.

To ting gør sammenligningen svær:

- **Pengene kommer ind på forskellige tidspunkter.** Køber du en aktie i marts og en anden i september, skal sammenligningen tage højde for, at ACWI også ville have fået pengene i marts og september. Radaren løser det med en *skyggeposition*.
- **Støj.** Over et par måneder kan selv en tilfældig portefølje ligge langt foran eller bagefter. Om en forskel er dygtighed eller held, kræver en lang serie og statistik.

## Teori

### Hvad er et godt benchmark?

Et benchmark bør være specificeret på forhånd, investerbart, målbart, utvetydigt og passende for strategien (Bailey 1992). Et benchmark valgt bagefter, fordi man ville se godt ud, er værdiløst. MSCI ACWI opfylder kravene for en global aktieinvestor: der findes billige ETF'er, der følger det, og reglerne for indekset er offentlige.

### MSCI ACWI

MSCI ACWI (*All Country World Index*) dækker store og mellemstore selskaber i både udviklede markeder og vækstmarkeder, i alt omkring 2.500 selskaber i 23 udviklede og 24 vækstmarkeder (MSCI's faktaark, 2025), og omkring 85 % af den fritflydende markedsværdi i hvert land. Selskaberne vægtes efter fritflydende markedsværdi. Det betyder, at USA i de senere år har vejet omkring 60–65 %, og at de største selskaber vejer tungt. ACWI er derfor ikke "neutralt", men det er *markedsporteføljen*: den portefølje, alle investorer tilsammen ejer.

### Aktiv og passiv investering

En passiv investor ejer markedet og får markedets afkast minus små omkostninger. En aktiv investor afviger fra markedsvægtene. William Sharpe (1991) påpegede en simpel aritmetik: hvis passive investorer får markedsafkastet før omkostninger, må de aktive *tilsammen* også gøre det, for tilsammen ejer de resten af markedet. Efter omkostninger må den gennemsnitlige aktive krone derfor klare sig dårligere end den gennemsnitlige passive. Aktiv investering er et nulsumsspil før omkostninger og et negativsumsspil efter.

Det er i overensstemmelse med data: S&P's SPIVA-rapporter viser år efter år, at et klart flertal af aktivt forvaltede aktiefonde klarer sig dårligere end deres benchmark over 10–15 år, og Fama og French (2010) finder, at det kun er få fonde, hvis afkast ikke kan forklares som held.

### Merafkast og relativt afkast

Lad $R_p$ være porteføljens og $R_b$ benchmarkets afkast over samme periode. Merafkastet (aktivt afkast, *excess return*) er differencen

$$
R_a = R_p - R_b
$$

målt i procentpoint. Et alternativ er det *geometriske* relative afkast

$$
R_{\text{rel}} = \frac{1 + R_p}{1 + R_b} - 1
$$

som er afkastet af at eje porteføljen finansieret ved at sælge benchmarket. For små tal er de næsten ens; for store afkast afviger de. Ordet *excess return* bruges også om afkast over den risikofri rente; i dette kapitel betyder det altid merafkast i forhold til benchmarket.

### Tracking error og informationsratio

Tracking error er standardafvigelsen af de aktive afkast over en række perioder:

$$
TE = \sigma(R_{p,t} - R_{b,t})
$$

annualiseret med $\sqrt{12}$ for månedsdata eller $\sqrt{52}$ for ugedata. En indeksfond har en tracking error tæt på 0; en koncentreret portefølje af temaaktier kan have 10–20 %. Informationsratioen sætter merafkast i forhold til den risiko, man tog for at få det:

$$
IR = \frac{\bar R_a}{TE}
$$

(begge annualiserede). Grinold og Kahn (2000) bruger den som det centrale mål for en aktiv forvalters dygtighed. En IR på 0,5 vedvarende over mange år regnes for meget god.

### Skyggepositionen

For en privat investor med ind- og udbetalinger på skæve tidspunkter er det mest retfærdige benchmark ikke "ACWI siden 1. januar", men "de samme kroner i ACWI på de samme dage". Det kaldes her en *skyggeposition*: hver gang du køber for et beløb, køber skyggen ACWI for samme beløb samme dag; hver gang du sælger en andel, sælger skyggen samme andel. Forskellen mellem din position og skyggen er så den værdi, dine *valg* har tilført, med timingen af pengene holdt ens på begge sider.

## Sådan gør radaren

### Benchmarket

Radarens beregninger bruger iShares' USA-noterede ETF `ACWI` (i USD) som MSCI ACWI. I `config/universe.yaml` er `SSAC.L` (iShares MSCI ACWI UCITS, akkumulerende) angivet som den udgave, en dansk investor kan købe. Kurserne er justerede, så benchmarket er et totalafkast efter fondens omkostninger. I DKK-beregninger omregnes det med `USDDKK=X`.

### Relativt afkast i tabellerne

På [Sektorrotation](/rotation) og [Temaer og faktorer](/themes) viser kolonnerne *Rel 1m*, *Rel 3m* og *Rel 6m* merafkastet mod ACWI som en difference:

$$
\text{rel}_{n} = \left(\frac{P_t}{P_{t-n}} - 1\right) - \left(\frac{B_t}{B_{t-n}} - 1\right), \quad n \in \{21, 63, 126\}
$$

hvor $B$ er ACWI. Benchmarket afkortes til ETF'ens seneste dato, så en ETF, der er holdt op med at opdatere, ikke måles mod nyere ACWI-gevinster. Begge afkast er i hver sin noteringsvaluta: en europæisk sektor-ETF i euro mod ACWI i dollar. Det er et bevidst valg i koden, men det betyder, at en svækkelse af dollaren mod euroen får europæiske ETF'er til at se relativt stærkere ud. Til at rangere ETF'erne i hver gruppe vægter radaren de tre som $0.2 \cdot \text{rel}_{1m} + 0.4 \cdot \text{rel}_{3m} + 0.4 \cdot \text{rel}_{6m}$ (vægtene står i koden). Se [Relativ styrke](laerebog/relativ-styrke).

For dine beholdninger og watchlist beregnes `rel_r3m` (kolonnen *Rel 3m*) på samme måde (aktiens 3-måneders afkast minus ACWI's), og det bruges i flaget *turning up* for watchlist og solgte positioner.

### Dine beholdninger mod skygge-ACWI

På [Mine beholdninger](/me) viser kolonnerne *Since buy (DKK)* og *ACWI (DKK)* (`since_buy` og `bench_since_buy`) din positions totalafkast i DKK og skyggepositionens. Metoden i `mine.vs_shadow`:

1. Hvert køb koster $q \cdot \text{kurs} + \text{kurtage}$ i handelsvalutaen, omregnet til DKK med valutakursen på handelsdagen. Samme DKK-beløb købes i ACWI-i-DKK samme dag.
2. Et salg fjerner samme *andel* fra både positionen og skyggen (gennemsnitsmetoden). Kostprisen reduceres forholdsmæssigt.
3. Udbytter regnes som geninvesteret på begge sider (justerede kurser).
4. Afkast = nuværende værdi / resterende kostpris − 1, for både position og skygge.

Forskellen (position minus skygge, i procentpoint) vises som en farvet måler under *Signals* (nøglen `excess_vs_acwi`): grå omkring 0, gradvist grønnere jo længere positionen ligger foran, og rødere jo længere den ligger bagefter, med ordene *ahead of ACWI*, *level with ACWI* og *behind ACWI*. Ankre og ordgrænser står i `gauges.excess_vs_acwi` i `settings.yaml`; se [Tekniske indikatorer](laerebog/tekniske-indikatorer#graderede-målere) for, hvordan målerne virker.

### Porteføljer over tid

På [Afkast over tid](/returns) sammenlignes hver portefølje med ACWI på to måder: ACWI's tidsvægtede afkast i DKK over samme periode, og *ACWI with the same cash flows*, hvor de samme ind- og udbetalinger går i ACWI. Det første svarer på "var mine valg gode?", det andet på "hvad ville mine penge have været værd?". Forskellen forklares i [Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr).

### Hvorfor ikke sektor- eller regionsindeks?

Radaren bruger enkelte lokale benchmarks, fx til den lokale rotationsgraf for europæiske sektorer. Men hovedspørgsmålet er altid ACWI, fordi det er dit reelle alternativ. En europæisk bankaktie, der slår europæiske banker men taber til verden, var et dårligere valg end en global indeksfond.

## Regneeksempel

### Skyggeposition med to køb og et salg

For enkelhedens skyld er aktien noteret i DKK, og ACWI's kurs er allerede omregnet til DKK.

| Dato | Handel | Aktie | ACWI (DKK) | Skygge |
|---|---|---|---|---|
| 1. marts | Køb 100 stk. à 100 kr. | 10.000 kr. | 500 | 10.000 / 500 = 20,000 enheder |
| 1. juni | Køb 40 stk. à 125 kr. | 5.000 kr. | 550 | 5.000 / 550 = 9,091 enheder |
| I alt | | 140 stk., kostpris 15.000 kr. | | 29,091 enheder |

I dag står aktien i 130 kr. og ACWI i 600.

- Position: 140 · 130 = 18.200 kr. Afkast: 18.200 / 15.000 − 1 = **21,33 %**.
- Skygge: 29,091 · 600 = 17.454,5 kr. Afkast: 17.454,5 / 15.000 − 1 = **16,36 %**.
- Merafkast: 21,33 − 16,36 = **4,97 procentpoint**. Dine valg (aktie og tidspunkter for netop den aktie) slog ACWI.

Sælger du nu 70 stk., fjernes halvdelen fra begge: 70 stk. med kostpris 7.500 kr., og 14,545 ACWI-enheder. Afkastene er uændrede (9.100/7.500 − 1 = 21,33 % og 8.727/7.500 − 1 = 16,36 %), fordi gennemsnitsmetoden fjerner kostpris i samme forhold.

### Differens og geometrisk relativt afkast

En sektor-ETF er steget 12 % på tre måneder, ACWI 5 %.

- Radarens `rel_r3m`: 12 − 5 = **7,0 procentpoint**.
- Geometrisk: 1,12 / 1,05 − 1 = **6,67 %**.

### Tracking error og informationsratio

Seks månedlige merafkast: +1, −2, +3, 0, −1, +2 %. Gennemsnit: 3/6 = 0,5 % om måneden. Afvigelserne fra gennemsnittet i anden: 0,25 + 6,25 + 6,25 + 0,25 + 2,25 + 2,25 = 17,5. Stikprøvevarians: 17,5 / 5 = 3,5, standardafvigelse 1,87 % om måneden.

$$
TE = 1.87 \cdot \sqrt{12} \approx 6.48\ \%, \qquad IR = \frac{0.5 \cdot 12}{6.48} \approx 0.93
$$

Det ligner en flot informationsratio, men på seks måneder er det næsten ren støj: standardfejlen på gennemsnittet er 1,87 / $\sqrt{6}$ = 0,76 % om måneden, større end selve gennemsnittet. Se [Statistik for investorer](laerebog/statistik).

## Faldgruber og begrænsninger

- **Kort horisont, stor støj.** Et merafkast over tre eller seks måneder siger meget lidt om dygtighed. Brug det som et signal om, hvad der virker *nu*, ikke som bevis for evner.
- **Valuta i rel_r-kolonnerne.** De relative afkast på rotationssiderne er i noteringsvaluta, ikke DKK. Skyggepositionen og porteføljeafkastet er i DKK.
- **Differens frem for forhold.** `rel_r*` er en simpel difference i procentpoint. Ved store afkast afviger den fra det geometriske relative afkast.
- **ACWI-ETF'en er ikke indekset.** ETF'en har omkostninger, kildeskat og små afvigelser. Det er netop derfor, den er det rigtige alternativ: den er investerbar.
- **Skyggen kender ikke skat.** Både position og skygge er før skat. En aktiesparekonto og frie midler beskattes forskelligt, og en ACWI-fond på positivlisten beskattes anderledes end en enkeltaktie. Se [Dansk skat for investorer](laerebog/skat).
- **Risiko.** Et merafkast fra en position med beta 1,5 i et stigende marked er ikke nødvendigvis dygtighed. Se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

## Videre læsning

- William F. Sharpe: "The Arithmetic of Active Management", *Financial Analysts Journal*, 47(1), 1991.
- Richard C. Grinold og Ronald N. Kahn: *Active Portfolio Management*, 2. udgave, McGraw-Hill, 2000.
- Eugene F. Fama og Kenneth R. French: "Luck versus Skill in the Cross-Section of Mutual Fund Returns", *Journal of Finance*, 65(5), 2010.
- Jeffery V. Bailey: "Are Manager Universes Acceptable Performance Benchmarks?", *Journal of Portfolio Management*, 18(3), 1992.
- S&P Dow Jones Indices: *SPIVA Scorecards* (halvårlige rapporter om aktive fonde mod deres benchmark).
- MSCI: *MSCI ACWI Index* (faktaark og metode), MSCI Inc.
