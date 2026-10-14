# Tekniske indikatorer

Tekniske indikatorer er formler, der omsætter en kursserie (og nogle gange volumen) til et tal, som beskriver noget bestemt: hvor hurtigt kursen er steget, hvor langt den er fra sit gennemsnit, hvor meget den typisk svinger. Radaren viser en håndfuld af de mest udbredte på tickerprofilen og bruger nogle af dem i dine beholdninger. Dette kapitel definerer dem præcist, viser hvordan radaren beregner dem, og forklarer radarens graduerede målere, der farver alle aflæsningerne.

## Intuition

Indikatorerne svarer på fire forskellige spørgsmål:

| Spørgsmål | Indikator |
|---|---|
| Er kursen steget usædvanligt meget eller lidt for nylig? | RSI |
| Tager den kortsigtede trend til eller af? | MACD |
| Hvor ligger kursen i forhold til sit normale udsving? | Bollinger-bånd og %B |
| Hvor meget svinger kursen typisk? | ATR, realiseret volatilitet, maksimalt drawdown |

Og en femte: handles der mere end normalt? (volumen).

Ingen af dem forudsiger kursen. De er måder at beskrive den nyere kurshistorik på, så du hurtigt kan se, om en aktie er "strakt", "rolig" eller "urolig". Evidensen for, at de giver penge i sig selv, er blandet (Park og Irwin 2007). Radaren bruger dem som kontekst og advarselslamper, ikke som signaler.

## Teori

### RSI (Relative Strength Index)

J. Welles Wilder (1978) definerede RSI over $n$ dage (typisk 14) ud fra gennemsnitlige gevinster og tab. Lad $U_t = \max(P_t - P_{t-1}, 0)$ og $D_t = \max(P_{t-1} - P_t, 0)$. Wilders udglatning er

$$
\bar U_t = \frac{(n-1)\,\bar U_{t-1} + U_t}{n}, \qquad
\bar D_t = \frac{(n-1)\,\bar D_{t-1} + D_t}{n}
$$

startet med det simple gennemsnit af de første $n$ ændringer. Så er

$$
RS_t = \frac{\bar U_t}{\bar D_t}, \qquad RSI_t = 100 - \frac{100}{1 + RS_t}
$$

RSI ligger mellem 0 og 100. Over 70 kaldes traditionelt *overkøbt*, under 30 *oversolgt*. Wilders udglatning er en EMA med $\alpha = 1/n$, ikke $2/(n+1)$.

Navnet er misvisende: RSI har intet med *relativ styrke mod et benchmark* at gøre (se [Relativ styrke](laerebog/relativ-styrke)). Den måler aktiens egne op- og nedture.

### MACD

Gerald Appels *Moving Average Convergence Divergence* er forskellen mellem en hurtig og en langsom EMA:

$$
MACD_t = EMA_{12}(P)_t - EMA_{26}(P)_t, \qquad
\text{Signal}_t = EMA_9(MACD)_t, \qquad
\text{Histogram}_t = MACD_t - \text{Signal}_t
$$

MACD-linjen er positiv, når den korte trend ligger over den lange. Histogrammet viser, om MACD er over eller under sin egen udglattede version, altså om den kortsigtede trend *accelererer* (positivt) eller *aftager* (negativt). MACD måles i kursenheder, så tallet for en aktie til 2.000 kr. kan ikke sammenlignes med tallet for en aktie til 20 kr.

### Bollinger-bånd og %B

John Bollingers bånd ligger $k$ standardafvigelser over og under et $n$-dages glidende gennemsnit, typisk $n = 20$ og $k = 2$:

$$
\text{midt} = SMA_{20}, \qquad
\text{øvre} = \text{midt} + 2\sigma_{20}, \qquad
\text{nedre} = \text{midt} - 2\sigma_{20}
$$

$$
\%B = \frac{P - \text{nedre}}{\text{øvre} - \text{nedre}}
$$

%B er 0 ved det nederste bånd, 0,5 ved midten og 1 ved det øverste. Værdier over 1 eller under 0 betyder, at kursen er uden for båndene. Bollinger bruger populationsstandardafvigelsen (divisor $n$). Båndene bliver smalle i rolige perioder og brede i urolige, så %B er et relativt mål for, hvor "langt ude" kursen er.

