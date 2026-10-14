# P/E og indtjening pr. aktie

## Intuition

En aktie er en andel af en virksomheds fremtidige overskud. Når du betaler 200 kr. for en aktie i et selskab, der tjener 10 kr. pr. aktie om året, betaler du 20 års nuværende indtjening. Det tal, 20, er price/earnings-forholdet, P/E. Det er det mest brugte nøgletal for, hvor "dyr" en aktie er, fordi det sætter prisen i forhold til det, du faktisk køber: en andel af indtjeningen.

P/E siger ikke i sig selv, om en aktie er billig eller dyr. Et selskab, der vokser hurtigt, kan sagtens være rimeligt prissat til 35 gange indtjeningen, og et selskab i tilbagegang kan være dyrt til 8. P/E er et udgangspunkt for spørgsmålet *hvad skal der til for, at prisen giver mening?*, ikke et svar.

Det næste spørgsmål er: *hvilken* indtjening? Sidste års faktiske tal, analytikernes skøn for i år eller deres skøn for næste år? De giver forskellige P/E-tal for den samme aktie på den samme dag, og forskellen er ofte større end forskellen mellem to aktier. Dette kapitel gennemgår baserne, de beslægtede nøgletal og de regnskabs- og datafælder, der gør, at radaren hellere viser et tomt felt end et forkert tal.

## Teori

### Indtjening pr. aktie

Indtjening pr. aktie (earnings per share, EPS) er nettoresultatet til aktionærerne divideret med antallet af aktier:

$$
\text{EPS} = \frac{\text{nettoresultat} - \text{præferenceudbytte}}{\text{gennemsnitligt antal udestående aktier}}
$$

Regnskaberne viser både *basic* EPS og *udvandet* (diluted) EPS, hvor optioner, warrants og konvertible lån regnes, som om de var udnyttet. Analytikere og dataleverandører bruger normalt udvandet EPS, og ofte en "justeret" udgave, hvor engangsposter (nedskrivninger, omstruktureringer, gevinster ved frasalg) er renset ud. Den justerede indtjening er ikke en regnskabsstandard; hvert selskab og hver analytiker definerer den lidt forskelligt.

### Fire slags EPS

| Base | Hvad det er | Styrke | Svaghed |
|---|---|---|---|
| Trailing (TTM) | Summen af de seneste fire rapporterede kvartaler | Faktiske tal, revideret | Ser bagud; påvirket af engangsposter |
| Indeværende regnskabsår | Konsensus for det år, selskabet er i gang med | Delvis kendt allerede | Blander realiseret og forventet |
| Næste regnskabsår (forward, FY1) | Konsensus for det følgende regnskabsår | Det, markedet prissætter | Et skøn, der ændrer sig |
| Forward 12 måneder | Tidsvægtet blanding af indeværende og næste år | Glat over årsskiftet | Kræver begge skøn og datoer |

*Konsensus* er gennemsnittet (eller medianen) af de analytikere, der dækker selskabet. Med få analytikere er konsensus skrøbelig: én ændring flytter tallet meget.

Hvad der kaldes "forward P/E", varierer mellem kilder. Yahoo bruger næste regnskabsår, FactSet bruger de næste 12 måneder. Sammenlign derfor aldrig to forward P/E-tal fra forskellige kilder uden at tjekke basen.

### P/E og earnings yield

$$
\text{P/E} = \frac{P}{\text{EPS}}, \qquad \text{earnings yield} = \frac{\text{EPS}}{P} = \frac{1}{\text{P/E}}
$$

Earnings yield (indtjeningsafkast) er den omvendte størrelse og kan sammenlignes direkte med en rente. En P/E på 20 svarer til en earnings yield på 5 %. Den omvendte form har en praktisk fordel: den er kontinuert omkring nul. Et selskab, der går fra lille overskud til lille underskud, får en P/E, der springer fra $+\infty$ til $-\infty$, mens earnings yield blot glider fra lidt over til lidt under 0.

Sammenhængen med det forventede afkast kommer fra Gordons vækstmodel. Hvis selskabet udbetaler andelen $b$ af indtjeningen, og udbyttet vokser med $g$ om året, er prisen $P = \frac{b \cdot \text{EPS}_1}{r - g}$, hvor $r$ er det afkast, investorerne kræver. Omskrevet:

$$
\frac{P}{\text{EPS}_1} = \frac{b}{r - g}
$$

En høj P/E betyder altså enten høj forventet vækst $g$, lav krævet afkast $r$ (lav risiko eller lave renter) eller begge. Det er derfor, en lav P/E ikke er en gratis frokost: den kan afspejle lav vækst eller høj risiko.

### Evidens

Basu (1977) viste, at amerikanske aktier med lav P/E gav højere risikojusteret afkast end aktier med høj P/E. Fama og French (1992) fandt, at book-to-market fangede meget af den samme effekt; værdipræmien er siden fundet i mange lande og aktivklasser (Asness, Moskowitz og Pedersen, 2013). Præmien er dog svingende: værdiaktier klarede sig markant dårligere end vækstaktier i det meste af 2010'erne. Og den er et langsigtet fænomen. Over 1–6 måneder, radarens horisont, er værdiansættelse en baggrundsvariabel, ikke et timingsignal.

### Kurs/indre værdi

**Kurs/indre værdi** (price-to-book, P/B) sammenligner prisen med den bogførte egenkapital pr. aktie:

$$
\text{P/B} = \frac{P}{\text{egenkapital pr. aktie}}
$$

P/B er mest meningsfuld for selskaber, hvis aktiver er finansielle og bogført tæt på markedsværdi: banker, forsikring, ejendomsselskaber. For software- og medicinalselskaber, hvis værdi ligger i immaterielle aktiver, der ikke står i balancen, siger P/B meget lidt. Aktietilbagekøb trækker egenkapitalen ned og kan give en meget høj eller endda negativ P/B uden at sige noget om værdien.

### Udbytteafkast

$$
\text{udbytteafkast} = \frac{\text{udbytte pr. aktie de seneste 12 måneder}}{P}
$$

Udbytteafkastet er den del af afkastet, der kommer kontant. Et usædvanligt højt udbytteafkast er ofte et faresignal: kursen er faldet, fordi markedet venter, at udbyttet bliver skåret. Udbytte er heller ikke hele billedet, fordi mange selskaber (især amerikanske) udlodder via tilbagekøb.

### Negativ indtjening og regnskabsfælder

- **Negativ eller nul EPS** giver ingen meningsfuld P/E. Et negativt P/E-tal er ikke "billigt"; det er udefineret. Brug i stedet earnings yield, pris/salg eller pris/cash flow, eller vent på overskud.
- **Små positive tal**: et selskab, der lige er kommet ud af underskud, kan have en P/E på 400. Tallet er korrekt, men ikke informativt.
- **Engangsposter**: en stor nedskrivning gør trailing EPS lav og P/E høj; en avance ved frasalg gør det modsatte.
- **Cykliske selskaber** har ofte lav P/E på toppen af cyklussen (rekordindtjening, som markedet ikke tror varer) og høj P/E i bunden. Her vildleder P/E systematisk.
- **Regnskabsstandarder**: IFRS og US GAAP behandler fx leasing, udviklingsomkostninger og goodwill forskelligt, så samme økonomi kan give forskellig EPS.

### Regnskabsåret ruller

Konsensus er knyttet til regnskabsår, ikke til kalenderen. Når et selskab har aflagt årsregnskab, rykker dataleverandøren basen: "indeværende år" bliver det nye år, og "næste år" bliver året efter. På den dag falder forward P/E typisk i ét hug, fordi nævneren nu er et år længere ude i fremtiden og som regel højere. Intet er sket med selskabet. Den samme overgang gør, at to snapshots af "næste års EPS" taget før og efter skiftet handler om to forskellige år; se [Estimatrevisioner](laerebog/estimatrevisioner).

### Valuta: når et selskab handler i én valuta og rapporterer i en anden

Shell handles i London i pence (GBp), men rapporterer i amerikanske dollar. Vestas handles i danske kroner, men rapporterer i euro. En P/E kræver, at pris og indtjening er i samme valuta. Hvis du dividerer en pris i pence med en EPS i dollar, får du et tal, der er forkert med både en faktor 100 og en valutakurs. Det kan stadig se plausibelt ud, og netop derfor er det farligt.

## Sådan gør radaren

### Snapshot hver uge

