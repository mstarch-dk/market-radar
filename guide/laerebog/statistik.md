# Statistik for investorer

Radaren er fuld af tal: gennemsnit, percentiler, rangeringer, beta med standardfejl, R². Dette kapitel samler den statistik, du skal kende for at læse dem rigtigt, og de fejl, der oftest får tal til at se mere overbevisende ud, end de er. Den vigtigste lektie står allerede her: finansielle data er støjende, og de fleste mønstre, man ser, er tilfældige.

## Intuition

Et aktieafkast er en lille sandsynlig bevægelse gemt i en stor tilfældig. En aktie, der i gennemsnit stiger 1 % om måneden, kan let svinge 8 % op eller ned i en enkelt måned. Det betyder, at selv en ægte fordel kun bliver synlig over mange år, og at et kort, flot forløb næsten intet beviser.

Statistik giver dig værktøjer til at stille tre spørgsmål til ethvert tal:

1. **Hvor typisk er det?** Gennemsnit, spredning og percentiler fortæller, hvor en værdi ligger i forhold til andre eller i forhold til sin egen historie.
2. **Hænger to ting sammen?** Korrelation og regression måler, hvor meget én serie bevæger sig med en anden.
3. **Kan det være held?** Standardfejl, t-værdier og stikprøvestørrelse fortæller, hvor sikkert et skøn er.

Og så er der fejlene, der ikke er tilfældige: at se på dagens vindere og glemme taberne (*survivorship bias*), at bruge oplysninger, man ikke havde dengang (*look-ahead bias*), at prøve hundrede regler og kun huske den bedste (*overfitting*), og at glemme, hvor sjælden en begivenhed er i forvejen (*base rates*).

## Teori

### Gennemsnit, varians og standardafvigelse

For observationer $x_1, \dots, x_n$ er gennemsnittet og stikprøvevariansen

$$
\bar x = \frac{1}{n} \sum_{i=1}^{n} x_i,
\qquad
s^2 = \frac{1}{n-1} \sum_{i=1}^{n} (x_i - \bar x)^2
$$

Standardafvigelsen $s = \sqrt{s^2}$ måler den typiske afstand til gennemsnittet i samme enhed som data. Divisoren $n-1$ (Bessels korrektion) giver et middelret skøn over den sande varians, fordi gennemsnittet selv er estimeret fra de samme data. Med divisor $n$ får man *populationsvariansen*; nogle indikatorer (fx Bollinger-bånd) bruger den. For afkast kaldes standardafvigelsen *volatilitet*.

### Percentiler og rang

En percentil siger, hvor stor en andel af en fordeling der ligger under en given værdi. Der findes flere definitioner, som giver lidt forskellige tal, især i små stikprøver:

- **Andel strengt under:** $p(v) = \frac{1}{n} \#\{i : x_i < v\}$. Den laveste værdi får 0.
- **Rang divideret med antal:** sorter værdierne og giv hver sin rang $1, \dots, n$ (lige store værdier får gennemsnittet af deres rang). Percentilen er $\text{rang}/n$. Den laveste får $1/n$, den højeste 1.

Percentiler er robuste over for ekstreme værdier og sammenlignelige på tværs af størrelser med forskellige enheder. Det er derfor, radarens momentumscore bygger på dem.

### Korrelation

Korrelationen mellem to serier er

$$
\rho_{xy} = \frac{\operatorname{cov}(x,y)}{\sigma_x \sigma_y}
= \frac{\sum (x_i - \bar x)(y_i - \bar y)}{\sqrt{\sum (x_i - \bar x)^2 \sum (y_i - \bar y)^2}}
$$

Den ligger mellem −1 og 1 og måler *lineær* samvariation. En korrelation på 0 udelukker ikke en sammenhæng (den kan være ikke-lineær), og en høj korrelation siger intet om årsag. Korrelationer mellem aktier er ustabile: de stiger typisk i kriser, netop når man har mest brug for spredning. Se [Diversifikation og korrelation](laerebog/diversifikation).

### Lineær regression (OLS)

En lineær regression forklarer en variabel $y$ med en eller flere forklarende variable:

$$
y_i = \alpha + \beta x_i + \varepsilon_i
$$

Mindste kvadraters metode (OLS) vælger $\alpha$ og $\beta$, så summen af de kvadrerede residualer $\sum \hat\varepsilon_i^2$ er mindst mulig. Med én forklarende variabel er løsningen

