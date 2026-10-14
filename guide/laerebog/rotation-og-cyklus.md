# Sektorer, temaer, faktorer og konjunkturcyklussen

## Intuition

Aktiemarkedet bevæger sig sjældent i takt. Selv når indekset står nogenlunde stille, flytter pengene sig ofte under overfladen: fra teknologi til forsyning, fra USA til Europa, fra vækstaktier til værdiaktier. Det kaldes rotation.

Den klassiske forklaring er konjunkturcyklussen. Forskellige brancher tjener deres penge på forskellige tidspunkter i cyklussen. En bank tjener godt, når renten stiger og kreditten vokser. En byggevirksomhed har brug for, at folk køber huse. Et forsyningsselskab sælger strøm, uanset hvordan det går. Markedet forsøger at prissætte, hvad der kommer, så aktierne skifter førerposition *før* økonomien gør.

Den forklaring er nyttig, men den er ikke hele sandheden. Rotation drives også af renter, valuta, politik, teknologiske gennembrud (temaer) og simpel investoradfærd (faktorer som momentum). Dette kapitel giver dig sprogbrugen og de typiske mønstre, og det forklarer, hvorfor radaren ikke prøver at gætte på fasen i cyklussen, men i stedet *måler* rotationen, som den sker.

## Teori

### Konjunkturcyklussens faser

En konjunkturcyklus beskrives ofte i fire faser. Inddelingen her følger den, der bruges af blandt andre Fidelity, og bygger på Stovalls (1996) sektormodel:

| Fase | Økonomien | Renter og kredit | Typisk stærke sektorer |
|---|---|---|---|
| **Tidlig** (opsving) | Vækst tager til fra bunden | Lave renter, kreditten åbner | Finans, cyklisk forbrug, industri, ejendomme, small caps |
| **Midt** | Solid, bred vækst | Renter normaliseres | Teknologi, kommunikation, industri |
| **Sen** | Vækst topper, inflation stiger | Stigende renter, strammere kredit | Energi, materialer, sundhed, dagligvarer |
| **Recession** | Faldende aktivitet | Rentefald, kreditspænd udvides | Dagligvarer, forsyning, sundhed |

Fasernes længde er meget forskellig. Midtfasen har historisk været den længste (ofte flere år), recessionen den korteste (typisk under et år). Aktiemarkedet bunder normalt *inde i* recessionen, længe før den officielt er slut.

### Cykliske og defensive sektorer

Den mest brugbare forenkling er opdelingen i to lejre:

- **Cykliske sektorer** har indtjening, der svinger meget med økonomien: cyklisk forbrug, finans, industri, materialer, energi og i nogen grad teknologi. De har typisk en beta over 1.
- **Defensive sektorer** sælger ting, folk køber uanset konjunkturen: dagligvarer, forsyning, sundhed. De har typisk en beta under 1 og opfører sig delvis som obligationer, fordi deres stabile udbytter bliver mere værd, når renten falder.

Når cykliske sektorer slår defensive, er det et tegn på risikovillighed og vækstforventninger. Når defensive fører, er markedet i forsvarsposition. Det er samme logik, som ligger bag flere rækker i [risk-on/risk-off-afstemningen](laerebog/risk-on-risk-off). Se [Beta, alfa og faktorer](laerebog/beta-og-alfa) for beta.

### Regioner og lande

Regioner roterer også, ofte drevet af:

- **Dollaren.** En svagere dollar har historisk hjulpet emerging markets og råvareeksportører (se [Kredit, renter og dollar](laerebog/kredit-renter-dollar)).
- **Sektorsammensætning.** Europa har mange banker, industri og råvarer og relativt lidt teknologi; USA og Taiwan er tunge i teknologi. En regions relative styrke er derfor ofte en skjult sektorsatsning.
- **Lokal politik og pengepolitik.** Rentebeslutninger, finanspolitik og handelspolitik rammer regioner forskelligt.

### Temaer

