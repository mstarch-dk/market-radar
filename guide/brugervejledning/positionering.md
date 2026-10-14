# Positionering og cyklus

Siden [Positioning & cycle](/positioning) samler de data, der **ikke** kommer fra kurser: analytikernes indtjeningsskøn, værdiansættelse, konjunkturens ledende indikatorer, renter, futuresmarkedets positionering og investorernes stemning. Kurserne fortæller, hvad markedet gør; disse data kan forklare hvorfor, bekræfte en bevægelse eller advare om, at den hviler på et tyndt grundlag.

Siden er det naturlige krydstjek, når noget ser for godt (eller for skidt) ud på [Regime](/regime), [Sector rotation](/rotation) eller [Momentum](/momentum).

Siden har syv afsnit. Nogle af tallene stemmer i regimet; andre er kun til orientering:

| Afsnit | Stemmer i regimet? |
|---|---|
| Indtjeningsrevisioner, S&P 500 (FactSet) | Ja |
| Indtjeningsrevisioner pr. region (Yahoo) | Nej |
| Værdiansættelse: CAPE og risikopræmie | Kun hvis du slår gruppen til på *Regime* |
| Værdiansættelse: yield gap | Nej |
| OECD CLI | Ja, G20 |
| Renter | Nej (USA's 10-årige rente og rentekurven stemmer via *Regime*) |
| CFTC-positionering | Nej |
| Sentiment (AAII, put/call) | Nej, aldrig |

## Earnings revisions (S&P 500, FactSet)

Øverst står tal fra FactSets ugentlige rapport *Earnings Insight* for S&P 500:

- **Growth estimate:** analytikernes skøn for indtjeningsvæksten i indeværende kvartal, og hvad skønnet var ved kvartalets start. Forskellen er det, der stemmer i regimet: hævet mere end {{settings:regime.revisions_band}} procentpoint er risk-on, sænket mere er risk-off.
- **Forward P/E:** kurs i forhold til de næste 12 måneders forventede indtjening, med 5- og 10-årsgennemsnit til sammenligning.
- **EPS guidance:** hvor mange selskaber der har givet positiv og negativ indtjeningsvejledning.
- **Next calendar year growth:** den forventede vækst for næste kalenderår.

Under tallene står, hvilke sektorer der har fået hævet og sænket deres skøn, og en tabel med de seneste rapporter. Stigende skøn i løbet af et kvartal er usædvanligt (normalt sænkes de), og derfor et stærkt signal. Se [Ledende indikatorer og indtjeningsrevisioner](laerebog/ledende-indikatorer) og [Estimatrevisioner](laerebog/estimatrevisioner).

## Earnings revisions by region (Yahoo consensus)

FactSet dækker kun S&P 500. For resten af verden ser radaren på ændringer i Yahoos konsensusskøn mellem ugentlige øjebliksbilleder, pr. radarregion og pr. Discover-marked. For hver region:

| Kolonne | Indhold |
|---|---|
| *Names* | Antal selskaber med skøn i begge øjebliksbilleder |
| *Raised* / *Cut* | Andelen, hvis skøn for næste år er hævet / sænket mere end {{settings:valuation.revision_band|pct}} |
| *Net* | *Raised* minus *Cut*: revisionsbredden, farvet fra *mostly cut* til *mostly raised* |
| *Median change* | Den mediane ændring i skønnet |

Der er en tabel for de seneste 4 uger og en for 12 uger. De første uger efter installation står der i stedet "Building history", fordi radaren først skal have øjebliksbilleder fra 4 og 12 uger tilbage. Tallene er uofficielle og stemmer ikke.

## Valuation

Tre mål for, hvor dyrt det amerikanske aktiemarked er:

- **Shiller CAPE (S&P 500):** kurs i forhold til 10 års inflationsjusteret indtjening, med percentil siden 1871 og siden 1990 og medianen. Højt er dyrt.
- **Implied equity risk premium (Damodaran):** det merafkast over 10-årige statsobligationer, som indeksets kurs implicit lover. Lavt betyder, at investorerne accepterer en tynd belønning for aktierisiko. Percentil siden 2008.
- **Earnings yield − real yield:** indtjeningsafkastet (1 / FactSets forward P/E) minus den amerikanske 10-årige realrente, i procentpoint. En simpel, aktuel udgave af risikopræmien.

Hvert mål har et graderet mærke, og graferne viser CAPE og risikopræmien over tid med medianen som linje.

CAPE og risikopræmien kan stemme i regimet (CAPE-percentil mindst {{settings:regime.cape_rich_pct}} er risk-off, højst {{settings:regime.cape_cheap_pct}} risk-on; risikopræmie-percentil højst {{settings:regime.erp_low_pct}} er risk-off, mindst {{settings:regime.erp_high_pct}} risk-on), men kun hvis du slår gruppen *Valuation* til på [Regime](brugervejledning/regime#grupper-du-kan-slå-til-og-fra). Som standard er den slået fra: værdiansættelse siger meget om de næste ti års afkast og lidt om de næste måneder, og et dyrt marked kan blive ved med at være dyrt længe. Se [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie).

## Leading indicators (OECD CLI)

OECD's sammensatte ledende indikatorer (CLI) for G20, USA, Europa (de fire store: Tyskland, Frankrig, Italien og Storbritannien) og Kina. 100 er den langsigtede trend. Indikatoren har tendens til at vende før økonomien.

| Kolonne | Indhold |
|---|---|
| *CLI* | Seneste værdi |
| *3m change* | Ændringen over 3 måneder, farvet fra *slowing* til *improving* |
| *Phase* | Konjunkturfasen |
| *As of* | Måned (OECD offentliggør med ca. 2 måneders forsinkelse) |

Faserne er:

| Fase | CLI | Retning |
|---|---|---|
| *Expansion* | over 100 | stigende |
| *Slowdown* | over 100 | faldende |
| *Contraction* | under 100 | faldende |
| *Recovery* | under 100 | stigende |

G20's fase stemmer i regimet: *Expansion* er risk-on, *Contraction* risk-off, de to andre neutrale. Faserne hænger sammen med, hvilke sektorer der plejer at føre; se [Sektorer, temaer, faktorer og konjunkturcyklussen](laerebog/rotation-og-cyklus).

## Rates: US and euro area

En tabel med de seneste 10-årige renter (USA, euroområdets AAA-kurve fra ECB, den amerikanske realrente og breakeven-inflationen) og en graf over tid. Realrenten er renten efter forventet inflation; breakeven er den inflation, obligationsmarkedet prissætter. Renterne er her til orientering; den amerikanske 10-årige rente og rentekurven stemmer via indikatorerne på *Regime*. Se [Kredit, renter og dollar](laerebog/kredit-renter-dollar).

## Futures positioning (CFTC)

CFTC's ugentlige *Commitments of Traders* viser, hvordan forskellige grupper af handlende er positioneret i futures på aktieindeks (S&P 500, Nasdaq-100, Russell 2000), VIX, amerikanske 10-årige obligationer, euro, guld, olie og kobber.

| Kolonne | Indhold |
|---|---|
| *Market* | Futuresmarkedet |
| *Trader group* | Asset managers (langsomme, trendfølgende penge), leveraged funds (hedgefonde) eller managed money (CTA'er) |
| *Net % of OI* | Nettoposition (long minus short) i procent af den samlede åbne interesse |
| *4w change* | Ændringen over 4 uger |
| *3y percentile* | Hvor dagens nettoposition ligger i sit eget interval over de seneste {{settings:positioning.lookback_weeks}} uger (0 = lavest, 100 = højest) |
| *Flag* | *3y high* eller *3y low*, når percentilen er i top eller bund {{settings:positioning.extreme_pct}} % |
| *As of* | Positionsdato (tirsdag, offentliggjort fredag) |

Percentilen er farvet efter, hvor langt den er fra midten: fra *crowded short* over *normal* til *crowded long*. Et *3y low* kan stadig være netto long; det er lavt **i forhold til sin egen historik**.

Ekstreme positioner hos de hurtige penge (leveraged funds og managed money) har en tendens til at være kontrære: når alle allerede er positioneret samme vej, er der få købere eller sælgere tilbage. Det er ikke et timingsignal i sig selv, men det fortæller, hvilken vej en vending ville gøre mest ondt. Se [Futurespositionering (CFTC COT)](laerebog/cot).

## Sentiment

To målinger af stemningen blandt amerikanske investorer:

- **AAII survey:** andelen af medlemmerne i American Association of Individual Investors, der er positive, minus andelen, der er negative, om de næste 6 måneder. Vist med percentil siden 1987, fordelingen og 8-ugers gennemsnit, plus en graf over spændet.
- **Equity put/call (CBOE):** antal handlede put-optioner pr. call-option på aktier, som 10-dages gennemsnit og percentil over ca. 3 år ({{settings:sentiment.putcall_lookback_days}} handelsdage). Percentilen kræver 60 dages data; indtil da står antallet af lagrede dage.

Begge er **kontrære**: ekstrem frygt (lav AAII-percentil, højt put/call) er farvet grøn, fordi den historisk oftere er kommet før bedre afkast; eufori og selvtilfredshed er farvet rød. For AAII regnes percentiler på højst {{settings:sentiment.aaii_extreme_pct}} som ekstrem frygt.

> **Bemærk:** Kontrære målinger stemmer aldrig i regimet. De time'r ikke en vending, og de er amerikanske. Brug dem til at vurdere, om stemningen er gået for langt, ikke til at handle på. Se [Put/call og AAII: kontrær sentiment](laerebog/sentiment).

## Sådan bruger du siden

- **Bekræft prisbevægelser.** Stiger markedet, mens indtjeningsskønnene hæves, og OECD CLI er i *Expansion* eller *Recovery*, hviler optrenden på mere end kurser.
- **Kig efter uenighed.** Er regimet *Risk-on*, mens skønnene sænkes, CFTC viser *3y high* hos de hurtige penge, og AAII viser eufori, er det et tegn på, at forventningerne er høje, og at skuffelser kan ramme hårdt.
- **Brug værdiansættelsen til forventninger, ikke timing.** En høj CAPE er et argument for lavere forventninger til de næste ti år, ikke for at sælge i morgen.
- **Tjek datoerne.** Kilderne opdateres med forskellig takt (FactSet og CFTC ugentligt, OECD månedligt med forsinkelse). Se alder og status for hver kilde på [Data & coverage](/data).