$$
\hat\beta = \frac{\sum (x_i - \bar x)(y_i - \bar y)}{\sum (x_i - \bar x)^2},
\qquad
\hat\alpha = \bar y - \hat\beta \bar x
$$

I finans er $y$ typisk en akties afkast og $x$ markedets; så er $\hat\beta$ aktiens *beta*. Se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

**Standardfejl.** Et skøn er usikkert, fordi det er beregnet på en tilfældig stikprøve. Residualvariansen skønnes som $s^2 = \sum \hat\varepsilon_i^2 / (n - k)$, hvor $k$ er antallet af estimerede koefficienter (2 med konstantled og én variabel). Standardfejlen på hældningen er

$$
SE(\hat\beta) = \sqrt{\frac{s^2}{\sum (x_i - \bar x)^2}}
$$

Generelt er kovariansmatricen for koefficienterne $s^2 (X^\top X)^{-1}$, og standardfejlene er kvadratrødderne af diagonalen.

**t-værdi.** $t = \hat\beta / SE(\hat\beta)$ måler, hvor mange standardfejl skønnet ligger fra 0. En tommelfingerregel er, at $|t| > 2$ svarer til signifikans på ca. 5 %-niveau. Men finansforskningen har testet så mange hypoteser, at Harvey, Liu og Zhu (2016) argumenterer for $|t| > 3$ for nye faktorer.

**R².** Forklaringsgraden er

$$
R^2 = 1 - \frac{\sum \hat\varepsilon_i^2}{\sum (y_i - \bar y)^2}
$$

andelen af variationen i $y$, som regressionen forklarer. Med én forklarende variabel er $R^2 = \rho_{xy}^2$. Et lavt R² betyder, at beta forklarer lidt af aktiens bevægelser; resten er selskabsspecifikt.

### Stikprøvestørrelse og støj

Standardfejlen på et gennemsnit er $\sigma / \sqrt{n}$. Det er en hård lov: for at halvere usikkerheden skal du have fire gange så mange data. For aktieafkast, hvor spredningen er stor i forhold til det forventede afkast, betyder det, at et gennemsnit over få år næsten intet siger om det sande forventede afkast (Merton 1980 påpegede, at forventede afkast er langt sværere at skønne end varianser).

### Survivorship bias

Ser du kun på de selskaber, fonde eller strategier, der eksisterer i dag, mangler dem, der gik konkurs, blev opkøbt eller lukket. Historikken ser bedre ud, end den var. Brown, Goetzmann, Ibbotson og Ross (1992) viste, hvordan overlevelse alene kan skabe tilsyneladende vedvarende performance hos fonde.

### Look-ahead bias

En test bruger oplysninger, som ikke var kendt på det tidspunkt, beslutningen skulle træffes: dagens indeksliste brugt bagud, reviderede makrotal i stedet for de første offentliggjorte, regnskabstal før de var offentlige. Resultatet ser forudsigende ud, men kunne ikke have været handlet.

### Overfitting og datamining

Prøver man mange varianter af en regel (vinduer, tærskler, kombinationer) på de samme data, vil den bedste se god ud alene af held. Med 20 uafhængige tests på 5 %-niveau er sandsynligheden for mindst ét falsk fund $1 - 0.95^{20} \approx 64$ %. Bailey, Borwein, López de Prado og Zhu (2014) viser, hvor let backtests overfittes. McLean og Pontiff (2016) finder, at offentliggjorte afkastmønstre i gennemsnit bliver betydeligt svagere efter offentliggørelsen, delvist fordi nogle af dem var datamining.

### Base rates

Et signals værdi afhænger af, hvor ofte den begivenhed, det skal forudsige, sker i forvejen. Bayes' sætning:

$$
P(A \mid S) = \frac{P(S \mid A)\, P(A)}{P(S \mid A)\, P(A) + P(S \mid \neg A)\, P(\neg A)}
$$

Et signal, der fanger de fleste store fald, men også ofte slår fejl i normale perioder, giver mange falske alarmer, når store fald er sjældne. Kahneman (2011) beskriver, hvordan mennesker systematisk overser basisraten.

## Sådan gør radaren

### Percentiler: andel strengt under

Når radaren placerer en værdi i sin egen historie, bruger den **andelen af historikken, der ligger strengt under** den nuværende værdi (`signals/valuation.py: percentile`):