Radaren tager et ugentligt snapshot af P/E og EPS-skøn for aktier (`valuation.py`). Et nyt snapshot tages, når det seneste er mindst {{settings:valuation.snapshot_days}} dage gammelt, og der gemmes ét pr. ISO-uge: kører du opdateringen igen i samme uge, erstatter det nye snapshot det gamle. Historikken bygger sig op uge for uge; radaren har ingen ældre data end sit eget første snapshot.

Kilden er Yahoos screener, børs for børs: Discovers markeder plus en liste af amerikanske børser. Hver børs skal returnere et minimum af navne; gør én af dem ikke det, fejler trinnet, og det seneste snapshot bliver stående. Aktier, som radaren følger (regionernes lister, dine beholdninger og din watchlist), men som screeneren ikke fanger, slås op én for én, højst {{settings:valuation.fallback_max}} pr. kørsel. Det gælder især asiatiske navne.

For hver aktie gemmes kurs, de tre EPS-tal (`eps_ttm`, `eps_cy`, `eps_fy1`), tre P/E-tal, P/B, udbytteafkast og næste regnskabsdato, plus en note, når noget er sorteret fra.

### De tre P/E-tal

| Felt | Kolonne i appen | Beregning |
|---|---|---|
| `pe_fy1` | *P/E next yr* | kurs i handelsvaluta / EPS næste regnskabsår |
| `pe_cy` | *P/E this yr* | kurs omregnet til rapporteringsvaluta / EPS indeværende år |
| `pe_ttm` | *P/E ttm* | kurs i handelsvaluta / trailing 12 mdr. EPS |

*P/E next yr* er den, der vises som standard i tabellerne på [Momentum](/momentum), [Discover](/discover) og [My holdings & watchlist](/me); de to andre kan slås til. Tallet farves efter, hvordan det ligger i forhold til sektoren, se [Relativ værdiansættelse](laerebog/relativ-vaerdiansaettelse).

Hvorfor to forskellige priser? Yahoo blander valutaer inden for ét og samme kursopslag, når selskabet rapporterer i en anden valuta, end det handles i: trailing EPS og næste års EPS kommer omregnet til handelsvalutaen (i pund for en pence-notering), men indeværende års EPS kommer i rapporteringsvalutaen. Radaren dividerer derfor hver EPS med en kurs i *dens egen* valuta:

- For `pe_ttm` og `pe_fy1` bruges kursen i handelsvalutaens hovedenhed (pence divideres med 100). Det giver det samme som Yahoos egne trailing og forward P/E.
- For `pe_cy` omregnes kursen til rapporteringsvalutaen med de seneste valutakurser. Yahoos eget felt for denne års P/E er forkert for de navne og bruges ikke. Mangler en kurs (Yahoo har fx ingen CNY/DKK-notering), bliver `pe_cy` tomt, aldrig et blandet forhold.

Afviger radarens `pe_fy1` mere end 5 % fra Yahoos eget forward P/E-felt, skrives Yahoos tal i noten, så du kan se forskellen.

### Hvad der sorteres fra

Et tal, der ikke kan være rigtigt, vises ikke. Hver frasortering skrives i snapshottets note:

- **EPS ≤ 0**: ingen P/E for den base (negativ eller nul indtjening).
- **P/E uden for [{{settings:valuation.pe_range}}]**: tallet udelades. Et P/E på 0,4 eller 900 er næsten altid en enheds- eller valutafejl, ikke en værdiansættelse.
- **Denne års P/E mod næste års**: ligger forholdet $\text{pe\_cy}/\text{pe\_fy1}$ uden for $[\tfrac{1}{3}, 3]$, udelades `pe_cy` som inkonsistent. Grænsen står fast i koden.
- **Kun ved opslag én for én**: er næste års EPS mere end 3 gange eller under en tredjedel af trailing EPS, udelades `pe_fy1`. Yahoos enkeltopslag blander for nogle markeder (Japan) baser; screenerens data gør ikke, og her kan et stort spring fra lav trailing indtjening være ægte. Grænsen står fast i koden.
- **P/B** beregnes som kursen i rapporteringsvaluta divideret med egenkapital pr. aktie (som Yahoo oplyser i rapporteringsvalutaen) og beholdes kun inden for $[0.05, 100]$. Negativ egenkapital giver ingen P/B. Grænserne står i koden.
- **Udbytteafkast** tages fra Yahoos trailing-felt (en brøk) og beholdes kun mellem 0 og 25 % (fast i koden).

