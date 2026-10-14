# Radarens momentumscore

Momentumscoren er radarens måde at sige "hvor stærk er denne aktie i forhold til sine naboer?" med ét tal fra 0 til 100. Den bygger direkte på forskningen i [Momentumeffekten](laerebog/momentumeffekten), men med nogle praktiske valg: tre horisonter i stedet for én, percentiler i stedet for rå afkast, og rangering inden for hver region. Dette kapitel gennemgår præcis, hvad koden gør, regner et eksempel igennem og forklarer, hvad du skal være opmærksom på, når du læser [Momentum](/momentum).

## Intuition

Et afkast på 30 % på seks måneder kan være enestående eller helt almindeligt, afhængigt af hvad resten af markedet har gjort. Momentumscoren ser derfor ikke på afkastet i sig selv, men på *placeringen*: hvor stor en del af de andre aktier i samme region har et lavere afkast?

Den gør det for tre horisonter:

- **12-1 måneder** (det klassiske, lange mål, uden den seneste måned),
- **6 måneder**,
- **3 måneder**,

og tager gennemsnittet. En aktie, der ligger i toppen på alle tre, får en score tæt på 100. En aktie, der kun har haft en god seneste kvartal, men et svagt år, lander i midten. Kombinationen belønner aktier, hvis styrke både er vedvarende og stadig til stede.

Rangeringen sker inden for hver region, fordi markeder bevæger sig forskelligt. Er europæiske aktier steget mindre end amerikanske, ville en fælles rangering fylde toplisten med amerikanske navne. Inden for regionen sammenlignes æbler med æbler.

## Teori

### Percentilrang i stedet for rå afkast

At kombinere afkast fra forskellige horisonter direkte er problematisk: 6-måneders afkast spreder sig mere end 3-måneders, så et simpelt gennemsnit ville give den længste horisont mest vægt. Ved først at omregne hvert afkast til en percentilrang (en værdi mellem 0 og 1) får alle tre horisonter samme skala og samme vægt. Percentiler er også robuste: en enkelt aktie, der er steget 400 %, trækker ikke resten af fordelingen.

### Hvorfor tre horisonter?

Den akademiske standard er 12-1-måneders afkast (Asness, Moskowitz og Pedersen 2013). Jegadeesh og Titman (1993) fandt dog, at strategier dannet på 3, 6, 9 og 12 måneder alle virker. Ved at tage 6 og 3 måneder med vægter radaren den nyere udvikling højere. Det passer til en horisont på 1–6 måneder, men gør scoren lidt mere følsom for kortsigtede bevægelser end det rene 12-1-mål.

Bemærk, at 3- og 6-måneders afkastene *ikke* springer den seneste måned over. Den kortsigtede vending, som 12-1-målet undgår, er altså delvist med igen i de to kortere horisonter.

## Sådan gør radaren

### Universet: fire regionale lister

Aktierne kommer fra `stock_groups` i `config/universe.yaml`:

| Region | Liste | Kilde |
|---|---|---|
| `us` | US (S&P 500) | SSGA's daglige beholdningsfil for SPY, gemt i {{settings:constituents_max_age_days}} dage |
| `europe` | Europe large caps | kurateret liste |
| `nordic` | Nordic (C25 + large caps) | kurateret liste |
| `asia` | Asia (semis & leaders) | kurateret liste |

Scoren beregnes separat for hver liste. En aktie, der står på to lister, får en score i hver.

### Afkastene

`signals/momentum.py` arbejder på de seneste 260 rækker i prismatricen (justerede lukkekurser i noteringsvaluta; rækkerne er i praksis alle hverdage, se [Afkast og renters rente](laerebog/afkast)):

$$
r_{1m} = \frac{P_t}{P_{t-21}} - 1, \quad
r_{3m} = \frac{P_t}{P_{t-63}} - 1, \quad
r_{6m} = \frac{P_t}{P_{t-126}} - 1, \quad
r_{12\text{-}1} = \frac{P_{t-21}}{P_{t-252}} - 1
$$

1-måneds afkastet vises, men indgår ikke i scoren.

### Scoren

Inden for hver region rangeres hvert af de tre afkast med pandas' `rank(pct=True)`: rang divideret med antal aktier med en værdi, hvor den højeste får 1 og lige store værdier deler gennemsnitsrangen. Scoren er

