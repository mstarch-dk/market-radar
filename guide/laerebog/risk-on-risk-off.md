# Risk-on og risk-off

## Intuition

Nogle perioder vil investorerne have risiko. Aktier stiger bredt, små og cykliske selskaber fører, kreditspændene snævrer ind, volatiliteten er lav, og råvarer som kobber stiger. Andre perioder flygter de fra risiko: aktier falder, statsobligationer, guld og dollaren efterspørges, kreditspændene udvides, og volatiliteten springer op. Markedsfolk kalder de to tilstande **risk-on** og **risk-off**.

Det interessante er ikke, at markedet nogle gange stiger og nogle gange falder. Det er, at *mange forskellige markeder bevæger sig sammen* i den samme retning, fordi de deles om den samme drivkraft: investorernes samlede appetit på risiko. Det gør det muligt at aflæse stemningen fra mange vinkler på én gang.

For en investor med en horisont på 1–6 måneder er regimet konteksten for alt andet. Momentum virker bedst i rolige, trendende markeder og kan lide store tab omkring vendepunkter. En stærk sektor betyder noget andet, når hele markedet er i risk-off. Og en stop-loss-regel bør måske være strammere, når regimet forværres. Regimet er ikke et købs- eller salgssignal; det er vejrudsigten, som de andre beslutninger tages i.

## Teori

### Hvad er et regime?

I statistikken er et regime en periode, hvor en tidsserie opfører sig efter ét sæt regler (fx ét gennemsnit og én volatilitet), indtil den skifter til et andet. Hamilton (1989) formaliserede ideen med Markov-skiftemodeller: der findes en skjult tilstand $s_t$ (fx "rolig" eller "urolig"), og afkastet trækkes fra en fordeling, der afhænger af tilstanden:

$$
r_t \mid s_t = k \sim N(\mu_k, \sigma_k^2), \qquad P(s_t = j \mid s_{t-1} = i) = p_{ij}
$$

Empirisk finder man i aktiemarkeder typisk to regimer: et med positivt gennemsnitsafkast og lav volatilitet, og et med lavt eller negativt afkast, høj volatilitet og høj korrelation mellem aktiver (Ang og Timmermann, 2012). Det sidste er det, investorer oplever som risk-off: diversifikationen svigter, netop når den skal bruges. Se [Diversifikation og korrelation](laerebog/diversifikation).

### Risikovilje

Bag regimet ligger *risikovilje*: hvor meget kompensation investorerne kræver for at bære risiko. Når risikovilligheden er høj, accepterer de lave risikopræmier, og prisen på risikable aktiver stiger. Når den falder, kræver de højere præmier, og prisen falder, ofte hurtigt. Risikovilligheden svinger med bl.a. formue (efter store tab har man mindre at miste), gearing og finansieringsforhold, usikkerhed om økonomien og ren stemning.

Den samme risikovilje påvirker mange markeder, og derfor kan den aflæses fra mange vinkler.

### Signaler på tværs af aktivklasser

| Marked | Risk-on | Risk-off | Kapitel |
|---|---|---|---|
| Aktiernes trend | Over 200-dages gennemsnit | Under | [Glidende gennemsnit og trend](laerebog/trend) |
| Markedsbredde | Mange aktier stiger | Få aktier bærer indekset | [Markedsbredde](laerebog/markedsbredde) |
| Optionsmarkedet | Lav VIX, normal terminsstruktur | Høj VIX, inverteret struktur | [VIX](laerebog/vix) |
| Kreditmarkedet | Snævre kreditspænd | Udvidede kreditspænd | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| Renter | Normal rentekurve, rolige renter | Inverteret kurve, renteshock | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| Valuta | Svagere dollar | Stærk dollar | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| Råvarer | Kobber slår guld | Guld slår kobber, olieshock | [Kobber, guld og olie](laerebog/raavarer) |
| Makro | Ledende indikatorer stiger | Ledende indikatorer falder | [Ledende indikatorer](laerebog/ledende-indikatorer) |
| Indtjening | Estimater opjusteres | Estimater nedjusteres | [Ledende indikatorer](laerebog/ledende-indikatorer) |

