# Beta, alfa og faktorer

## Intuition

Når markedet stiger 1 %, hvor meget stiger din aktie så typisk? Det er **beta**. En aktie med beta 1,3 bevæger sig i gennemsnit 30 % mere end markedet, både op og ned; en aktie med beta 0,6 bevæger sig kun lidt mere end halvt så meget.

Når du har trukket den del af afkastet fra, som markedet forklarer, er der en rest. Den gennemsnitlige rest er **alfa**: det afkast, som ikke kan forklares ved, at aktien bare fulgte markedet med en vis gearing. Resten, der svinger rundt om alfa fra uge til uge, er den **aktiespecifikke risiko**: nyheder om netop dette selskab.

Det er vigtige skel for en investor, der sammenligner med MSCI ACWI:

- Høj beta i et stigende marked ligner dygtighed, men er bare gearing. Det kunne du have fået billigere ved at eje mere ACWI.
- Alfa er det, der er værd at betale for, men det er svært at måle: tallet er næsten altid omgivet af stor statistisk usikkerhed.
- Aktiespecifik risiko kan spredes væk ved at eje mange papirer (se [Diversifikation og korrelation](laerebog/diversifikation)). Markedsrisikoen kan ikke.

Faktormodeller udvider ideen: i stedet for kun markedet forklares afkastet også med systematiske stilarter som momentum, value, kvalitet og lav volatilitet.

## Teori

### CAPM

Capital Asset Pricing Model (Sharpe, 1964; Lintner, 1965) siger, at i ligevægt er det forventede merafkast på et aktiv proportionalt med dets beta til markedsporteføljen:

$$
E[r_i] - r_f = \beta_i \left(E[r_m] - r_f\right)
$$

Kun markedsrisikoen belønnes, fordi den aktiespecifikke risiko kan diversificeres væk. Empirisk holder modellen dårligt: lav-beta-aktier har historisk givet mere, og høj-beta-aktier mindre, end CAPM forudsiger (Black, Jensen og Scholes, 1972; Frazzini og Pedersen, 2014). Men som måleværktøj, til at adskille markedseksponering fra resten, er den stadig standard.

### Beta

Beta estimeres ved en lineær regression af aktivets merafkast på markedets merafkast:

$$
r_{i,t} - r_{f,t} = \alpha + \beta\,(r_{m,t} - r_{f,t}) + \varepsilon_t
$$

Med mindste kvadraters metode (OLS) er hældningen

$$
\hat\beta = \frac{\operatorname{cov}(r_i, r_m)}{\operatorname{var}(r_m)} = \rho_{i,m}\cdot\frac{\sigma_i}{\sigma_m}
$$

Beta er altså korrelationen ganget med forholdet mellem volatiliteterne. En aktie kan have høj beta, fordi den svinger meget (høj $\sigma_i$), selv om korrelationen er moderat.

**Forklaringsgraden** $R^2$ er den andel af aktivets varians, markedet forklarer. I en regression med én forklarende variabel er $R^2 = \rho^2$. En typisk enkeltaktie har $R^2$ mellem 0,1 og 0,5 over for et globalt indeks; en bred ETF ligger tæt på 1.

### Standardfejl: hvorfor beta ± se betyder noget

Beta er et estimat fra en stikprøve. Standardfejlen er tilnærmelsesvis

$$
\text{se}(\hat\beta) \approx \sqrt{\frac{1 - R^2}{n - 2}}\cdot\frac{\sigma_i}{\sigma_m}
$$

med $n$ observationer. Et groft 95 %-interval er $\hat\beta \pm 2\,\text{se}$. Med 52 ugers data og en almindelig enkeltaktie er standardfejlen ofte 0,2–0,4, så en målt beta på 1,3 kan i virkeligheden ligge alt fra 0,7 til 1,9. Derfor viser radaren aldrig beta uden standardfejl.

Betaer er desuden ustabile over tid og har tendens til at bevæge sig mod 1 (Blume, 1971). Vasicek (1973) foreslog at krympe estimatet mod gennemsnittet i forhold til dets usikkerhed; mange dataleverandører bruger en simpel variant: $0.67\hat\beta + 0.33$. Radaren gør det ikke, men det er en god grund til at sammenligne 1- og 3-årsvinduet.