### ATR (Average True Range)

Wilders *true range* tager højde for kursgab mellem dage:

$$
TR_t = \max\big(H_t - L_t,\; |H_t - C_{t-1}|,\; |L_t - C_{t-1}|\big)
$$

ATR er en udglattet $TR$ med Wilders metode ($\alpha = 1/n$, typisk $n = 14$):

$$
ATR_t = ATR_{t-1} + \frac{TR_t - ATR_{t-1}}{n}
$$

ATR er det typiske daglige udsving i kroner (eller kursenheder). Divideret med kursen bliver det et procentmål, der kan sammenlignes på tværs af aktier. ATR bruges meget til at sætte stop-loss i en afstand, der passer til aktiens normale udsving.

### Realiseret volatilitet

Standardafvigelsen af daglige log-afkast, annualiseret:

$$
\sigma_{\text{år}} = \sqrt{252} \cdot \operatorname{sd}\big(\ln(P_t / P_{t-1})\big)
$$

Se [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown) for den bredere diskussion.

### Maksimalt drawdown

Det største fald fra en top til en efterfølgende bund i et vindue:

$$
MDD = \min_t \left( \frac{P_t}{\max_{s \le t} P_s} - 1 \right)
$$

### Volumen

Usædvanlig høj volumen ledsager ofte nyheder, regnskaber eller institutionelle køb og salg. Et simpelt mål er forholdet mellem kort og lang gennemsnitlig volumen. En kursstigning på høj volumen regnes traditionelt for mere "ægte" end en på lav volumen.

## Sådan gør radaren

Indikatorerne beregnes i `signals/technicals.py` (og ATR i `signals/levels.py`) og vises på kortet *Technicals* på tickerprofilen ([Tickerprofilen](brugervejledning/tickerprofil)). RSI, MACD, Bollinger, realiseret volatilitet og drawdown beregnes på tickerens **egne** handelsdage (samme bars som grafen), så de stemmer med en ekstern graf. Perioderne for RSI, MACD og Bollinger står i koden.

### RSI 14

- Wilders metode med $n = 14$, startet med det simple gennemsnit af de første 14 ændringer, som de fleste kurssider gør.
- En serie, der kun stiger, giver 100; kun falder, 0; helt flad, 50.
- Tickerprofilen skriver *overbought* ved RSI ≥ 70 og *oversold* ved RSI ≤ 30 (fast i koden).
- RSI vises også som måler i [Mine beholdninger](/me), beregnet på beholdningens egne handelsdage.

### MACD 12/26/9 og MACD/ATR

- EMA'erne er pandas' `ewm(span=…, adjust=False)`, altså $\alpha = 2/(n+1)$ og startet i den første kurs.
- Intet vises, før der er mindst 26 kurser.
- Tilstanden er *bullish*, når histogrammet er positivt, ellers *bearish*.
- Fordi MACD er i kursenheder, graderer radaren **histogrammet divideret med ATR** (`macd_atr`). Det gør tallet sammenligneligt på tværs af aktier: 0,2 betyder, at MACD ligger en femtedel af et typisk dagsudsving over sin signallinje. Måleren har markering ved {{settings:gauges.macd_atr.ticks}} og ordene *bearish*, *fading*, *turning up* og *bullish* (`gauges.macd_atr`).

### Bollinger 20 dage, 2σ

- Midten er SMA20, båndene ±2 standardafvigelser beregnet med divisor $n$ (`ddof=0`), som hos Bollinger.
- %B vises og graderes (`gauges.bb_pct_b`, markeringer ved {{settings:gauges.bb_pct_b.ticks}}). Er båndene sammenfaldende (en helt flad kurs), er %B manglende.

### ATR og ATR %

- Wilders ATR over {{settings:stops.atr_days}} dage (`stops.atr_days`), beregnet som pandas' `ewm(alpha=1/n, adjust=False, min_periods=n)` på true range.
- Høj og lav er udbyttejusteret med samme faktor som lukkekursen (se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser)), så true range er konsistent med de justerede lukkekurser.
- To afvigelser fra Wilders lærebogsversion: udglatningen startes i den første true range i stedet for gennemsnittet af de første $n$ (forskellen forsvinder efter nogle uger), og ATR beregnes på radarens fælles kalender, hvor en børs' helligdag gentager den forrige dags bar.
- ATR % = ATR / seneste kurs. Det er en envejsmåler (`gauges.atr_pct`): rolig er grå, urolig er orange til rød, aldrig grøn.
- ATR er grundlaget for radarens stop: højeste lukkekurs siden køb minus $k$ gange ATR. Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