Hver indikator har sin egen styrke. Kreditmarkedet er ofte tidligt ude, fordi obligationsinvestorer fokuserer på konkursrisiko. Optionsmarkedet reagerer hurtigt, men også på kortvarig nervøsitet. Ledende indikatorer er langsomme, men brede. Markedsbredde afslører, om en stigning er sund eller båret af få aktier.

### Hvorfor kombinere mange indikatorer?

Hver enkelt indikator giver fejlsignaler. VIX springer op på en dårlig uge og falder igen. Rentekurven var inverteret i over to år fra 2022, uden at der kom en amerikansk recession i den periode. Kobber kan stige på grund af en mine, der lukker.

Ideen med at kombinere er den samme som ved et panel af dommere: hvis hver dommer har ret lidt oftere end tilfældigt, og deres fejl er *uafhængige*, har flertallet ret langt oftere end den enkelte. Regneeksemplet nedenfor viser det. Men gevinsten afhænger helt af uafhængigheden. Indikatorer, der måler det samme (fire forskellige mål for aktiemarkedets trend), giver ikke fire stemmer værd af information, men måske én.

Et andet argument er robusthed. En simpel, lige vægtning af mange indikatorer er ofte lige så god som en optimeret model uden for den periode, den blev optimeret på, fordi optimeringen tilpasser sig støj. Dawes (1979) viste det generelt for beslutningsmodeller: "uforbedrede" modeller med lige vægte slår ofte menneskelig vurdering og holder sig tæt på optimerede modeller.

### Regimer varer ved

Regimer er *persistente*: et rolig marked er oftest roligt i morgen også, og en krise går sjældent over på en uge. I Markov-modellen ses det som en høj sandsynlighed $p_{ii}$ for at blive i samme tilstand. Den forventede varighed af et regime er

$$
E[\text{varighed}] = \frac{1}{1 - p_{ii}}
$$

perioder. Volatilitet er særlig persistent (volatilitetsklynger), hvilket er grunden til, at et regime med høj volatilitet sjældent forsvinder fra den ene dag til den anden.

Persistensen er det, der gør regimet brugbart: hvis tilstanden i dag siger noget om tilstanden om en måned, kan du indrette dig efter den. Men den gør også, at regimet er bedst til at beskrive *hvor vi er*, ikke til at forudsige vendepunkter. Overgangene er pludselige og ses først efter nogle dage eller uger.

Kritzman, Page og Turkington (2012) viste, at selv simple regimeskift-modeller på tværs af turbulens, inflation og vækst kunne have forbedret en porteføljes risikojusterede afkast historisk, men også at modellerne er følsomme over for, hvilke data de er estimeret på.

## Sådan gør radaren

Radaren estimerer ikke en Markov-model. Den bruger en gennemsigtig **afstemning**: en række indikatorer, der hver især med faste regler stemmer risk-on, risk-off eller neutral. Nettostemmen giver en etiket: *Risk-on*, *Risk-off* eller blandet (*Mixed*). Hele modellen er beskrevet i [Radarens afstemningsmodel](laerebog/afstemningsmodellen), og hver indikators teori står i kapitlerne i tabellen ovenfor.

Én række hører ikke til nogen af de andre kapitler, så den beskrives her: **Global trend (ACWI)**. Den sammenligner ACWI's seneste lukkekurs med gennemsnittet af de seneste 200 og 50 lukkekurser:

- **risk-on**, hvis kursen er over 200-dages gennemsnittet *og* 50-dages gennemsnittet er over 200-dages.
- **risk-off**, hvis kursen er under 200-dages gennemsnittet *og* 50-dages er under 200-dages.
- **neutral** ellers (blandet trend).

Reglen ligger fast i koden (`src/radar/signals/regime.py`). Se [Glidende gennemsnit og trend](laerebog/trend) for baggrunden.