### Alfa

**Jensens alfa** (Jensen, 1968) er regressionens skæring: det gennemsnitlige merafkast, der er tilbage, når beta gange markedets merafkast er trukket fra. Med ugentlige data er årlig alfa cirka skæringen gange 52.

Alfa har sin egen t-værdi, $t = \hat\alpha / \text{se}(\hat\alpha)$. Med uafhængige residualer er $\text{se}(\hat\alpha) \approx \sigma_\varepsilon / \sqrt{n}$, så en årlig alfa skal være omtrent

$$
|\alpha_{år}| \gtrsim 2\cdot\frac{\sigma_{\varepsilon,år}}{\sqrt{T}}
$$

for at være signifikant ($|t| \ge 2$), hvor $T$ er antal år. Med 25 % aktiespecifik volatilitet og ét års data kræver det en alfa på omkring 50 % om året. Det er hovedårsagen til, at næsten alle målte alfaer for enkeltaktier er statistisk støj.

### Idiosynkratisk volatilitet

Standardafvigelsen af residualerne $\varepsilon_t$, annualiseret, er den **idiosynkratiske** (aktiespecifikke) volatilitet. Den totale varians deles op:

$$
\sigma_i^2 = \beta^2\sigma_m^2 + \sigma_\varepsilon^2
$$

Den første del er systematisk og kan ikke diversificeres væk; den anden kan. I en portefølje med mange papirer udligner residualerne hinanden, mens beta-delen bliver.

### Downside beta

Beta antager, at aktien reagerer ens på markedets stigninger og fald. Det gør mange ikke. **Downside beta** er beta estimeret kun i perioder, hvor markedet faldt. Ang, Chen og Xing (2006) finder, at aktier med høj downside beta historisk har givet en præmie: investorer kræver betaling for aktier, der falder mest, når alt andet også falder. For porteføljeopbygning er det praktisk: en aktie med beta 1,0 men downside beta 1,5 forstærker netop de dårlige perioder.

### Faktormodeller

Fama og French (1993) udvidede CAPM med to faktorer: størrelse (SMB, små minus store) og værdi (HML, høj minus lav book-to-market). Carhart (1997) tilføjede momentum (UMD, vindere minus tabere). Fama og French (2015) lagde rentabilitet og investering til. Modellen ser sådan ud:

$$
r_i - r_f = \alpha + \beta_m (r_m - r_f) + \sum_k \beta_k f_k + \varepsilon
$$

hvor hver $f_k$ er afkastet af en lang-kort faktorportefølje. Alfaen er nu det, der hverken forklares af markedet eller af faktorerne. En "alfa" fra CAPM forsvinder ofte, når momentum eller kvalitet kommer med: det var en faktoreksponering, ikke selskabsspecifik dygtighed. Faktorerne selv forklares i [Sektorer, temaer, faktorer og konjunkturcyklussen](laerebog/rotation-og-cyklus) og [Momentumeffekten](laerebog/momentumeffekten).

### Faktortilt med ETF'er

Akademiske faktorer er lang-korte porteføljer, som en privat investor ikke kan købe. Et praktisk alternativ er faktor-ETF'er (fx en momentum- eller kvalitets-ETF), som kun er lange. De indeholder derfor både markedet og faktoren. Trækker man markedets afkast fra, $f_k = r_{ETF,k} - r_m$, får man en tilnærmet faktor: merafkastet ved at tilte mod stilen. En positiv koefficient på $r_{MTUM} - r_m$ betyder: "aktien bevæger sig, som om den havde ekstra eksponering mod momentum ud over markedet".

Faktor-ETF'er korrelerer indbyrdes (kvalitet og lav volatilitet ligner hinanden; momentum skifter karakter med markedet), så de enkelte koefficienter er usikre, selv når modellen samlet forklarer meget. Det kaldes multikollinearitet. Se på t-værdierne, ikke kun på koefficienterne.

## Sådan gør radaren