Temaer er tværgående historier, der ikke følger sektorgrænserne: halvledere, forsvar, uran og kernekraft, elnet, cybersikkerhed. De drives typisk af strukturelle skift (teknologi, geopolitik, energiomstilling) mere end af konjunkturen. Temaer har ofte stærk momentum, når de først får fat, men også høj volatilitet, koncentrerede beholdninger og en tendens til at blive dyre, når fortællingen er bredt kendt.

### Faktorer

En faktor er en egenskab, der går på tværs af sektorer, og som forskningen har knyttet til afkast. De mest kendte, der alle findes som ETF'er:

| Faktor | ETF | Idé | Kilde |
|---|---|---|---|
| Momentum | MTUM | Det, der er steget, fortsætter | Jegadeesh og Titman (1993); Carhart (1997) |
| Value | VLUE | Billige aktier slår dyre over tid | Fama og French (1993) |
| Quality | QUAL | Profitable, stabile selskaber med lav gæld | Asness, Frazzini og Pedersen (2019) |
| Min volatility | USMV | Lavvolatile aktier giver bedre risikojusteret afkast end teorien forudsiger | Ang m.fl. (2006); Frazzini og Pedersen (2014) |

Faktorer opfører sig også forskelligt i cyklussen. Value og small caps har ofte været stærke i den tidlige fase; quality og lav volatilitet holder bedst i sen fase og recession; momentum kan lide store tab lige efter et markedsvendepunkt, når sidste års tabere pludselig fører (Daniel og Moskowitz, 2016). Asness, Moskowitz og Pedersen (2013) viser, at value og momentum findes i alle større aktivklasser og er negativt korrelerede med hinanden.

### Hvad siger evidensen?

Mønstrene i tabellen ovenfor er gennemsnit over mange cyklusser, og hver cyklus er anderledes. Tre forbehold:

1. **Faserne kendes først bagefter.** NBER, der daterer amerikanske recessioner, offentliggjorde først i december 2008, at recessionen var begyndt i december 2007. Den, der venter på at kende fasen, kommer for sent.
2. **Selv perfekt viden giver beskedne gevinster.** Stangl, Jacobsen og Visaltanachoti (2009) fandt, at en sektorrotationsstrategi, der kendte de faktiske konjunkturfaser på forhånd, kun slog markedet med et par procentpoint om året, og at gevinsten forsvandt, når faserne skulle gættes i realtid og handelsomkostninger regnes med.
3. **Markedet er hurtigere end data.** Aktiekurser er selv en af de bedste ledende indikatorer. Når sektorrotationen er synlig i kurserne, er den allerede delvis prissat.

Derfor er det mere robust at *måle* rotationen direkte (med [relativ styrke](laerebog/relativ-styrke) og [rotationsgrafen](laerebog/rrg)) og bruge cyklusfortællingen som en forklaring på, hvad du ser, end at forudsige fasen og placere sig derefter. Momentum i sektorer og brancher er bedre dokumenteret end cyklustiming (Moskowitz og Grinblatt, 1999).

## Sådan gør radaren

### Grupperne

Radaren følger fem grupper af ETF'er fra `etf_groups` i `config/universe.yaml`:

| Gruppe | Indhold | Side |
|---|---|---|
| *US sectors* | De 11 S&P 500-sektorer (XLK, XLF, XLE, XLU osv.) | [Sektorrotation](/rotation) |
| *Europe sectors (STOXX 600)* | 17 STOXX 600-sektorer (iShares, Xetra) | [Sektorrotation](/rotation) |
| *Regions & countries* | USA, Europa, Japan, emerging markets, Kina, Indien, de nordiske lande m.fl. | [Sektorrotation](/rotation) |
| *Themes* | Halvledere, forsvar, uran, robotter, cybersikkerhed, guld, biotek, vand, elnet m.fl. | [Temaer og faktorer](/themes) |
| *Factors & style* | MTUM, QUAL, USMV, VLUE, vækst/værdi (IWF/IWD), høj beta/lav volatilitet (SPHB/SPLV) | [Temaer og faktorer](/themes) |

