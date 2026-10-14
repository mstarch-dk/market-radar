# Ledende indikatorer og indtjeningsrevisioner

## Intuition

Økonomiske nøgletal som BNP og beskæftigelse kommer sent. BNP for et kvartal offentliggøres en måned eller mere efter kvartalets udgang og revideres i årevis bagefter. Arbejdsløsheden stiger typisk først, når recessionen er i gang. Til at forstå, hvor økonomien er på vej hen, har du brug for tal, der bevæger sig *før* økonomien: ledende indikatorer. Det kan være ordreindgang, erhvervstillid, byggetilladelser, rentespænd og aktiekurser. Hver for sig er de støjfyldte, men samlet giver de et tidligt billede af konjunkturen.

For aktier er der en endnu mere direkte størrelse: indtjeningen. Aktiekurser følger på lang sigt indtjeningen, og på kort sigt følger de *forventningerne* til indtjeningen. Når analytikerne løfter deres estimater, er det typisk et medvind for aktierne; når de skærer, en modvind. Ændringen i forventningerne, revisionerne, er derfor en af de mest direkte indikatorer for aktiemarkedets fundament.

Dette kapitel handler om de to: OECD's sammensatte ledende indikatorer for økonomien, og FactSets opgørelse af revisionerne i S&P 500's indtjeningsestimater.

## Teori

### OECD's sammensatte ledende indikatorer

OECD beregner hver måned en Composite Leading Indicator (CLI) for en række lande og regioner. Den er designet til at forudse vendepunkter i konjunkturcyklussen 6–9 måneder frem. Hvert lands CLI er sammensat af en håndfuld komponenter, valgt fordi de historisk har vendt før den økonomiske aktivitet. Typiske komponenter er:

- erhvervstillid og ordreforventninger i industrien,
- forbrugertillid,
- byggetilladelser og boligmarkedet,
- rentespænd og aktiekurser,
- ordrer og lagre.

Komponenterne renses for sæsonudsving og langsigtet trend og glattes. Derefter *amplitudejusteres* de, så de svinger med samme størrelse, og lægges sammen. Resultatet er en indeksserie, hvor **100 er den langsigtede trend**: en CLI på 101 betyder, at aktiviteten ventes at ligge over sin trend (en positiv outputgab-cyklus), en CLI på 99 under.

Det vigtige er både *niveauet* (over eller under 100) og *retningen* (stigende eller faldende). Det giver fire faser:

| Niveau | Retning | Fase | Tolkning |
|---|---|---|---|
| Over 100 | Stigende | **Expansion** (ekspansion) | Vækst over trend og tiltagende |
| Over 100 | Faldende | **Slowdown** (afmatning) | Vækst over trend, men aftagende |
| Under 100 | Faldende | **Contraction** (nedgang) | Vækst under trend og aftagende |
| Under 100 | Stigende | **Recovery** (genopretning) | Vækst under trend, men tiltagende |

Faserne følger samme logik som kvadranterne i [rotationsgrafen](laerebog/rrg): niveau mod retning. Konjunkturen bevæger sig typisk rundt i rækkefølgen Expansion → Slowdown → Contraction → Recovery, men den kan krøge tilbage og springe faser over. Faserne hænger løst sammen med sektorrotation i [konjunkturcyklussen](laerebog/rotation-og-cyklus).

Aktiemarkedet er selv en ledende indikator, og det er ofte *hurtigere* end CLI. Aktier bunder typisk, mens CLI stadig falder (i Contraction), og de har ofte toppet, før CLI går i Slowdown. CLI er derfor mest nyttig som bekræftelse og som en bredere vurdering af, om et kursfald har økonomisk rygdækning.

### Offentliggørelse og forsinkelse

CLI offentliggøres månedligt med en forsinkelse: tallet for en given måned kommer typisk omkring to måneder senere. Desuden revideres de seneste måneder, når nye komponentdata kommer ind, og når trendberegningen opdateres (trendfiltre er usikre i slutningen af serien). Et signal om en vending kan altså forsvinde ved næste revision.

### Indtjeningsrevisioner

Analytikere estimerer, hvad virksomhederne vil tjene pr. aktie (EPS) i de kommende kvartaler og år. Summen for alle selskaber i S&P 500 giver et estimat for indeksets samlede indtjening og dermed for indtjeningsvæksten i forhold til samme kvartal året før.

Estimaterne ændrer sig løbende. Mønstret er velkendt:

1. **Før og i løbet af kvartalet** sænker analytikerne typisk deres estimater gradvist. Virksomhederne guider forsigtigt, og analytikerne følger med.
2. **I regnskabssæsonen** slår typisk omkring tre fjerdedele af selskaberne de (nu lavere) estimater, og den faktiske vækst ender over estimatet ved kvartalets start eller slutning.

Det betyder, at en *nedjustering* i løbet af kvartalet er normalen, og at det er afvigelsen fra det mønster, der er informativ. Et kvartal, hvor estimaterne stiger i stedet for at falde, er et stærkt tegn. Chan, Jegadeesh og Lakonishok (1996) dokumenterede, at aktier med opjusterede estimater klarer sig bedre end aktier med nedjusterede i månederne efter: indtjeningsmomentum, beslægtet med prismomentum.

FactSet udgiver hver uge rapporten *Earnings Insight*, der opgør S&P 500's forventede indtjeningsvækst, hvordan den har ændret sig, antallet af selskaber med positiv og negativ guidance, og indeksets forward P/E (kurs divideret med de forventede indtjeninger de næste 12 måneder) sammenlignet med gennemsnittet over 5 og 10 år. Revisionerne for enkeltaktier og regioner behandles i [Estimatrevisioner](laerebog/estimatrevisioner), og forward P/E i [P/E og indtjening pr. aktie](laerebog/pe-og-eps).

### Guidance

Guidance er virksomhedernes egne udmeldinger om den forventede indtjening. Fordi virksomheder har en tilskyndelse til at sætte barren lavt, er negativ guidance mere almindelig end positiv. FactSet rapporterer antallet af selskaber i S&P 500 med negativ og positiv EPS-guidance for det kommende kvartal; forholdet mellem dem sammenlignes typisk med det historiske gennemsnit.

## Sådan gør radaren

### OECD CLI

Radaren henter de amplitudejusterede CLI-serier fra OECD's SDMX-API (`update_oecd_cli` i `src/radar/external.py`) for de områder, der står under `external.oecd_cli` i `config/universe.yaml`: G20, USA, *Europe big 4* (Tyskland, Frankrig, Italien og Storbritannien; OECD udgiver ikke længere CLI for euroområdet eller Danmark) og Kina.

Funktionen `cli_table` beregner for hvert område:

- seneste værdi,
- ændringen over 3 måneder: seneste værdi minus værdien 3 måneder tidligere (`chg_3m`),
- fasen: *over 100* betyder mindst 100; *stigende* betyder `chg_3m` strengt over 0. Er ændringen præcis 0, tæller den som faldende.

**Kun G20 stemmer** (det første område i listen). Expansion stemmer **risk-on**, Contraction stemmer **risk-off**, Slowdown og Recovery er **neutral**. De øvrige områders faser står i rækkens note.

Rækken har kilden "oecd" og bliver *stale*, hvis den seneste måned er mere end {{settings:coverage.max_age.oecd}} dage ældre end rapportens dato (en månedlig observation dateres til den 1. i måneden). Grænsen er rummelig på grund af offentliggørelsesforsinkelsen.

CLI-tabellen for alle områder og en graf over de seneste år står på [Positionering](/positioning) under *Leading indicators (OECD CLI)*.

### FactSet Earnings Insight

Radaren henter den seneste *Earnings Insight*-PDF og læser teksten (`parse_factset`). Til afstemningen bruges to tal:

- den aktuelle forventede vækst for kvartalet i fokus ("growth now"),
- den forventede vækst for samme kvartal på den referencedato, FactSet angiver, typisk kvartalets start ("growth start").

Revisionen er forskellen i procentpoint:

$$
\text{rev} = g_{\text{nu}} - g_{\text{start}}
$$

- **risk-on**, hvis rev er over {{settings:regime.revisions_band}} procentpoint (`regime.revisions_band`),
- **risk-off**, hvis den er under −{{settings:regime.revisions_band}},
- **neutral** ellers.

Kan rapportens vækstsætninger ikke læses, bliver rækken *n/a* med en note om det; radaren gætter ikke. Rækken har kilden "factset" og bliver *stale* efter {{settings:coverage.max_age.factset}} dage.

Noten viser også antallet af selskaber med positiv og negativ guidance. Forward P/E med 5- og 10-årsgennemsnit, guidance og historikken vises på [Positionering](/positioning) under *Earnings revisions (S&P 500, FactSet)*; de stemmer ikke.