Radaren har to betaer. Den grundige står i kortet *Risk vs ACWI (DKK, weekly)* på tickerprofilen (se [Tickerprofilen](brugervejledning/tickerprofil)); den simple står i kortet med tekniske indikatorer.

**Den grundige beta** (`signals/risk.py`, `window_stats`):

- Ugentlige afkast (fredag til fredag, uafsluttet uge udeladt) i kroner, både for aktivet og for ACWI.
- Vinduer på {{settings:risk.windows.1y}} og {{settings:risk.windows.3y}} uger, kun uger hvor begge har data; færre end {{settings:risk.min_weeks}} uger giver intet tal.
- Merafkast over den 3-måneders amerikanske statsrente (FRED DGS3MO), omregnet til en ugerente som i [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown). Mangler renten, bruges rå afkast, og kortet siger det.
- OLS med skæring. Kortet viser *Beta ± se (R²)*: beta, dens standardfejl og forklaringsgraden.
- *Alpha (t)*: skæringen gange 52, med skæringens t-værdi.
- *Stock-specific vol*: standardafvigelsen af residualerne med 2 frihedsgrader trukket fra (skæring og hældning), gange $\sqrt{52}$.
- *Downside beta*: samme regression, men kun på de uger, hvor ACWI faldt. Der kræves mindst 10 sådanne uger (fast i koden); ellers vises intet.

**Faktortilt** (`factor_loadings`), vist som *Factor tilts* under samme kort:

- Aktivets merafkast regresseres på ACWI's merafkast og på spændet (ETF minus ACWI) for hver af faktor-ETF'erne {{settings:risk.factors}} (`risk.factors`) samt aktivets sektor-ETF, hvis den kendes. Alt i kroner, ugentligt.
- Det længste vindue bruges ({{settings:risk.windows.3y}} uger).
- En regressor, der slet ikke bevæger sig, droppes. Der kræves mindst $\max(\text{min\_weeks},\, 4(k+1))$ uger, hvor $k$ er antal regressorer, så der er rimeligt mange observationer pr. koefficient.
- Hver faktor vises med sin koefficient og t-værdi; en badge fremhæves, når $|t| \ge 2$. Modellens samlede $R^2$ og den tilbageværende alfa vises også, med grundlaget: *excess over T-bills* (merafkast over renten) eller *raw returns*, når renten mangler.

**Den simple beta** (`signals/technicals.py`, `beta_corr`): kovarians over varians på ugentlige afkast over de seneste 52 uger (mindst 26), uden risikofri rente og uden standardfejl. Den beregnes på kurser i aktiens egen noteringsvaluta mod ACWI i dollar, ikke i kroner. Den vises som *Beta / correlation vs ACWI* sammen med korrelationen. Fundamentkortet viser desuden Yahoos egen beta ved siden af radarens.

> **Bemærk:** De to betaer måler ikke helt det samme. Den grundige er i kroner over for ACWI i kroner med merafkast; den simple er i lokal valuta over for ACWI i dollar. For en dansk aktie, hvor kronen følger euroen, kan dollarens udsving give en mærkbar forskel. Brug den grundige, når du vurderer risiko for din formue i kroner.

Datakonventionerne nævner et eksempel: energisektor-ETF'en XLE havde engang en 1-års beta på −0,9, mens 3-årsbetaen var +0,45. Det er et godt argument for altid at se de to vinduer side om side.

## Regneeksempel

En aktie har over 52 uger en ugentlig volatilitet på 4 %, ACWI har 2 %, og korrelationen er 0,6. Lad os sige, at regressionens skæring er 0,1 % om ugen.

**Beta.** $\beta = 0.6 \cdot 4/2 = 1.2$.

**Forklaringsgrad.** $R^2 = 0.6^2 = 0.36$. Markedet forklarer 36 % af aktiens varians.

**Idiosynkratisk volatilitet.** Den uforklarede varians er $(1 - 0.36)\cdot 0.04^2 = 0.001024$, altså $\sigma_\varepsilon = 3.2\,\%$ om ugen. Årligt: $3.2\,\% \cdot \sqrt{52} \approx 23.1\,\%$. Til sammenligning er den systematiske del $1.2 \cdot 2\,\% \cdot \sqrt{52} \approx 17.3\,\%$ om året.