$$
p = 100 \cdot \frac{\#\{\, x_i < v \,\}}{n}
$$

For Shiller CAPE (siden 1871 og siden 1990), Damodarans risikopræmie, AAII-spændet og put/call-forholdets 10-dages gennemsnit er **det seneste punkt udeladt** af historikken: dagens værdi sammenlignes med fortiden, ikke med sig selv. Put/call kræver mindst 60 dages historik i vinduet på {{settings:sentiment.putcall_lookback_days}} dage, før der vises en percentil. Se [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie) og [Put/call og AAII: kontrær sentiment](laerebog/sentiment).

To steder er dagens værdi med i historikken, så den kun tæller i nævneren: en ETF's P/E-percentil i sin egen ugentlige historik (kræver {{settings:valuation.etf_history_weeks}} snapshots) og CFTC-positioneringens percentil over {{settings:positioning.lookback_weeks}} uger. Her kan percentilen højst blive $100 \cdot (n-1)/n$.

### Rang inden for en gruppe

Momentumscoren bruger pandas' `rank(pct=True)`: rang divideret med antallet af værdier i gruppen, hvor lige store værdier får gennemsnitsrangen. Den højeste får 1 (100), den laveste $1/n$. Holdings, der sammenlignes med hele aktieuniverset, bruger derimod andelen strengt under. Forskellen forklares med tal i [Radarens momentumscore](laerebog/momentumscore).

### Regression med standardfejl

Risikostatistikken på tickerprofilen (`signals/risk.py`, se [Tickerprofilen](brugervejledning/tickerprofil)) kører OLS med konstantled på ugentlige afkast i DKK:

- Ugeafkast fra fredag til fredag; en igangværende uge udelades, fordi den dækker færre dage.
- Vinduer på {{settings:risk.windows.1y}} og {{settings:risk.windows.3y}} uger. Har en ticker færre end {{settings:risk.min_weeks}} fælles uger med ACWI, vises **ingen** statistik (null), aldrig et gæt.
- Koefficienter fra mindste kvadrater, residualvarians med $n - k$ frihedsgrader, standardfejl fra $s^2 (X^\top X)^{-1}$, t-værdier og R².
- Beta vises med sin standardfejl (±) og R²; Jensens alfa annualiseres (gange 52) og vises med sin t-værdi.
- *Downside beta* er samme regression kun på uger, hvor ACWI faldt, og kræver mindst 10 sådanne uger (fast i koden).
- Faktorregressionen kræver mindst $\max(\text{min\_weeks}, 4(k+1))$ uger for $k$ forklarende variable, så der er mindst fire observationer pr. koefficient (fast i koden).

Med den 3-måneders amerikanske statsrente fra FRED regnes der i merafkast over den risikofri rente; uden den på rå afkast.

### Survivorship bias i markedsbredden

Det amerikanske aktieunivers er **dagens** S&P 500 (fra SSGA's SPY-beholdningsliste). Når radaren beregner markedsbredde bagud (andel over 200-dages gennemsnit, nye 52-ugers højder minus lavpunkter), bruger den de nuværende medlemmer for hele historikken. Selskaber, der er røget ud af indekset, typisk efter kursfald, mangler; selskaber, der er kommet ind efter kursstigninger, er med. Historisk markedsbredde ser derfor lidt stærkere ud, end den var, og det er både survivorship og look-ahead bias. Radaren skriver det selv under *blind spots* på [Data og dækning](/data). Det samme gælder Discover, som kun kender dagens noteringer. Se [Markedsbredde](laerebog/markedsbredde).

## Regneeksempel

### Percentil og rang

En værdis historik (seneste punkt udeladt) er: 12, 15, 18, 20, 22, 25, 28, 30, 35, 40. I dag er værdien 29.

Syv værdier (12 til 28) er strengt under 29, så percentilen er $100 \cdot 7/10 = 70$.

Fire aktier har 3-måneders afkast på 3 %, 7 %, 7 % og 10 %:

| Afkast | Rang | `rank(pct=True)` | Andel strengt under |
|---|---|---|---|
| 3 % | 1 | 0,25 | 0,00 |
| 7 % | 2,5 | 0,625 | 0,25 |
| 7 % | 2,5 | 0,625 | 0,25 |
| 10 % | 4 | 1,00 | 0,75 |

De to metoder rangerer ens, men niveauet er forskudt.

### Regression

Fem ugers afkast for ACWI ($x$) og en aktie ($y$), i procent:

| Uge | $x$ | $y$ | $x \cdot y$ | $x^2$ |
|---|---|---|---|---|
| 1 | −2 | −3 | 6 | 4 |
| 2 | −1 | −1 | 1 | 1 |
| 3 | 0 | 0 | 0 | 0 |
| 4 | 1 | 2 | 2 | 1 |
| 5 | 2 | 2 | 4 | 4 |
| Sum | 0 | 0 | 13 | 10 |

Begge gennemsnit er 0, så $\hat\beta = 13/10 = 1.3$ og $\hat\alpha = 0$.

Residualer $y - 1.3x$: −0,4; 0,3; 0; 0,7; −0,6. Kvadratsum: 0,16 + 0,09 + 0 + 0,49 + 0,36 = 1,10. Med $n - k = 5 - 2 = 3$ frihedsgrader er $s^2 = 1.10/3 = 0.367$.

$$
SE(\hat\beta) = \sqrt{0.367 / 10} = 0.19, \qquad t = 1.3 / 0.19 \approx 6.8
$$

Total kvadratsum for $y$: 9 + 1 + 0 + 4 + 4 = 18, så $R^2 = 1 - 1.10/18 = 0.94$. Korrelationen er $13 / \sqrt{10 \cdot 18} = 0.97$, og $0.97^2 \approx 0.94$.

Med fem observationer ville radaren ikke vise noget: der kræves {{settings:risk.min_weeks}} uger.

### Hvor længe skal man vente på bevis?

En aktie har et forventet afkast på 1 % om måneden og en månedlig volatilitet på 8 %. Efter 12 måneder er standardfejlen på gennemsnittet $8 / \sqrt{12}$ = 2,31 %, og t-værdien for "afkastet er større end 0" er 1 / 2,31 = 0,43. For at nå $t = 2$ skal $\sqrt{n} = 2 \cdot 8 / 1 = 16$, altså $n = 256$ måneder, over 21 år.

### Basisrate

Antag, at et fald på over 10 % sker i 10 % af alle kvartaler. Et signal advarer før 80 % af faldene, men også i 20 % af de rolige kvartaler. Hvor ofte følges en advarsel af et fald?

$$
P(\text{fald} \mid \text{advarsel}) = \frac{0.8 \cdot 0.1}{0.8 \cdot 0.1 + 0.2 \cdot 0.9} = \frac{0.08}{0.26} \approx 31\ \%
$$

Signalet "fanger 80 %", men to ud af tre advarsler er falske alarmer.

## Faldgruber og begrænsninger

- **En percentil er relativ til sin historik.** En CAPE-percentil på 95 siden 1871 betyder noget andet end 95 siden 1990. Læs altid, hvilket vindue der er brugt.
- **Små grupper giver grove percentiler.** Med 20 aktier i en gruppe springer percentilen i trin på 5.
- **Beta fra et år er støjende.** Standardfejlen er ofte 0,2–0,4. Sammenlign 1- og 3-årsvinduet, og læs ± før du stoler på tallet.
- **t-værdier forudsætter uafhængige observationer** med konstant varians. Aktieafkast har perioder med høj og lav volatilitet og fede haler, så de rigtige standardfejl er ofte større.
- **Survivorship i radarens egne data.** Markedsbredde og Discover bygger på dagens lister. Historikken er pænere end virkeligheden.
- **Snapshots starter, når du starter.** Percentiler i radarens egne ugentlige snapshots (ETF-P/E) har kun den historik, radaren selv har samlet.
- **Mange signaler, mange tilfældige fund.** Radaren viser mange indikatorer samtidig. Nogle vil altid se ekstreme ud.

## Videre læsning

- Jeffrey M. Wooldridge: *Introductory Econometrics: A Modern Approach*, Cengage (mange udgaver).
- Campbell R. Harvey, Yan Liu og Heqing Zhu: "… and the Cross-Section of Expected Returns", *Review of Financial Studies*, 29(1), 2016.
- David H. Bailey, Jonathan M. Borwein, Marcos López de Prado og Qiji Jim Zhu: "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance", *Notices of the American Mathematical Society*, 61(5), 2014.
- R. David McLean og Jeffrey Pontiff: "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance*, 71(1), 2016.
- Stephen J. Brown, William Goetzmann, Roger G. Ibbotson og Stephen A. Ross: "Survivorship Bias in Performance Studies", *Review of Financial Studies*, 5(4), 1992.
- Robert C. Merton: "On Estimating the Expected Return on the Market", *Journal of Financial Economics*, 8(4), 1980.
- Daniel Kahneman: *Thinking, Fast and Slow*, Farrar, Straus and Giroux, 2011.
