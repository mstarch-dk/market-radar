# Afkast og renters rente

Alt i radaren hviler på ét tal: hvor meget en kurs har ændret sig over en periode. Det lyder enkelt, men der er flere måder at måle det på, og de giver forskellige svar. Dette kapitel gennemgår de begreber, resten af bogen bygger på: simpelt afkast og log-afkast, renters rente, annualisering, forskellen på aritmetisk og geometrisk gennemsnit, volatilitetstræk og totalafkast.

## Intuition

Køber du en aktie til 100 kr. og sælger den til 110 kr., har du tjent 10 %. Det er det *simple afkast*. Falder den bagefter 10 %, er du ikke tilbage på 100 kr., men på 99 kr. Procenter lægges ikke sammen; de ganges. Det er renters rente, og det virker begge veje: gevinster bygger oven på gevinster, og et tab skal indhentes med en større procentvis gevinst (et fald på 50 % kræver en stigning på 100 %).

Derfor er det vigtigt at skelne mellem:

- **gennemsnittet af de enkelte perioders afkast** (det aritmetiske gennemsnit), som siger noget om en typisk periode, og
- **den faste vækstrate, der faktisk fører fra start til slut** (det geometriske gennemsnit), som er det, din formue oplever.

Forskellen mellem de to vokser med svingningerne. To investeringer med samme gennemsnitlige månedsafkast ender forskellige steder, hvis den ene svinger mere. Det kaldes volatilitetstræk (*volatility drag*).

Endelig er kursen ikke hele afkastet. Udbytter er også afkast, og en kurs, der falder på udbyttedagen, er ikke et tab. Radaren regner derfor på *justerede* kurser, så afkast er totalafkast. Det uddybes i [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).

## Teori

### Simpelt afkast

Det simple afkast fra tidspunkt $t-1$ til $t$ er

$$
R_t = \frac{P_t}{P_{t-1}} - 1
$$

hvor $P_t$ er kursen (helst den udbyttejusterede). Over flere perioder ganges vækstfaktorerne $(1+R_t)$:

$$
1 + R_{0 \to T} = \prod_{t=1}^{T} (1 + R_t) = \frac{P_T}{P_0}
$$

Det simple afkast har en praktisk egenskab: en porteføljes afkast i én periode er det vægtede gennemsnit af positionernes afkast, $R_p = \sum_i w_i R_i$. Derfor bruges det til porteføljer og til at sammenligne med et benchmark.

### Log-afkast

Log-afkastet (det kontinuerte afkast) er

$$
r_t = \ln\!\left(\frac{P_t}{P_{t-1}}\right) = \ln(1 + R_t)
$$

Fordelen er, at log-afkast *lægges sammen* over tid: $r_{0 \to T} = \sum_t r_t = \ln(P_T / P_0)$. Det gør dem bekvemme i statistik, fx når man beregner volatilitet, fordi summer af uafhængige stokastiske variable er lettere at regne på end produkter. Ulempen er, at de ikke kan vægtes sammen på tværs af positioner i en portefølje.

For små afkast er de to næsten ens ($\ln(1+R) \approx R - R^2/2$), men forskellen vokser: +50 % simpelt afkast er kun 40,5 % i log-afkast, og −50 % er −69,3 %.

### Renters rente og annualisering

Hvis et beløb vokser med en fast rate $g$ om året i $n$ år, er slutværdien $(1+g)^n$. Omvendt kan et samlet afkast $R$ over $d$ kalenderdage omregnes til en årlig rate:

$$
R_{\text{p.a.}} = (1 + R)^{365/d} - 1
$$

Med handelsdage bruger man ofte 252 som et år: $(1+R)^{252/n} - 1$ for $n$ handelsdage. Annualisering af korte perioder er dog misvisende. Et afkast på 5 % på en måned bliver til næsten 80 % om året, men det siger intet om de næste elleve måneder. Annualisering *ekstrapolerer* en kort periode, som om den ville gentage sig.

Volatilitet annualiseres anderledes, fordi varianser (ikke standardafvigelser) lægges sammen over uafhængige perioder: $\sigma_{\text{år}} = \sigma_{\text{dag}} \sqrt{252}$. Se [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown).

### Aritmetisk og geometrisk gennemsnit