**Standardfejl på beta.**

$$
\text{se}(\hat\beta) \approx \sqrt{\frac{0.64}{50}}\cdot\frac{0.04}{0.02} = 0.113 \cdot 2 \approx 0.23
$$

Kortet ville vise noget i retning af *1,20 ± 0,23 (0,36)*. Et 95 %-interval er cirka 0,75 til 1,65. Med 156 uger og samme tal falder standardfejlen til $\sqrt{0.64/154}\cdot 2 \approx 0.13$.

**Alfa.** Årligt: $0.1\,\% \cdot 52 = 5.2\,\%$. Standardfejlen på den ugentlige skæring er cirka $3.2\,\% / \sqrt{52} = 0.44\,\%$, så $t \approx 0.1/0.44 \approx 0.23$. En årlig alfa på 5,2 % lyder af noget, men en t-værdi på 0,23 betyder, at den ikke kan skelnes fra held. For at nå $t = 2$ med ét års data skulle den ugentlige skæring være cirka 0,89 %, svarende til 46 % om året. Over tre år kræves stadig omkring $2 \cdot 23.1\,\% / \sqrt{3} \approx 27\,\%$ om året.

**Downside beta.** Antag, at ACWI faldt i 22 af de 52 uger, og at regressionen på netop de uger giver en hældning på 1,5. Så forstærker aktien markedets dårlige uger mere end dens almindelige beta på 1,2 antyder. Med kun 22 observationer er standardfejlen på downside beta dog endnu større end på den almindelige beta.

## Faldgruber og begrænsninger

- **Støj.** Beta fra et år er støjfyldt, alfa fra et år er næsten altid støj. Se på standardfejl og t-værdi, før du læser noget ind i tallene.
- **Ustabilitet.** Et selskab kan ændre karakter (ny gæld, ny forretning), og en sektor kan skifte regime (energi i en oliekrise). Historisk beta er ikke fremtidig beta.
- **Valuta.** Beta i kroner indeholder både aktie- og valutaeffekter. En amerikansk aktie, der ejes i kroner, har en anden beta over for ACWI i kroner end over for S&P 500 i dollar.
- **Ugefrekvens.** Ugentlige afkast reducerer problemet med asynkrone lukketider, men for meget illikvide aktier undervurderes beta stadig, fordi kursen reagerer med forsinkelse.
- **Faktor-ETF'er er ikke rene faktorer.** De er lange porteføljer med deres egne konstruktionsregler, og deres spænd til markedet indeholder sektorskævheder. Tolk en ladning som "bevæger sig som", ikke som "er".
- **Multikollinearitet.** Kvalitet og lav volatilitet, eller momentum og vækst, korrelerer. Den samlede model kan forklare meget, mens hver enkelt koefficient er usikker.
- **Overfortolkning af alfa.** En positiv alfa i et vindue er ikke bevis for, at noget vil fortsætte. Den kan skyldes en faktor, der ikke er i modellen, eller ren tilfældighed.

## Videre læsning

- William F. Sharpe, "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk", *Journal of Finance* 19(3), 1964.
- Michael C. Jensen, "The Performance of Mutual Funds in the Period 1945–1964", *Journal of Finance* 23(2), 1968.
- Marshall E. Blume, "On the Assessment of Risk", *Journal of Finance* 26(1), 1971.
- Eugene F. Fama og Kenneth R. French, "Common Risk Factors in the Returns on Stocks and Bonds", *Journal of Financial Economics* 33(1), 1993.
- Mark M. Carhart, "On Persistence in Mutual Fund Performance", *Journal of Finance* 52(1), 1997.
- Andrew Ang, Joseph Chen og Yuhang Xing, "Downside Risk", *Review of Financial Studies* 19(4), 2006.
- Andrea Frazzini og Lasse Heje Pedersen, "Betting Against Beta", *Journal of Financial Economics* 111(1), 2014.