Felterne ses også i [tickerprofilen](brugervejledning/tickerprofil) med P/E-historikken fra de gemte snapshots.

## Regneeksempel

> **Eksempel:** Et selskab som Shell, noteret i London i pence og med regnskab i dollar. Tallene er opfundne.

Yahoo oplyser:

- Kurs: 2.700 GBp
- Trailing EPS (omregnet til pund): 2,40 GBP
- Næste års EPS (omregnet til pund): 2,70 GBP
- Indeværende års EPS (i dollar): 3,30 USD
- Egenkapital pr. aktie (i dollar): 22,50 USD
- Valutakurser: 1 GBP = 8,60 DKK, 1 USD = 6,45 DKK

**Trin 1: kurs i handelsvalutaens hovedenhed.** $2700 / 100 = 27.00$ GBP.

**Trin 2: trailing og næste års P/E** (begge i pund):

$$
\text{pe\_ttm} = \frac{27.00}{2.40} = 11.25, \qquad \text{pe\_fy1} = \frac{27.00}{2.70} = 10.0
$$

**Trin 3: kurs i rapporteringsvaluta.** Pence → pund → dollar via kroner:

$$
P_{\text{USD}} = 2700 \cdot 0.01 \cdot \frac{8.60}{6.45} = 27.00 \cdot 1.3333 = 36.00
$$

**Trin 4: indeværende års P/E** (begge i dollar):

$$
\text{pe\_cy} = \frac{36.00}{3.30} = 10.91
$$

Kontrol: $10.91 / 10.0 = 1.09$, inden for $[\tfrac13, 3]$, så tallet beholdes.

**Trin 5: P/B og earnings yield.**

$$
\text{P/B} = \frac{36.00}{22.50} = 1.60, \qquad \text{earnings yield (FY1)} = \frac{1}{10.0} = 10\ \%
$$

**Hvad var gået galt uden valutahåndtering?** Divideres de rå 2.700 pence med 3,30 dollar, fås 818: uden for intervallet og sorteret fra. Det er den ufarlige fejl. Divideres 27,00 pund med 3,30 dollar, fås 8,2, et tal der ser helt plausibelt ud, men er forkert med valutakursen (omkring 25 % for lavt). Det er den farlige fejl, og grunden til, at radaren regner `pe_cy` på kursen i dollar.

## Faldgruber og begrænsninger

- **Yahoo er en uofficiel kilde.** Konsensus kommer uden kvalitetsgaranti, antallet af analytikere bag tallet vises ikke i snapshottet, og definitionen af "justeret" EPS følger leverandøren.
- **Basen skifter over året.** Kort efter årsregnskabet falder *P/E next yr* mekanisk. Sammenlign derfor helst aktier, der har samme regnskabsår, eller brug ændringen i P/E med omtanke omkring januar–marts.
- **Lav P/E er ikke det samme som billig.** Cykliske selskaber på toppen, selskaber med strukturelt faldende indtjening og selskaber med høj gæld ser billige ud på P/E. P/E ser ikke gælden; EV/EBIT gør, men det modellerer radaren ikke.
- **Høj P/E er ikke det samme som dyr.** Vækst gør en høj multipel rimelig, se Gordon-formlen ovenfor.
- **Manglende tal er information.** Et tomt felt betyder underskud, et inkonsistent skøn eller ingen dækning. Noten gemmes i snapshottet (`data/valuation/stocks.parquet`); se på den, før du drager konklusioner.
- **Ugentlig opløsning.** P/E-tallet er fra snapshottets dag, ikke fra i dag. Har kursen flyttet sig 10 % siden, har P/E også.

## Videre læsning

- Sanjoy Basu: "Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios: A Test of the Efficient Market Hypothesis", *Journal of Finance* 32(3), 1977.
- Eugene F. Fama og Kenneth R. French: "The Cross-Section of Expected Stock Returns", *Journal of Finance* 47(2), 1992.
- Clifford S. Asness, Tobias J. Moskowitz og Lasse Heje Pedersen: "Value and Momentum Everywhere", *Journal of Finance* 68(3), 2013.
- Aswath Damodaran: *Investment Valuation*, 3. udgave, Wiley, 2012 (kapitlerne om multipler).
- Benjamin Graham og David Dodd: *Security Analysis*, 1934 (og senere udgaver).