### Realiseret volatilitet (3 måneder)

Standardafvigelsen (divisor $n-1$) af de seneste 63 daglige log-afkast, gange $\sqrt{252}$. Der kræves mindst 31 afkast (halvdelen af vinduet), ellers er tallet manglende.

### Maksimalt drawdown (1 år)

Det største fald fra top til bund inden for de seneste 252 handelsdage.

### Volumen

`vol_surge` = gennemsnitlig volumen de seneste 20 dage divideret med gennemsnittet over 120 dage. Det vises på [Momentum](/momentum) og tickerprofilen med en envejsmåler (`gauges.vol_surge`).

### Graderede målere

Mange aflæsninger i radaren (RSI, %B, MACD/ATR, ATR %, volumen, afstand til 52-ugers top, momentumscore, regimets rækker, værdiansættelse, sentiment) vises ikke bare som et tal eller et ord, men som en farvet måler. Logikken ligger i `signals/gauges.py`:

1. **Ankre.** Hver måler har en liste af punkter $(x_i, s_i)$: en værdi og en score mellem −1 (advarsel, rød) og +1 (gunstig, grøn). Specifikationerne står under `gauges:` i `settings.yaml`; regimets rækker bygger deres ud fra `regime:`-tærsklerne.
2. **Lineær interpolation.** Scoren for en værdi $x$ mellem to ankre er $s(x) = s_i + (s_{i+1} - s_i)(x - x_i)/(x_{i+1} - x_i)$. Uden for yderste anker holdes scoren fast på endepunktets værdi.
3. **Envejsmålere.** Rene risikomål (`scale: sequential`, fx ATR %, volumen, beta, VIX) kan kun gå fra 0 til −1. De bliver aldrig grønne.
4. **Ni niveauer.** Scoren deles i niveauerne −4 til 4: $\text{niveau} = \operatorname{sign}(s) \cdot \lfloor 4|s| + 0.5 \rfloor$. Det giver diskrete farver, der er lette at skimme.
5. **Ord.** Hver måler har ordbånd (`labels`): det første bånd, hvis øvre grænse er over værdien, giver ordet. Farve er derfor aldrig den eneste information.
6. **Manglende data** giver ingen måler, aldrig en måler på 0.

Målere på niveau −3 eller lavere bliver til *watch-outs*, der vises først. Undtaget er egenskaber ved aktien (ATR % og beta), som beskriver, hvordan aktien er, ikke en ændring, og stop/kursmål for aktier, du ikke ejer. Grænsen −3 og undtagelserne står i koden.

Kolonnen *Signals* viser én prik pr. måler, så du kan se de mest bekymrende aflæsninger på en hel tabel.

## Regneeksempel

### RSI

Over de første 14 dage er summen af gevinster 14 kr. og summen af tab 7 kr. Startværdierne er $\bar U = 14/14 = 1.0$ og $\bar D = 7/14 = 0.5$.

$$
RS = \frac{1.0}{0.5} = 2, \qquad RSI = 100 - \frac{100}{3} = 66.7
$$

Dag 15 stiger kursen 2 kr.:

$$
\bar U = \frac{13 \cdot 1.0 + 2}{14} = 1.0714, \qquad
\bar D = \frac{13 \cdot 0.5 + 0}{14} = 0.4643
$$

$$
RS = 2.3077, \qquad RSI = 100 - \frac{100}{3.3077} = 69.8
$$

Tickerprofilen skriver *neutral* (under 70). Måleren med standardankrene (60; −0,15) og (70; −0,6) giver $-0.15 - 0.45 \cdot 9.8/10 \approx -0.59$, niveau −2 og ordet *near overbought*.

### ATR og ATR %

I går lukkede aktien på 53. I dag er høj 52, lav 49 og luk 50.

$$
TR = \max(52 - 49,\; |52 - 53|,\; |49 - 53|) = \max(3, 1, 4) = 4
$$