$$
\text{score} = 100 \cdot \frac{q(r_{12\text{-}1}) + q(r_{6m}) + q(r_{3m})}{3}
$$

hvor $q$ er percentilrangen, afrundet til én decimal. Aktierne sorteres efter scoren, og rang 1 er den stærkeste (ved lighed afgør rækkefølgen i listen).

Fire regler er værd at kende:

- **Manglende input giver ingen score.** Mangler ét af de tre afkast, er scoren tom, ikke et gennemsnit af de to andre (`skipna=False`). Aktien vises ikke på toplisten.
- **Historikkrav.** Har en aktie færre end {{settings:momentum.min_history_days}} rækker med kurs i vinduet (`momentum.min_history_days`), sættes 12-1-afkastet og SMA200 til manglende. I praksis kræver 12-1-afkastet desuden en kurs 252 rækker tilbage, altså cirka et års historik. En aktie med 200–252 dages historik får derfor heller ingen score.
- **Laveste mulige score er ikke 0.** Med $N$ aktier i en region er den laveste percentilrang $1/N$, så selv den svageste aktie får $100/N$. For S&P 500 er det 0,2, for en kurateret liste på 40 aktier 2,5.
- **Hver horisont rangeres for sig.** En aktie uden 12-1-afkast (fx en ny notering) indgår stadig i rangeringen af 6- og 3-måneders afkast for de andre, selvom den ikke selv får en score.

Scoren vises i kolonnen *Score* med en farvet måler (`gauges.score` i `settings.yaml`, med markeringer ved {{settings:gauges.score.ticks}}) og ordene *weak*, *below average*, *average*, *strong* og *leader*.

### Toplisten, NEW og frafaldne

For hver region vises de {{settings:momentum.top_n}} bedste (`momentum.top_n`). Hver `radar run` gemmer et øjebliksbillede (*snapshot*) af alle rangeringer i `data/snapshots/` med dato, ticker, rang og score.

- **NEW** markerer en aktie, der er i dagens top {{settings:momentum.top_n}}, men ikke var det i det seneste snapshot, der er mindst {{settings:snapshot_min_gap_days}} dage gammelt (`snapshot_min_gap_days`). Mindsteafstanden sikrer, at du sammenligner med for omkring en uge siden, ikke med i går.
- **Dropped out of top {{settings:momentum.top_n}}** viser de aktier, der var i toppen i det snapshot, men ikke er det nu.
- Findes der intet tilstrækkeligt gammelt snapshot, vises ingen NEW-markeringer.

