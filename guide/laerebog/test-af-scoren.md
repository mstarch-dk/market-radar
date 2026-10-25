# Test af momentumscoren

Er [momentumscoren](laerebog/momentumscore) god til at finde aktier, der klarer sig bedre end de andre bagefter? Det spørgsmål kan ikke besvares med én portefølje på én dato. Dette kapitel forklarer, hvordan radaren tester scoren på historikken, hvilke tal testen giver, og hvorfor de skal læses med forsigtighed.

## Intuition

Forestil dig, at du hver måned i fem år rangerede alle aktier efter scoren og så efter, hvordan de klarede sig de næste måneder. Virker scoren, skal de bedst placerede i gennemsnit klare sig bedre end de dårligst placerede, og det skal ske i de fleste måneder, ikke kun i én heldig periode.

Det er præcis, hvad testen gør. Tre ting er afgørende:

- **Mange datoer.** Én kurv kan være heldig. 60 månedlige rangeringer kan også være det, men meget sjældnere.
- **Den rigtige målestok.** Steg alle aktier, siger det intet om scoren. Derfor måles hver aktie mod gennemsnittet af *alle* aktier i universet samme dag (den ligevægtede gennemsnitsaktie), ikke mod ACWI.
- **Kun det, der var kendt.** Scoren på en dato beregnes kun med kurser til og med den dato. Resultatet måles fra næste handelsdag.

## Teori

### Informationskoefficienten (IC)

IC er rangkorrelationen (Spearman) mellem scoren på datoen og afkastet bagefter, over alle aktier:

$$
IC_t = \operatorname{corr}\big(\operatorname{rang}(s_{i,t}),\ \operatorname{rang}(r_{i,t \to t+h})\big)
$$

IC er 1, hvis rækkefølgen holder perfekt, 0, hvis der ingen sammenhæng er, og negativ, hvis vinderne bagefter taber. For signaler på aktier er en gennemsnitlig IC på 0,02–0,05 almindelig, og 0,05–0,10 er stærkt. Et lavt tal er altså ikke i sig selv dårligt: det gælder om, at det er stabilt.

### Kvintiler og spredning

Aktierne deles i fem lige store grupper efter scoren. For hver gruppe beregnes det gennemsnitlige *merafkast* mod gennemsnitsaktien. Spredningen Q5 − Q1 (bedste minus dårligste femtedel) er det, en simpel lang-kort-strategi ville have tjent, før omkostninger. Stiger tallene jævnt fra Q1 til Q5, er sammenhængen *monoton*, hvilket er et godt tegn.

### t-tal med Newey-West

Gennemsnittet af månedlige IC'er har en usikkerhed. Et t-tal over cirka 2 betyder, at gennemsnittet næppe er 0 ved et tilfælde. Med horisonter over en måned overlapper perioderne: et 6-måneders afkast fra januar og et fra februar deler fem måneder. Så er nabomånederne ikke uafhængige, og et almindeligt t-tal bliver for stort. Newey-West-standardfejlen korrigerer for det ved at medregne korrelationen mellem nabomåneder op til $h - 1$ måneder tilbage:

$$
\hat\sigma^2_{NW} = \hat\gamma_0 + 2 \sum_{k=1}^{L} \Big(1 - \frac{k}{L+1}\Big) \hat\gamma_k, \qquad t = \frac{\bar x}{\sqrt{\hat\sigma^2_{NW} / n}}
$$

hvor $\hat\gamma_k$ er autokovariansen ved forskydning $k$ og $L = h - 1$.

### Overfitting og holdout

Prøver man ti varianter af scoren, vil én af dem næsten altid se bedre ud, også selv om ingen af dem er bedre. Den klassiske forsvarslinje er en *holdout*: en periode, der ikke bruges til at vælge. En variant tæller kun som en forbedring, hvis den er bedre både før og i holdout-perioden.

## Sådan gør radaren

`uv run radar study score` (se [Test momentumscoren på historikken](brugervejledning/scoretest)):