Kursgabet ned fra 53 tæller med. Med gårsdagens ATR på 2,50 og $n = 14$:

$$
ATR = 2.50 + \frac{4 - 2.50}{14} = 2.607
$$

ATR % = 2,607 / 50 = 5,2 %. På envejsmåleren ligger det mellem ankrene (0,04; −0,5) og (0,07; −1): $-0.5 - 0.5 \cdot 0.0121/0.03 \approx -0.70$, niveau −3 og ordet *very volatile*. Fordi ATR % er en egenskab, bliver det ikke en watch-out.

### MACD/ATR

Samme dag er MACD-histogrammet 0,50. `macd_atr` = 0,50 / 2,607 = 0,19. Mellem ankrene (0,1; 0,3) og (0,5; 1): $0.3 + 0.7 \cdot 0.092/0.4 \approx 0.46$, niveau 2 og ordet *bullish*.

### Bollinger %B

SMA20 er 100, og standardafvigelsen (divisor 20) er 4. Båndene er 92 og 108. Kursen er 106:

$$
\%B = \frac{106 - 92}{108 - 92} = \frac{14}{16} = 0.875
$$

Mellem ankrene (0,65; 0) og (1; −0,5): $-0.5 \cdot 0.225/0.35 \approx -0.32$, niveau −1 og ordet *upper half*. Havde radaren brugt divisor 19, ville standardafvigelsen være $4 \cdot \sqrt{20/19}$ = 4,10, og båndene lidt bredere.

### Realiseret volatilitet og drawdown

Standardafvigelsen af de daglige log-afkast er 1,5 %. Årlig volatilitet: $0.015 \cdot \sqrt{252} = 0.015 \cdot 15.87 = 23.8$ %.

Lukkekurserne er 100, 120, 90, 110, 95. Løbende top: 100, 120, 120, 120, 120. Fald fra toppen: 0 %, 0 %, −25,0 %, −8,3 %, −20,8 %. Maksimalt drawdown: −25,0 %.

## Faldgruber og begrænsninger

- **Overkøbt kan blive ved.** I en stærk trend kan RSI ligge over 70 i ugevis. For en momentuminvestor er en høj RSI ofte et tegn på styrke, ikke et salgssignal. Brug den som et tegn på, at kursen er strakt, og at et tilbagefald er sandsynligt.
- **Indikatorerne er afledt af den samme kurs.** RSI, MACD og %B måler varianter af det samme og er stærkt korrelerede. Tre "grønne" indikatorer er ikke tre uafhængige beviser.
- **Parametre er konventioner.** 14, 12/26/9 og 20/2 er historiske standardvalg, ikke optimerede værdier. At justere dem til at passe til historikken er overfitting; se [Statistik for investorer](laerebog/statistik).
- **Forsinkelse.** Alle udglattede mål halter. MACD og Bollinger reagerer først, når bevægelsen er i gang.
- **Gaps og helligdage.** True range fanger kursgab; men på radarens fælles kalender gentager en helligdag den forrige dags bar, hvilket påvirker ATR en smule.
- **Målerne er en fortolkning.** Ankrene i `settings.yaml` er valgt som rimelige tommelfingerregler, ikke estimeret fra data. Ændrer du dem, ændrer farverne sig, men ikke tallene.
- **Ingen indikator er en anbefaling.** Radaren viser dem som kontekst. Beslutninger kræver mere end en farve.

## Videre læsning

- J. Welles Wilder Jr.: *New Concepts in Technical Trading Systems*, Trend Research, 1978 (RSI og ATR).
- Gerald Appel: *Technical Analysis: Power Tools for Active Investors*, FT Prentice Hall, 2005 (MACD).
- John Bollinger: *Bollinger on Bollinger Bands*, McGraw-Hill, 2001.
- John J. Murphy: *Technical Analysis of the Financial Markets*, New York Institute of Finance, 1999.
- Andrew W. Lo, Harry Mamaysky og Jiang Wang: "Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation", *Journal of Finance*, 55(4), 2000.
- Cheol-Ho Park og Scott H. Irwin: "What Do We Know About the Profitability of Technical Analysis?", *Journal of Economic Surveys*, 21(4), 2007.