Hver ETF får relative afkast mod ACWI over 1, 3 og 6 måneder, en score og en rang inden for gruppen (se [Relativ styrke](laerebog/relativ-styrke#sådan-gør-radaren)) samt en kvadrant i [rotationsgrafen](laerebog/rrg). Europæiske sektorer får desuden en kvadrant mod STOXX 600.

Radaren forsøger **ikke** at bestemme konjunkturfasen og har ingen regel, der siger "sen fase, køb energi". Cyklussen ses indirekte gennem [OECD's ledende indikatorer](laerebog/ledende-indikatorer), [kreditspænd og rentekurven](laerebog/kredit-renter-dollar) og [kobber/guld](laerebog/raavarer) i regimet.

### Faktorpar

Faktorgruppen er bygget til at blive læst i par, som kommentaren i `universe.yaml` siger:

- **IWF mod IWD** (Russell 1000 vækst mod værdi): hvilken stil betaler markedet for?
- **SPHB mod SPLV** (høj beta mod lav volatilitet): et direkte mål for risikovilje. Fører SPHB, vil markedet have risiko.

De samme fire faktorfonde (`risk.factors`: {{settings:risk.factors}}) bruges også i faktorregressionen på tickerprofilen, se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

### Sådan bruger du siderne

Radarens horisont er 1–6 måneder. En fornuftig arbejdsgang:

1. **Start med regimet.** Er afstemningen risk-on, er cykliske sektorer og høj beta mere relevante; er den risk-off, er det relevant, at defensive sektorer og lav volatilitet fører. Se [Regime](/regime).
2. **Se grupperne under ét.** Fører cykliske eller defensive sektorer? Fører SPHB eller SPLV? Fører vækst eller værdi? Et samlet mønster er mere troværdigt end én fond.
3. **Find skiftene.** Fonde, der bevæger sig fra *Improving* til *Leading*, og fonde med store positive *Δ rank* er kandidater til nærmere undersøgelse. Fonde, der går fra *Leading* til *Weakening*, er værd at holde øje med, hvis du ejer dem.
4. **Tjek det absolutte billede.** *Abs 3m* og *>200d*: stiger fonden faktisk?
5. **Find det, du kan købe.** Brug UCITS-kolonnen og positivlisten (nedenfor) og læs [tickerprofilen](brugervejledning/tickerprofil).

Se også [brugervejledningen til sektorrotation](brugervejledning/sektorrotation) og [temaer og faktorer](brugervejledning/temaer-og-faktorer).

### UCITS-tvillinger og positivlisten

Signalerne beregnes på likvide, amerikansk noterede ETF'er, fordi de har lang historik og gode data. Men som privatinvestor i EU kan du normalt ikke købe dem: de mangler det dokument (KID), som EU's PRIIPs-regler kræver. Derfor angiver `universe.yaml` for mange fonde en **UCITS-tvilling**, en europæisk registreret ETF, der følger samme tema, med ticker, navn og ISIN.

Tvillingen er ikke identisk. Indekset kan være et andet (fx global i stedet for amerikansk), og afkastet kan derfor afvige betydeligt. Tjek altid på justETF.

Kolonnen *Positive list* viser, om ISIN'en står på SKATs liste over aktiebaserede investeringsselskaber (positivlisten). Det har betydning for beskatningen i frie midler og for, om fonden kan ligge på en aktiesparekonto. Detaljerne står i [Dansk skat for investorer](laerebog/skat).

## Regneeksempel

Antag, at tabellen for amerikanske sektorer viser disse 3-måneders relative afkast mod ACWI (*Rel 3m*):

| Cyklisk | Rel 3m | Defensiv | Rel 3m |
|---|---|---|---|
| Industri (XLI) | +3,1 pp | Dagligvarer (XLP) | −2,5 pp |
| Finans (XLF) | +2,4 pp | Forsyning (XLU) | −3,0 pp |
| Cyklisk forbrug (XLY) | +1,8 pp | Sundhed (XLV) | −1,2 pp |

**Gennemsnit:**

- Cykliske: (3,1 + 2,4 + 1,8) / 3 = 7,3 / 3 = +2,43 pp
- Defensive: (−2,5 − 3,0 − 1,2) / 3 = −6,7 / 3 = −2,23 pp
- Forskel: 2,43 − (−2,23) = 4,67 pp i cykliske sektorers favør over 3 måneder.

**Faktorparrene:** IWF (vækst) +2,0 pp og IWD (værdi) −1,5 pp giver 3,5 pp til vækst. SPHB (høj beta) +4,0 pp og SPLV (lav volatilitet) −3,0 pp giver 7,0 pp til høj beta.

**Tolkning.** Alle tre målinger peger samme vej: markedet betaler for cyklikalitet og risiko. Det passer med en tidlig til midt-fase i lærebogsskemaet, og det passer med et risk-on-regime. Hvis regimet samtidig viste stigende kreditspænd og faldende markedsbredde, ville det være en uoverensstemmelse værd at undersøge: en smal, risikovillig rotation båret af få navne.

Bemærk, hvad eksemplet *ikke* siger: at industri vil fortsætte med at føre. Det siger kun, at rotationen indtil nu har været cyklisk. Momentumforskningen giver en svag statistisk fordel til, at det fortsætter nogle måneder; cyklusmodellen siger intet sikkert om hvornår, det vender.

## Faldgruber og begrænsninger

- **Cyklusskemaet er et gennemsnit.** I 2020 varede recessionen to måneder; i 2022 faldt både aktier og obligationer uden recession. Mange "regler" holder kun i nogle cyklusser.
- **Sektorer ændrer sig.** Klassifikationerne ændres (fx flyttede GICS i 2018 Alphabet og Meta til kommunikation), og sektorer får nye karakteristika. Teknologi er i dag også en kvalitetsfaktor og ikke kun cyklisk.
- **Temaer er koncentrerede.** En tema-ETF kan have 30–40 % i fem aktier. Et tema er ofte en skjult enkeltaktiesatsning.
- **Faktor-ETF'er er tilnærmelser.** MTUM, VLUE, QUAL og USMV er long-only og meget korrelerede med markedet. De viser faktorens retning, ikke dens rene afkast.
- **Overlap mellem grupper.** Halvledere (tema), teknologi (sektor), Taiwan (land) og vækst (faktor) er langt hen ad vejen den samme satsning. Fire stærke rækker er ikke fire uafhængige signaler.
- **UCITS-tvillingen er ikke signalfonden.** Signalet gælder den amerikanske fond; afkastet, du får, kommer fra tvillingen.
- **Rotation er relativ.** Den stærkeste sektor kan falde. Se [Risk-on og risk-off](laerebog/risk-on-risk-off).

## Videre læsning

- Stovall, S. (1996): *Standard & Poor's Guide to Sector Investing*, McGraw-Hill.
- Fidelity Investments: "The Business Cycle Approach to Equity Sector Investing" (whitepaper, Fidelity Institutional).
- Stangl, J., Jacobsen, B. og Visaltanachoti, N. (2009): "Sector Rotation over Business Cycles", arbejdspapir, Massey University.
- Moskowitz, T. J. og Grinblatt, M. (1999): "Do Industries Explain Momentum?", *Journal of Finance* 54(4).
- Fama, E. F. og French, K. R. (1993): "Common Risk Factors in the Returns on Stocks and Bonds", *Journal of Financial Economics* 33(1).
- Asness, C. S., Moskowitz, T. J. og Pedersen, L. H. (2013): "Value and Momentum Everywhere", *Journal of Finance* 68(3).
- Asness, C. S., Frazzini, A. og Pedersen, L. H. (2019): "Quality Minus Junk", *Review of Accounting Studies* 24(1).
- Frazzini, A. og Pedersen, L. H. (2014): "Betting Against Beta", *Journal of Financial Economics* 111(1).