For $T$ periodeafkast $R_1, \dots, R_T$ er

$$
\bar R_{\text{aritm}} = \frac{1}{T} \sum_{t=1}^{T} R_t,
\qquad
\bar R_{\text{geom}} = \left( \prod_{t=1}^{T} (1 + R_t) \right)^{1/T} - 1
$$

Det geometriske gennemsnit er altid mindre end eller lig med det aritmetiske (ulighed mellem aritmetisk og geometrisk middel), og de er kun ens, når alle afkast er ens. Det aritmetiske gennemsnit er det bedste skøn over *én* fremtidig periodes forventede afkast; det geometriske beskriver den realiserede vækst over hele forløbet.

### Volatilitetstræk

En nyttig tilnærmelse forbinder de to:

$$
\bar R_{\text{geom}} \approx \bar R_{\text{aritm}} - \frac{\sigma^2}{2}
$$

hvor $\sigma$ er standardafvigelsen af periodeafkastene. Med et aritmetisk årsafkast på 8 % og en volatilitet på 20 % er det geometriske afkast cirka 8 − (0,2²/2)·100 = 8 − 2 = 6 %. To procentpoint om året forsvinder i svingningerne. Det er en af grundene til, at volatilitet koster, selv for en investor, der aldrig sælger i panik, og at gearede produkter med daglig rebalancering kan tabe værdi i et marked, der ender, hvor det startede (Messmore 1995 kaldte fænomenet *variance drain*).

### Totalafkast

Totalafkastet medregner udbytter (og andre udlodninger), som om de blev geninvesteret på udbyttedagen:

$$
1 + R^{\text{TR}}_t = \frac{P_t + D_t}{P_{t-1}}
$$

hvor $D_t$ er udbyttet, der går ex i periode $t$. Over lange perioder er forskellen stor: for brede aktieindeks har udbytter historisk udgjort en væsentlig del af det samlede realafkast (Dimson, Marsh og Staunton 2002). Et kursindeks undervurderer derfor systematisk, hvad en ejer har fået.

## Sådan gør radaren

### Afkast over faste vinduer

Radaren måler afkast over et fast antal rækker i prismatricen, ikke over kalendermåneder:

| Navn i appen | Kolonne | Vindue |
|---|---|---|
| *1m* | `r1m` | 21 rækker (ca. en måned) |
| *3m* | `r3m` | 63 rækker (ca. tre måneder) |
| *6m* | `r6m` | 126 rækker (ca. seks måneder) |
| *12-1m* | `r12_1` | fra 252 til 21 rækker tilbage |

Formlen er det simple afkast, fx

$$
r_{3m} = \frac{P_{t}}{P_{t-63}} - 1
$$

og 12-1-afkastet springer den seneste måned over:

$$
r_{12\text{-}1} = \frac{P_{t-21}}{P_{t-252}} - 1
$$

Hvorfor den sidste måned udelades, forklares i [Momentumeffekten](laerebog/momentumeffekten). Vinduerne er faste i koden (`signals/momentum.py`), ikke i `settings.yaml`.

Kurserne er udbyttejusterede lukkekurser i noteringsvalutaen, så alle afkastene er totalafkast. En ting er værd at vide: prismatricen har én række for hver dato, hvor *et eller andet* af radarens instrumenter (inklusive valutakurser) har handlet, og huller fyldes med seneste kurs i op til 5 rækker. I praksis er det alle hverdage, så 252 rækker er lidt under et kalenderår (ca. 50 uger), og en børs' helligdag tæller som en flad dag. Det er bevidst: alle tickers måles over præcis samme kalenderperiode, uanset børs.

De samme vinduer (21, 63, 126 og 252 rækker) bruges på [Afkast over tid](/returns) til porteføljernes periodeafkast, og *ytd* regnes fra 1. januar.

### Annualisering kun med mindst ét år

På [Afkast over tid](/returns) (`portfolios/performance.py`) vises det tidsvægtede afkast både samlet og pr. år, men det årlige tal kræver mindst 365 kalenderdage:

$$
R_{\text{p.a.}} = (1 + R_{\text{total}})^{365/d} - 1, \qquad d \ge 365
$$

Under et år er feltet tomt, ikke et ekstrapoleret tal. Det samme gælder det pengevægtede afkast (XIRR), som også er en årlig rate. Grænsen på 365 dage står i koden. Se [Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr).