Du finder regimet på [Regime](/regime): den samlede etiket, alle indikatorrækker med deres stemme, og grafer for trend, markedsbredde, kreditspænd, VIX m.fl. Se [brugervejledningen til regimet](brugervejledning/regime).

## Regneeksempel

**Flertallets visdom, med og uden uafhængighed.** Antag fem indikatorer, der hver især peger rigtigt 60 % af tiden, og som fejler uafhængigt af hinanden. Flertallet (mindst 3 af 5) har ret med sandsynligheden

$$
P(\geq 3) = \binom{5}{3} 0.6^3\, 0.4^2 + \binom{5}{4} 0.6^4\, 0.4 + 0.6^5
$$

Leddene: 10 · 0,216 · 0,16 = 0,3456; 5 · 0,1296 · 0,4 = 0,2592; 0,6⁵ = 0,0778. I alt **0,683**. Fem middelmådige indikatorer giver et flertal, der har ret 68 % af tiden i stedet for 60 %.

Antag nu i stedet, at tre af de fem er så tæt korrelerede, at de altid stemmer ens (fx tre mål for aktiemarkedets bredde). Så er der reelt tre uafhængige stemmer: en "blok" med vægt 3 og to enkeltindikatorer. Blokken alene afgør flertallet, så flertallet har ret, præcis når blokken har ret: **60 %**. Gevinsten ved at kombinere er forsvundet. Det er derfor, det betyder noget, hvor mange rækker der måler det samme (se [faldgruberne i afstemningsmodellen](laerebog/afstemningsmodellen#faldgruber-og-begrænsninger)).

**Persistens.** Antag, at et risk-on-regime på ugebasis fortsætter med sandsynligheden 0,95. Den forventede varighed er 1 / (1 − 0,95) = 20 uger, knap fem måneder. Sandsynligheden for, at regimet stadig består om 13 uger (et kvartal), er 0,95¹³ ≈ 0,513. Selv et meget persistent regime har altså kun omkring halvt chance for at holde et kvartal frem. Regimet er en god beskrivelse af nu, og en svag forudsigelse af om tre måneder.

## Faldgruber og begrænsninger

- **Regimet beskriver, det forudsiger ikke.** Det skifter efter markedet, ikke før. Ved et pludseligt chok (fx marts 2020) går mange indikatorer i risk-off samtidig, efter de første store fald.
- **Falske skift.** En kort korrektion kan vippe flere indikatorer, som så vender tilbage. At handle på hvert skift giver mange handler og meget støj.
- **Korrelation mellem indikatorerne.** I en krise bevæger alt sig sammen, og mange indikatorer siger det samme. Det ligner stærk enighed, men er måske ét signal talt mange gange.
- **USA-tung.** De fleste tilgængelige makro- og markedsdata er amerikanske. Et regime, der primært er drevet af USA, behøver ikke passe på Europa eller Norden.
- **Risk-off er ikke "sælg alt".** Historisk har nogle af de bedste enkeltdage ligget midt i risk-off-perioder. Regimet er kontekst for størrelser, stop og forventninger, ikke en ind/ud-knap.
- **Regimer ændrer karakter.** Korrelationen mellem aktier og obligationer var negativ i det meste af 2000–2020 og positiv i 2022. Det, der var risk-off-tegn i ét årti, er ikke nødvendigvis det i det næste.

## Videre læsning

- Hamilton, J. D. (1989): "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle", *Econometrica* 57(2).
- Ang, A. og Timmermann, A. (2012): "Regime Changes and Financial Markets", *Annual Review of Financial Economics* 4.
- Kritzman, M., Page, S. og Turkington, D. (2012): "Regime Shifts: Implications for Dynamic Strategies", *Financial Analysts Journal* 68(3).
- Dawes, R. M. (1979): "The Robust Beauty of Improper Linear Models in Decision Making", *American Psychologist* 34(7).