## Regneeksempel

**OECD CLI for G20.** Rapportens dato er 14. oktober. På grund af forsinkelsen er august den seneste måned. De seneste fire måneder (maj til august):

| Måned | CLI |
|---|---|
| Maj | 100,12 |
| Juni | 100,20 |
| Juli | 100,25 |
| August | 100,31 |

`chg_3m` = 100,31 − 100,12 = +0,19 (august minus maj, tre måneder tidligere). Niveauet er over 100, og ændringen er positiv → **Expansion** → **risk-on**.

Antag, at USA samtidig står på 99,80 og for tre måneder siden stod på 99,95. Ændringen er −0,15, niveauet er under 100 → Contraction. Det står i noten ("United States contraction"), men stemmer ikke, fordi kun G20 stemmer.

Friskhed: augusttallet er dateret 1. august, 74 dage før rapportens dato. Med en grænse på 75 dage (din opsætning: {{settings:coverage.max_age.oecd}}) tæller rækken lige akkurat. Kommer septembertallet ikke inden 16. oktober, bliver rækken *stale* og holder op med at stemme, indtil nye data er hentet.

**FactSet.** Rapporten siger, at den forventede vækst for Q3 er 8,1 %, og at den 30. juni var 7,3 %:

$$
\text{rev} = 8.1 - 7.3 = 0.8
$$

Med et bånd på 0,5 procentpoint (din opsætning: {{settings:regime.revisions_band}}) → **risk-on**. Analytikerne har løftet forventningerne gennem kvartalet i stedet for at sænke dem, som er normalen.

Antag i stedet 6,6 % nu mod 7,3 % ved kvartalets start: rev = −0,7 → **risk-off**. Men husk mønstret fra teorien: en mindre nedjustering i løbet af kvartalet er normal, så −0,7 er kun moderat svagt i historisk perspektiv.

## Faldgruber og begrænsninger

- **CLI kommer sent og revideres.** Et tal for september, offentliggjort i november, beskriver økonomien, som den så ud for to måneder siden, og kan blive ændret næste måned. Aktiemarkedet har ofte allerede reageret.
- **Kun G20 stemmer.** Det globale aggregat kan maskere store regionale forskelle. Er Europa i Contraction, mens G20 er i Expansion, stemmer rækken risk-on.
- **Ingen dansk eller euro-CLI.** OECD udgiver dem ikke længere; *Europe big 4* er den nærmeste erstatning og omfatter Storbritannien, men ikke de mindre eurolande.
- **Små ændringer, tærskelfølsomhed.** Fasen skifter, når ændringen krydser 0, også hvis den kun er ±0,01. Gaugen på [Positionering](/positioning) viser, hvor tæt ændringen er på 0.
- **Revisionsmønstret er sæsonbestemt.** Under regnskabssæsonen blander FactSets "growth now" faktiske resultater (der typisk slår estimaterne) med estimater for dem, der endnu ikke har rapporteret. Revisionen har derfor en tendens til at stige i regnskabssæsonen og falde mellem sæsonerne. Det er samme tal, men det betyder noget forskelligt på forskellige tidspunkter i kvartalet.
- **Kvartalsskift.** Når FactSet skifter fokus til næste kvartal, starter sammenligningen forfra.
- **Kun S&P 500.** FactSet-rækken siger intet direkte om Europa eller Norden. Revisioner uden for USA ses kun gennem Yahoo-konsensus (se [Estimatrevisioner](laerebog/estimatrevisioner)), som ikke stemmer.
- **PDF-læsning.** Tallene læses fra rapportens tekst med faste sætningsmønstre. Ændrer FactSet formuleringen, bliver rækken *n/a* i stedet for at vise et forkert tal.

## Videre læsning

- OECD (2012): "OECD System of Composite Leading Indicators", OECD Statistics Directorate, metodedokument (Gyomai, G. og Guidetti, E.).
- OECD: Composite Leading Indicators, https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html
- FactSet: *Earnings Insight* (ugentlig, J. Butters), https://insight.factset.com
- Chan, L. K. C., Jegadeesh, N. og Lakonishok, J. (1996): "Momentum Strategies", *Journal of Finance* 51(5).
- Stock, J. H. og Watson, M. W. (1989): "New Indexes of Coincident and Leading Economic Indicators", *NBER Macroeconomics Annual* 4.