Momentumtabellen har ingen kolonne for ændring i rang. Den findes på rotationssiderne (kolonnen *Δ rank* for ETF'er, mod samme slags snapshot), og [Discover](/discover) har sin egen ændring i score over 21 dage.

### Klynger (clusters)

Over hver regions tabel viser radaren *Clusters in the top {{settings:momentum.top_n}}*: brancher (*industry*) og sektorer, der er overrepræsenteret blandt de bedste. Branche og sektor kommer fra Yahoo. For hver branche, og derefter hver sektor, beregnes det forventede antal i toppen, hvis lederne var trukket tilfældigt fra regionen:

$$
\text{forventet} = \frac{\#\{\text{aktier i regionen i gruppen}\}}{\#\{\text{aktier i regionen}\}} \cdot N_{\text{top}}
$$

En gruppe vises som klynge, hvis den har mindst {{settings:sectors.cluster_min}} navne i toppen (`sectors.cluster_min`) **og** mindst {{settings:sectors.cluster_ratio}} gange det forventede (`sectors.cluster_ratio`). En sektor springes over, hvis alle dens navne i toppen allerede er dækket af en brancheklynge. Klyngerne sorteres efter forholdet mellem faktisk og forventet antal, og antallet af NEW-navne i klyngen vises. Klynger er branchemomentum gjort synligt: se [Momentumeffekten](laerebog/momentumeffekten#industrimomentum-moskowitz-og-grinblatt-1999).

### Øvrige kolonner

- *From 52w high* (`from_high`): $P_t / \max(P_{t-251}, \dots, P_t) - 1$, afstanden til den højeste lukkekurs de seneste 252 rækker. 0 % er en ny top.
- *Vol 20d/120d* (`vol_surge`): gennemsnitlig volumen de seneste 20 rækker divideret med gennemsnittet over de seneste 120 (som inkluderer de 20). Over 1 betyder mere handel end normalt.
- *Trend* (`trend_ok`): kurs over SMA200 og SMA50 over SMA200; se [Glidende gennemsnit og trend](laerebog/trend).

### Dine beholdninger: percentil mod hele universet

I [Mine beholdninger](/me) beregnes scoren anderledes (`mine._pct_vs`), så aktier fra forskellige markeder kan sammenlignes: for hvert af de tre afkast tælles **andelen af alle aktier i alle fire regioner, der har et strengt lavere afkast** (en aktie på to lister tæller to gange), og gennemsnittet ganges med 100. Mangler ét af beholdningens tre afkast, er der ingen score. To forskelle fra regionsscoren:

1. Sammenligningsgruppen er hele universet, ikke regionen.
2. "Strengt under" giver den laveste 0 og er $1/N$ lavere end `rank(pct=True)` for en aktie uden ligestillede.

Den samme aktie kan derfor have én score på [Momentum](/momentum) og en anden i [Mine beholdninger](/me). På tickerprofilen bruges regionsscoren, hvis aktien er på en regionsliste; ellers andelen strengt under inden for den region, aktien hører til (eller den amerikanske liste, hvis regionen er ukendt). Profilen skriver, hvilket grundlag der er brugt.

Scoren bruges også i de regelbaserede stop: med intakt trend og en score på mindst {{settings:stops.strong_score}} (`stops.strong_score`) får positionen mere plads. Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

## Regneeksempel

### Fem aktier i én region

| Aktie | $r_{12\text{-}1}$ | $r_{6m}$ | $r_{3m}$ |
|---|---|---|---|
| A | 40 % | 25 % | 10 % |
| B | 15 % | 18 % | 12 % |
| C | 60 % | 5 % | −2 % |
| D | −10 % | −5 % | 3 % |
| E | 25 % | 30 % | 15 % |

**Trin 1: percentilrang pr. horisont** (rang fra lavest = 1 til højest = 5, divideret med 5):

| Aktie | $q(r_{12\text{-}1})$ | $q(r_{6m})$ | $q(r_{3m})$ |
|---|---|---|---|
| A | 4/5 = 0,8 | 4/5 = 0,8 | 3/5 = 0,6 |
| B | 2/5 = 0,4 | 3/5 = 0,6 | 4/5 = 0,8 |
| C | 5/5 = 1,0 | 2/5 = 0,4 | 1/5 = 0,2 |
| D | 1/5 = 0,2 | 1/5 = 0,2 | 2/5 = 0,4 |
| E | 3/5 = 0,6 | 5/5 = 1,0 | 5/5 = 1,0 |

**Trin 2: gennemsnit gange 100:**

| Aktie | Beregning | Score | Rang |
|---|---|---|---|
| E | (0,6 + 1,0 + 1,0)/3 · 100 | **86,7** | 1 |
| A | (0,8 + 0,8 + 0,6)/3 · 100 | **73,3** | 2 |
| B | (0,4 + 0,6 + 0,8)/3 · 100 | **60,0** | 3 |
| C | (1,0 + 0,4 + 0,2)/3 · 100 | **53,3** | 4 |
| D | (0,2 + 0,2 + 0,4)/3 · 100 | **26,7** | 5 |

C har det klart bedste 12-1-afkast, men er faldet tilbage de seneste måneder og ender som nummer 4. E er ikke bedst på lang sigt, men stærkest på de to korte horisonter og vinder samlet. Med fem aktier er den lavest mulige score 100/5 = 20.

**Målerne.** E's score på 86,7 ligger mellem ankrene (80; 0,6) og (95; 1) i standardopsætningen: $0.6 + 0.4 \cdot 6.7 / 15 \approx 0.78$, niveau 3 af 4 og ordet *leader*. D's 26,7 ligger mellem (25; −0,5) og (40; 0): $-0.5 + 0.5 \cdot 1.7/15 \approx -0.44$, niveau −2 og ordet *below average*.

### En beholdning mod universet

Du ejer aktie H med $r_{12\text{-}1}$ = 30 %, $r_{6m}$ = 20 % og $r_{3m}$ = 11 %. Lad os for eksemplets skyld sige, at hele universet er de fem aktier ovenfor.

- 12-1: D, B og E (−10, 15, 25) er under 30 → 3/5 = 0,6
- 6m: D, C og B (−5, 5, 18) er under 20 → 3/5 = 0,6
- 3m: C, D og A (−2, 3, 10) er under 11 → 3/5 = 0,6

H's score i [Mine beholdninger](/me) er 60,0.

Til sammenligning: beregnet på samme måde (strengt under) ville E få (2/5 + 4/5 + 4/5)/3 · 100 = 66,7 mod de 86,7 i regionsrangeringen. Forskellen kommer af, at E ikke tæller sig selv som "under", og at gruppen er lille. I et univers på flere hundrede aktier er forskellen mellem metoderne under et point.

### 12-1-afkastet

En aktie lukker i dag på 120, for 21 rækker siden på 114 og for 252 rækker siden på 80. $r_{12\text{-}1} = 114/80 - 1$ = 42,5 %. Dagens kurs indgår ikke.

### En klynge

Regionen har 500 aktier, heraf 15 i branchen *Semiconductors* (3 %) og 70 i sektoren *Technology* (14 %). Toplisten har 20 navne.

- Semiconductors: forventet 0,03 · 20 = 0,6. Fire halvlederaktier i toppen: 4 ≥ {{settings:sectors.cluster_min}}, og 4 ≥ {{settings:sectors.cluster_ratio}} · 0,6. Klynge.
- Technology: forventet 0,14 · 20 = 2,8. Der kræves mindst {{settings:sectors.cluster_ratio}} · 2,8 navne; med standardværdien 1,5 er det 4,2, altså 5 navne. Er der 5 teknologiaktier i toppen, heraf de 4 halvledere, vises sektoren også, fordi den femte ikke er dækket. Er der kun de 4 halvledere, springes sektoren over.

### Volumen

Gennemsnitlig volumen de seneste 20 dage er 3,0 mio. aktier, over 120 dage 2,0 mio. `vol_surge` = 1,5×. Måleren for volumen er envejs (en risikomarkering): ved 1,5× er scoren −0,3 og ordet *elevated volume*.

## Faldgruber og begrænsninger

- **Relativ, ikke absolut.** En score på 90 i et faldende marked kan betyde, at aktien er faldet mindre end de andre. Se også ACWI-trenden på [Regime](/regime).
- **Regionsafhængig.** En nordisk aktie med score 80 er stærk blandt nordiske aktier, ikke nødvendigvis globalt. Brug beholdningsscoren eller *Rel 3m* for at sammenligne på tværs.
- **Lokal valuta.** Afkastene er i noteringsvalutaen. Inden for en region er det oftest den samme valuta, men den nordiske liste blander DKK, SEK, NOK og EUR.
- **Kurateret univers.** Europa, Norden og Asien er udvalgte lister, ikke hele markedet. En stærk aktie uden for listerne ses kun i [Discover](/discover).
- **Ny notering, ingen score.** Børsintroduktioner og spin-offs får først en score efter cirka et år.
- **NEW er relativt til et snapshot.** Kører du sjældent `radar run`, kan "forrige snapshot" være flere uger gammelt, og NEW dækker så over en længere periode.
- **Rang 1 er ikke et købssignal.** Momentumlisten er et udgangspunkt for research: tjek historien bag bevægelsen, værdiansættelse og risiko. Se [brugervejledningen](brugervejledning/momentum).

## Videre læsning

- Narasimhan Jegadeesh og Sheridan Titman: "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency", *Journal of Finance*, 48(1), 1993.
- Clifford S. Asness, Tobias J. Moskowitz og Lasse Heje Pedersen: "Value and Momentum Everywhere", *Journal of Finance*, 68(3), 2013.
- Tobias J. Moskowitz og Mark Grinblatt: "Do Industries Explain Momentum?", *Journal of Finance*, 54(4), 1999.
- Thomas J. George og Chuan-Yang Hwang: "The 52-Week High and Momentum Investing", *Journal of Finance*, 59(5), 2004 (om afstanden til 52-ugers toppen som momentummål).
- Clifford S. Asness, Andrea Frazzini, Ronen Israel og Tobias J. Moskowitz: "Fact, Fiction, and Momentum Investing", *Journal of Portfolio Management*, 40(5), 2014.