Der er én undtagelse at kende: risikostatistikkerne på tickerprofilen (`signals/risk.py`) annualiserer det geometriske ugeafkast med 52 uger, så snart der er {{settings:risk.min_weeks}} ugers data, altså også under et år. De er beskrivende statistik af et vindue, ikke et afkastløfte.

### Holdings: totalafkast i DKK

For dine beholdninger regner radaren afkastet siden køb i DKK, med udbytter som geninvesteret og kurtage som en del af anskaffelsessummen. Se [Benchmark og relativt afkast](laerebog/benchmark).

## Regneeksempel

### Simple og log-afkast over to dage

En aktie går fra 100 til 110 og derefter til 99.

| | Simpelt afkast | Log-afkast |
|---|---|---|
| Dag 1 | 110/100 − 1 = +10,0 % | ln(1,1) = +9,53 % |
| Dag 2 | 99/110 − 1 = −10,0 % | ln(0,9) = −10,54 % |
| Samlet | 1,1 · 0,9 − 1 = −1,0 % | 9,53 − 10,54 = −1,01 % |

Det aritmetiske gennemsnit af de simple afkast er 0 %, men du har tabt 1 %. Det geometriske gennemsnit pr. dag er $\sqrt{0.99} - 1$ = −0,50 %. Tilnærmelsen $\bar R - \sigma^2/2$ giver $0 - 0.1^2/2 = -0.005$, altså −0,5 %, når man bruger 10 % som spredning: volatilitetstrækket.

### Radarens vinduer

En aktie lukker i dag på 120. For 21 rækker siden lukkede den på 114, for 63 rækker siden på 100, for 126 rækker siden på 96 og for 252 rækker siden på 80.

- $r_{1m} = 120/114 - 1$ = 5,26 %
- $r_{3m} = 120/100 - 1$ = 20,0 %
- $r_{6m} = 120/96 - 1$ = 25,0 %
- $r_{12\text{-}1} = 114/80 - 1$ = 42,5 % (bemærk: tælleren er kursen for en måned siden, 114, ikke dagens 120)

### Annualisering

En portefølje har et tidsvægtet afkast på 25 % over 500 dage. Det årlige afkast er

$$
1.25^{365/500} - 1 = e^{0.73 \cdot \ln 1.25} - 1 = e^{0.1629} - 1 \approx 17.7\ \%
$$

Havde perioden været 200 dage, ville radaren ikke vise noget årligt tal: $1.25^{365/200} - 1$ ville give 50,3 %, et tal, der mest afspejler tilfældighederne i et halvt år.

## Faldgruber og begrænsninger

- **Procenter kan ikke lægges sammen.** +10 % og −10 % er ikke 0 %. Sammenlign altid vækstfaktorer.
- **Gennemsnit af afkast overvurderer væksten.** Et højt aritmetisk gennemsnit med stor volatilitet kan dække over en beskeden geometrisk vækst.
- **Annualisering af korte perioder** forstørrer støj. Radaren viser derfor kun årlige rater for porteføljer med mindst et års historik.
- **Kursafkast er ikke totalafkast.** Et højt udbytte ligner et kursfald på ex-dagen. Radaren bruger justerede kurser, men en ekstern graf gør det måske ikke.
- **Valuta.** Radarens momentumafkast er i noteringsvalutaen. For en dansk investor er afkastet i DKK det, der tæller; se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).
- **Rækker er ikke kalenderdage.** "1m" er 21 rækker i den fælles kalender, ikke nødvendigvis fra samme dato sidste måned.

## Videre læsning

- Zvi Bodie, Alex Kane og Alan J. Marcus: *Investments*, McGraw-Hill (mange udgaver), kapitel om afkast og risiko.
- Elroy Dimson, Paul Marsh og Mike Staunton: *Triumph of the Optimists: 101 Years of Global Investment Returns*, Princeton University Press, 2002.
- Tom Messmore: "Variance Drain", *Journal of Portfolio Management*, 21(4), 1995.
- John Y. Campbell, Andrew W. Lo og A. Craig MacKinlay: *The Econometrics of Financial Markets*, Princeton University Press, 1997, kapitel 1 (simple og log-afkast).
