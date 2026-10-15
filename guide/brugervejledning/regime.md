# Regime

Siden [Regime](/regime) svarer på det første spørgsmål i det ugentlige overblik: hvordan er "vejret" på aktiemarkedet lige nu? Omkring 20 indikatorer for trend, markedsbredde, volatilitet, kredit, renter, dollar, råvarer, konjunktur og indtjening giver hver deres stemme, og stemmerne lægges sammen til en samlet vurdering: *Risk-on*, *Mixed* (blandet) eller *Risk-off*.

Regimet er ikke en prognose. Det beskriver, om de målte input i dag peger mod risikovillighed eller forsigtighed. Teorien står i [Risk-on og risk-off](laerebog/risk-on-risk-off) og [Radarens afstemningsmodel](laerebog/afstemningsmodellen).

## Den samlede vurdering

Øverst står *Overall reading* med et farvet mærke:

| Mærke | Betydning |
|---|---|
| *Risk-on* (grøn) | Klart flere indikatorer peger mod risikovillighed end mod forsigtighed |
| *Mixed* (gul) | Billedet er blandet |
| *Risk-off* (rød) | Klart flere indikatorer peger mod forsigtighed |

Under mærket står optællingen, fx "7 risk-on · 3 risk-off · 8 neutral/informational · 1 stale · net 0.40". Kun indikatorer, der stemmer *risk-on* eller *risk-off*, indgår i nettotallet:

$$
\text{net} = \frac{\text{on} - \text{off}}{\text{on} + \text{off}}
$$

Er nettotallet over +0,33, er vurderingen *Risk-on*; under −0,33 er den *Risk-off*; ellers *Mixed*. Grænsen på 0,33 ligger fast i koden. Med 7 risk-on og 3 risk-off bliver netto (7 − 3) / 10 = 0,4, altså *Risk-on*.

Det betyder også, at neutrale rækker ikke trækker vurderingen mod midten. Er der kun to stemmer, begge risk-on, er nettotallet 1. Kig derfor altid på, hvor mange der faktisk stemmer.

### Hvad der ikke tæller
Følgende rækker vises, men tæller ikke i nettotallet:

- **neutral:** indikatoren ligger mellem sine tærskler, eller den er kun til information.
- **n/a:** der er ingen data (kilden mangler, eller historikken er for kort).
- **stale:** data er ældre end kildens maksimale alder (se nedenfor).
- **not voting:** indikatoren hører til en gruppe, du har slået fra (se [Grupper du kan slå til og fra](brugervejledning/regime#grupper-du-kan-slå-til-og-fra)).
- **context:** rækken er kun til baggrund og stemmer aldrig (de tre momentumrækker nedenfor). Den tæller med i "shown but not voting" i optællingen.

### Dækningslinjen
Under afstemningen står en linje som "18 of 20 indicators have current data", efterfulgt af de rækker, der mangler data eller er forældede, det ældste input med dato, og eventuelle kilder, hvis seneste opdatering fejlede. Linket *Data & coverage →* fører til siden med alle kilder. Context-rækkerne tælles ikke med her. Læs den linje, før du stoler på vurderingen: et *Risk-on* bygget på halvdelen af indikatorerne er svagere end et bygget på dem alle.

## Indikatortabellen

Under *Indicators* står én række pr. indikator med disse kolonner:

| Kolonne | Indhold |
|---|---|
| *Indicator* | Navnet, fx *Volatility (VIX)* eller *Breadth – Nordic (C25 + large caps)* |
| *Reading* | Den aktuelle aflæsning, fx "16.2" eller "+4.1% vs 200d" |
| *Vote* | Rækkens stemme: *risk-on*, *risk-off*, *neutral*, *n/a* eller *stale*; plus *not voting*, hvis gruppen er slået fra, eller *context* for en baggrundsrække |
| *Reading, graded* | Et ord og en lille skala med tærskler og en markør, farvet efter hvor tæt aflæsningen er på tærsklerne |
| *Context* | Forklaring, fx ændring over en måned og datadato |

Den graderede skala er nyttig, fordi den viser **hvor tæt** en indikator er på at skifte stemme. En VIX lige under den rolige grænse og en VIX langt under giver samme stemme, men ikke samme margin.

### Indikatorerne og deres regler

| Indikator | Risk-on når … | Risk-off når … |
|---|---|---|
| Global trend (ACWI) | kursen og 50-dages snit er over 200-dages snit | begge er under 200-dages snit |
| Markedsbredde, én pr. region | mindst {{settings:regime.breadth_strong}} % af aktierne er over deres 200-dages snit | højst {{settings:regime.breadth_weak}} % er |
| Nye højder minus nye lavpunkter | netto mindst +{{settings:regime.highs_lows_band}} % | netto højst −{{settings:regime.highs_lows_band}} % |
| Volatility (VIX) | under {{settings:regime.vix_calm}} | over {{settings:regime.vix_stress}} |
| VIX-terminsstruktur (VIX/VIX3M) | under {{settings:regime.vix_term_calm}} | over 1 (inverteret) |
| Kreditspænd, US high yield | mere end 3 % under sit 6-måneders snit | mere end 3 % over |
| Kreditspænd, euro high yield | som ovenfor | som ovenfor |
| US-dollar (bred) | faldet mere end 3 % over 3 måneder | steget mere end 3 % |
| Kobber/guld | steget mere end {{settings:regime.copper_gold_band|pct}} over 3 måneder | faldet mere end {{settings:regime.copper_gold_band|pct}} |
| OECD CLI (G20) | fasen er ekspansion | fasen er kontraktion |
| Indtjeningsrevisioner (S&P 500, FactSet) | kvartalets vækstskøn hævet mere end {{settings:regime.revisions_band}} procentpoint siden kvartalets start | sænket mere end {{settings:regime.revisions_band}} |
| Shiller CAPE (US) | percentil højst {{settings:regime.cape_cheap_pct}} | percentil mindst {{settings:regime.cape_rich_pct}} |
| Implicit risikopræmie (Damodaran) | percentil mindst {{settings:regime.erp_high_pct}} | percentil højst {{settings:regime.erp_low_pct}} |

Tærsklerne på 3 % for kreditspænd og dollar ligger fast i koden; de øvrige står i `config/settings.yaml`.

Nogle indikatorer kan **kun stemme risk-off**, fordi de advarer om stress, men ikke i sig selv er et tegn på styrke:

- *Yield curve (10Y-2Y)*: risk-off, når rentekurven er inverteret (under 0); ellers neutral.
- *US 10Y yield*: risk-off, når renten er steget mere end {{settings:regime.rates_shock}} procentpoint over 3 måneder; ellers neutral.
- *Oil (WTI)*: risk-off, når olien er steget mere end {{settings:regime.oil_shock|pct}} over 3 måneder; ellers neutral.

Én indikator **stemmer aldrig**: *Equal vs cap weight (RSP/SPY)* viser, om den gennemsnitlige aktie slår indekset (bred fremgang) eller om få megaselskaber bærer det (smal fremgang). Den står der til information.

Tre rækker om momentum selv stemmer heller aldrig og er mærket *context*. De siger noget om, hvordan momentumscoren har det, ikke om markedet er risikovilligt:

- *Momentum payoff (top − bottom quintile)*: hvad scoren har givet. Det er afkastet for den bedste femtedel af aktierne minus den dårligste over de seneste 3 måneder, med scoren som den var for 3 måneder siden (og det samme for 1 måned). Står MTUM i kurserne, vises også MTUM mod ACWI. Over ±{{settings:regime.momentum_payoff_band|pct}} hedder aflæsningen *paying* eller *losing*.
- *Return dispersion (3m, all stocks)*: spredningen i 3-måneders afkast mellem aktierne (75 %-fraktilen minus 25 %-fraktilen) og dens percentil i radarens egen historik. Ved højst {{settings:regime.dispersion_low_pct}}. percentil hedder den *narrow*, ved mindst {{settings:regime.dispersion_high_pct}}. *wide*. En bred spredning giver momentum mere at sortere på.
- *Momentum-crash setup (ACWI)*: *watch*, når ACWI har tabt over 2 år, og *yes*, når den derefter er steget mindst {{settings:regime.crash_rebound|pct}} på en måned. Det er netop den situation, hvor momentum historisk er krakket. Se [Momentumeffekten](laerebog/momentumeffekten).

Hvorfor netop disse indikatorer, og hvad de hver især siger, står i lærebogens del IV: [Markedsbredde](laerebog/markedsbredde), [VIX og volatilitetens terminsstruktur](laerebog/vix), [Kredit, renter og dollar](laerebog/kredit-renter-dollar), [Kobber, guld og olie](laerebog/raavarer) og [Ledende indikatorer og indtjeningsrevisioner](laerebog/ledende-indikatorer).

### Forældede data (stale)
Hver række har en kilde, og hver kilde har en maksimal alder. Er rækkens data ældre end grænsen, regnet fra dashboardets datadato, bliver status *stale*: aflæsningen vises nedtonet, konteksten siger "older than N days: not counted", og rækken tæller ikke med. Grænserne er:

| Kilde | Maksimal alder (dage) |
|---|---|
| Kurser (trend, bredde, VIX, råvarer) | {{settings:coverage.max_age.prices}} |
| FRED (kredit, renter, dollar) | {{settings:coverage.max_age.fred}} |
| FactSet | {{settings:coverage.max_age.factset}} |
| OECD CLI | {{settings:coverage.max_age.oecd}} |
| CAPE | {{settings:coverage.max_age.cape}} |
| Risikopræmie (ERP) | {{settings:coverage.max_age.erp}} |

## Grupper du kan slå til og fra

Kortet *Counted in the vote* har afkrydsningsfelter for to grupper af indikatorer:

- *Euro high-yield spread*: det europæiske kreditspænd ved siden af det amerikanske. Standard: {{settings:regime.votes.credit_eu}}.
- *Valuation (CAPE, equity risk premium)*: Shiller CAPE og Damodarans risikopræmie. Standard: {{settings:regime.votes.valuation}}.

Værdiansættelse er slået fra som standard, fordi den bevæger sig langsomt: et dyrt marked kan forblive dyrt i årevis, så den er ikke et timingsignal på 1–6 måneder. Rækkerne vises stadig, med mærket *not voting*, så du kan se aflæsningen.

Dit valg virker med det samme, uden en ny opdatering. Det gemmes på din computer og bruges alle steder, regimet bruges: på denne side, i bredden af stop på dine beholdninger og ved næste `radar report` (som Claude Code-kommandoerne læser). Afviger dit valg fra standarden, står standarden i parentes.

## Graferne

Under *Charts* ligger historikken bag de vigtigste aflæsninger:

- *Global trend – MSCI ACWI* med 50- og 200-dages snit
- *Breadth – % of stocks above their 200-day average*, én linje pr. region
- *High-yield credit spreads, US and euro (%)*
- *New 52w highs minus new lows*
- *Volatility – VIX* og *VIX term structure*
- *Copper/gold ratio*
- *OECD leading indicators (100 = trend)*

Stiplede vandrette linjer er tærsklerne fra tabellen. Knapperne *6M*, *1Y*, *3Y* og *All* vælger periode, og når du bevæger musen hen over grafen, viser en aflæsning værdierne på den dag.

## Sådan bruger du siden

- **Start her hver uge.** Er regimet *Risk-off*, er det et argument for at være mere kritisk over for nye positioner og for at stramme op, ikke en ordre om at sælge.
- **Se efter ændringer, ikke niveauer.** Et skift fra *Risk-on* til *Mixed* og flere indikatorer, der nærmer sig deres tærskler, er mere interessant end en enkelt uge.
- **Tjek bredden.** Stiger indekset, mens markedsbredden falder, og RSP/SPY viser smal fremgang, hviler optrenden på få navne.
- **Tjek dækningen.** Mange *n/a*- eller *stale*-rækker betyder, at vurderingen bygger på færre input end normalt. Opdater data, eller se på [Data & coverage](/data), hvilken kilde der halter.

> **Bemærk:** Regimet påvirker også dine beholdninger: i et *Mixed*- eller *Risk-off*-regime bliver de regelbaserede trailing stops strammere. Se [Mine beholdninger og watchlist](brugervejledning/beholdninger).

De ikke-prisbaserede data bag nogle af indikatorerne (FactSet, OECD, CAPE) og de kontrære målinger, der aldrig stemmer, står på [Positionering og cyklus](brugervejledning/positionering).