- **Datoer**: den sidste handelsdag i hver afsluttet måned, fra den første dag med nok historik til scoren.
- **Horisonter**: 1, 3, 6 og 12 måneder (21, 63, 126 og 252 handelsdage) fra næste handelsdag (`backtest.fill`: {{settings:backtest.fill}}).
- **Afkast** i noteringsvalutaen på justerede kurser (udbytte medregnet), som merafkast mod gennemsnitsaktien. Toppen af listen gives også i DKK mod ACWI i DKK.
- **En dato tæller** kun, hvis mindst {{settings:backtest.study_min_names}} aktier har både en score og et afkast. En aktie uden afkast bagefter (fx afnoteret) tælles og udelades, den tælles aldrig som 0.
- **Opdeling**: pr. år, pr. regime på datoen, pr. region (rangeret inden for regionen) og før/efter holdout-datoen {{settings:backtest.study_holdout_from}}.
- **Varianter**: komponenterne alene (12-1, 6 og 3 måneder, plus 1 måned som tjek af kortsigtet vending), scoren rangeret inden for regionen, med trend først, volatilitetsjusteret, afstanden til 52-ugers toppen og scoren rangeret inden for sektoren (med dagens sektorer, så ikke helt som på datoen). Desuden fem varianter, der blev valgt på forhånd, før resultaterne var kendt:
  - *score_skip*: scoren med den seneste måned sprunget over i alle tre dele (12-1, 6-1 og 3-1 måneder).
  - *resid* (residual momentum): 12-1-måneders afkastet fratrukket beta gange ACWI's afkast, måned for måned i DKK, divideret med sin egen volatilitet. Beta måles på ugeafkast over op til 104 uger (mindst 52). Det er en forenkling af Blitz, Huij og Martens, som fjerner tre faktorer og også alfa; med kun få års historik ville et skæringspunkt sluge det meste af det vindue, der måles. Vinduerne står fast i koden.
  - *fip* (frog in the pan): andelen af op-dage minus ned-dage i 12-1-vinduet med fortegn efter afkastet, så et afkast skabt af mange små bevægelser rangerer over det samme afkast skabt af få spring.
  - *score_fip*: scoren og *fip* vægtet 2:1.
  - *vol_surge*: kolonnen *Vol 20d/120d* fra [Momentum](/momentum) alene. Den viser, om højere volumen end normalt siger noget om afkastet bagefter.
- **Dom**: en variant er en *candidate improvement*, når dens gennemsnitlige IC er højere end scorens både før og i holdout-perioden, holdout-IC'ens t-tal er over 2, og forskellen til scoren i holdout-perioden selv har et t-tal over 2. Ellers står der fx *better in-sample only (likely chance)*. Rapporten siger, hvor mange varianter der er prøvet.
- **Stopreglen over mange datoer** (`--exits 6`): hver dags 15 bedste aktier beholdt i 6 måneder mod de samme køb med reglen fulgt (begge halvdele, kun stop, kun take-profit), med kurtage på {{settings:backtest.fee_bps}} basispoint pr. handel.

### Kvalitets- og værdiscoren

`--signal quality`, `value` eller `qv` tester [kvalitets- og værdiscoren](laerebog/kvalitetsscore) med de samme datoer, horisonter, statistikker og domme, med scoren selv som basislinje:

- **Universet** er de amerikanske aktier med regnskaber fra SEC EDGAR. Andre regioner har ingen datoer for, hvornår tallene blev kendt.
- **Som på datoen**: et tal tæller fra dagen efter sin indleveringsdato plus {{settings:backtest.fundamentals_lag_days}} dag (`backtest.fundamentals_lag_days`). Den seneste version kendt på datoen bruges, så en rettelse indleveret senere ikke ændrer fortiden. Markedsværdien er aktieantallet kendt på datoen gange datoens kurs. Scorerne regnes af appens egen kode, med ét fravalg: tjekket mod Yahoos markedsværdi springes over, fordi Yahoos tal er dagens.
- **Sammenlignelige aktier** er de amerikanske. Appen samler alle regioner, så percentilerne er ikke helt de samme som på siden *Quality & value*.
- **Varianter**: de fire søjler, de enkelte nøgletal, gross profitability (bruttoavance / aktiver; Novy-Marx), magic formula (gennemsnittet af percentilerne for ROIC og EBIT/EV; Greenblatt), K+V og momentum 1:1, og momentumscoren rangeret blandt de samme aktier.
- **Korrelation med momentum**: for hver dato rangkorrelationen mellem basislinjen og momentumscoren. Historisk har værdi og momentum været negativt korrelerede (Asness, Moskowitz og Pedersen), og det er grunden til at bruge begge.

En ændring af scoren i appen er en separat beslutning: en post i journalen og en ændring af indstillinger og vejledning. Testen ændrer aldrig noget selv.

Resultaterne af alle fire scorer, testen over årtier og resultaterne fremad står på siden [Evidence](/evidence); se [Evidens-siden](brugervejledning/scoretest#evidens-siden). Hver rapport gemmer et fingeraftryk af reglen, den testede: de indstillinger, tallene afhænger af, og scorens version. Ændres en af dem, står rapporten som en ældre regel, indtil testen køres igen.

### Fremad uden t-tal

Papirsporet, A/B-testen og de frosne porteføljeforslag måler hver kurv fra dens egen dag til i dag. En kurv fra marts og en fra april deler alle månederne fra april, så deres resultater er langt fra uafhængige. Et almindeligt t-tal for gennemsnittet ville tælle dem som uafhængige og overvurdere, hvor sikkert resultatet er. Med få kurve hjælper Newey-West heller ikke meget, fordi korrektionen selv skal skønnes ud fra de samme få tal. Siden viser derfor antallet og andelen, der slog ACWI, uden t-tal, og en kurv tæller først med, når den har en vis alder. Først når papirsporet har kørt i flere år, siger gennemsnittet noget, og så er det den reneste test af scoren, radaren har.

## Regneeksempel

### Én dato

Ti aktier rangeres efter score og deles i fem grupper á to. Gennemsnitsaktien stiger 2 % de næste tre måneder.

| Kvintil | Aktiernes afkast | Gennemsnit | Merafkast |
|---|---|---|---|
| Q1 (laveste score) | −4 %, 0 % | −2 % | −4 % |
| Q2 | 1 %, 1 % | 1 % | −1 % |
| Q3 | 3 %, 1 % | 2 % | 0 % |
| Q4 | 2 %, 4 % | 3 % | +1 % |
| Q5 (højeste score) | 6 %, 2 % | 4 % | +2 % |

Spredningen Q5 − Q1 er 2 % − (−4 %) = 6 procentpoint. Rækkefølgen er næsten monoton, så IC'en er høj, men på én dato siger det lidt.

### Mange datoer

Sig, at scoren over 54 datoer har en gennemsnitlig IC på 0,06 med et Newey-West-t-tal på 2,0, og at IC'en er positiv i 72 % af månederne. Det er et beskedent, men nogenlunde stabilt signal. Er t-tallet derimod 0,7, kan gennemsnittet lige så godt være 0.

## Faldgruber og begrænsninger

- **Overlevelsesbias.** Universet er dagens S&P 500 og dagens udvalgte lister. Aktier, der er røget ud, mangler, og aktier, der kom med efter en stor stigning, er med. Det gør momentum bedre, end det var, og mere jo længere tilbage testen går. Scorens regel testes derfor også på brancher og lande uden overlevelsesbias; se [Testen over årtier](brugervejledning/scoretest#testen-over-årtier).
- **Få uafhængige perioder.** Fem års historik er cirka 20 uafhængige kvartaler. Et resultat, der hviler på 2022 eller 2023 alene, er skrøbeligt; se opdelingen pr. år.
- **Regionen.** Den samlede rangering blander cirka 500 amerikanske og godt 100 andre aktier. Har USA ført, ligner det dygtighed. Se IC'en inden for hver region.
- **Momentumkrak.** Momentum kan virke i årevis og så tabe kraftigt i en skarp vending opad efter et fald. En periode uden sådan en vending overvurderer signalet.
- **Samme IC, anden top.** To varianter kan rangere hele universet lige godt og alligevel vælge vidt forskellige 15 bedste. *resid* og *fip* vælger roligere aktier, så deres top giver typisk mindre afkast end scorens, selv når IC'en er den samme. Se både IC og *top N*.
- **Toppen er skæv.** Gennemsnittet for de 15 bedste kan bæres af én eller to aktier, der steg meget. Andelen, der slog gennemsnitsaktien (*hit*), siger mere om, hvor bredt det virker.
- **Justerede kurser skrives om.** Efter hvert udbytte justeres hele den tidligere kursrække. Det flytter kursniveauerne, men næsten ikke afkastene, så tallene ændrer sig kun lidt fra kørsel til kørsel.
- **Ingen skat.** Afkastene er før skat; kurtage er kun med i testen af stopreglen.
- **Regnskaber bevæger sig langsomt.** Kvalitets- og værdiscoren skifter mest, når et nyt regnskab kommer, så nabomåneder deler det meste af deres information, og testen har endnu færre uafhængige perioder end momentum. Sektorerne og bank/forsikring-sættet er dagens.
- **Én kurv er ikke et bevis.** En [hindsight-kurv](brugervejledning/scoretest#hindsight-kurve-med-claude) viser et eksempel. Testen over alle måneder er beviset, og selv den er kun så god som dataene.

## Videre læsning

- Richard C. Grinold og Ronald N. Kahn: *Active Portfolio Management*, 2. udgave, 1999 (informationskoefficienten).
- Whitney K. Newey og Kenneth D. West: "A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix", *Econometrica*, 55(3), 1987.
- Clifford S. Asness, Tobias J. Moskowitz og Lasse Heje Pedersen: "Value and Momentum Everywhere", *Journal of Finance*, 68(3), 2013.
- Kent Daniel og Tobias J. Moskowitz: "Momentum Crashes", *Journal of Financial Economics*, 122(2), 2016.
- David Blitz, Joop Huij og Martin Martens: "Residual Momentum", *Journal of Empirical Finance*, 18(3), 2011.
- Zhi Da, Umit G. Gurun og Mitch Warachka: "Frog in the Pan: Continuous Information and Momentum", *Review of Financial Studies*, 27(7), 2014.
- Charles M. C. Lee og Bhaskaran Swaminathan: "Price Momentum and Trading Volume", *Journal of Finance*, 55(5), 2000.
- Campbell R. Harvey, Yan Liu og Heqing Zhu: "… and the Cross-Section of Expected Returns", *Review of Financial Studies*, 29(1), 2016 (om mange tests og for lave t-tal).
- David H. Bailey og Marcos López de Prado: "The Deflated Sharpe Ratio", *Journal of Portfolio Management*, 40(5), 2014.
