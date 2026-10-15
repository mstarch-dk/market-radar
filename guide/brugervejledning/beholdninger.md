# Mine beholdninger og watchlist

Siden [Holdings & watchlist](/me) viser dine egne navne i tre tabeller: det, du ejer nu (*Holdings*), det, du holder øje med (*Watchlist*), og det, du har solgt (*Sold positions*). Hvert navn får radarens momentum, dit afkast i DKK målt mod en skyggeposition i ACWI, regelbaserede advarsler og, for beholdninger, et gennemgangsniveau.

Tallene regnes live ud fra de seneste kurser, hver gang du åbner siden. Regimet og rotationsgrafens kvadranter, som niveauerne bruger, kommer fra den seneste opdatering.

## Hvor kommer navnene fra?

- **Beholdninger og solgte positioner** følger af dine handler på siden [Portfolio](/portfolio). Se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).
- **Watchlisten** bygger du selv: klik ☆ ud for et navn i en tabel, eller *Add to watchlist* på en [tickerprofil](brugervejledning/tickerprofil). ★ tager det af igen. Ændringerne gemmes i `userdata/` og overlever en ny import. Navne fra listen `watchlist:` i `config/universe.yaml` og watchlisten fra en Yahoo-import kommer også med.

Har du ingen beholdninger endnu, foreslår siden at importere dem fra Yahoo Finance nederst (se [Hurtig import fra Yahoo Finance](#hurtig-import-fra-yahoo-finance)).

## Vælg portefølje

Over tabellerne står vælgeren *Portfolio*. Som standard viser siden *Yours: every real portfolio*: alle dine rigtige porteføljer lagt sammen, uden arkiverede og virtuelle. Du kan i stedet vælge én portefølje, alle virtuelle, alle med et bestemt tag eller *Everything, virtual included*. Valget står i adressen som `?pf=` (fx `?pf=3` eller `?pf=tag:momentum-a`), så du kan gemme et bogmærke til en bestemt visning. Viser siden andet end dine egne porteføljer, står der *Showing the chosen portfolios, not only yours.*, og *back to yours* fører dig tilbage. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

## Kolonnerne

Alle tre tabeller har de samme grundkolonner:

| Kolonne | Betyder |
|---|---|
| *Score* | Momentumpercentil 0–100 mod hele aktieuniverset på tværs af regioner, så navne fra forskellige markeder kan sammenlignes |
| *1m*, *3m*, *6m* | Afkast over 1, 3 og 6 måneder i handelsvalutaen |
| *Rel 3m* | 3-måneders afkast minus ACWI's, i procentpoint |
| *From high* | Afstand til 52-ugers høj |
| *Signals* | Én prik pr. graderet aflæsning: RSI, momentumscore, afstand til 52-ugers høj, stop, kursmål og afkast mod ACWI. Hold musen over for detaljer |
| *P/E* | Aktier: P/E på næste års forventede indtjening; fonde: Yahoos P/E for fonden. Flere værdiansættelseskolonner kan slås til i tabellens værktøjslinje |
| *Flags* | Regelbaserede mærker (se nedenfor) |

*Trend* (50-dages over et stigende 200-dages) er skjult som standard og kan slås til. Tabellerne kan sorteres, søges i, filtreres og hentes som CSV; filtrene står i adressen.

### Kun for beholdninger

| Kolonne | Betyder |
|---|---|
| *Since buy (DKK)* | Den åbne positions samlede afkast i DKK, inklusive valutakurs og udbytte (brutto, regnet som geninvesteret), efter gennemsnitsmetoden |
| *ACWI (DKK)* | Samme beløb i en skyggeposition i ACWI |
| *Review* | Gennemgangsniveauet (200-dages gennemsnittet) og afstanden til det. Med `stops.mode: atr` er det i stedet det glidende stop |
| *Target* | Take-profit (kursmål) og afstanden til det. Vises kun, når kursmålet er slået til (`stops.take_profit`) |

### Kun for solgte positioner

*Sold* er datoen for dit seneste salg, og *Since sell* er, hvor meget kursen har bevæget sig siden. Kolonnen er nyttig, når du vil se, om et salg var klogt.

## Afkast mod en skyggeposition i ACWI

*Since buy* og *ACWI (DKK)* er bygget til at besvare ét spørgsmål: havde det været bedre bare at eje verdensindekset?

- Hver gang du købte, lægges det samme beløb i DKK (inklusive kurtage) i ACWI samme dag.
- Hver gang du solgte, fjernes den samme andel fra begge.
- Udbytte regnes som geninvesteret på begge sider, fordi kurserne er udbyttejusterede.

Farven på *Since buy* følger forskellen mellem de to: grøn, når positionen er foran ACWI, rød, når den er bagefter. Se [Benchmark og relativt afkast](laerebog/benchmark).

Afkastet er det samlede for alle dine valgte porteføljer. Det er rigtigt til sammenligningen med ACWI, men ikke til skat, hvor en aktiesparekonto opgøres for sig.

Kan afkastet ikke regnes ud, står der et mærke i stedet: *can't compute return* (fx en manglende valutakurs) eller *check purchase price units*, når resultatet er urimeligt. Det sidste skyldes næsten altid en købskurs i pund, hvor Yahoo bruger pence (GBp), eller omvendt.

## Flagene

De grå mærker i *Flags* er regler, der beskriver tilstanden. Hvilke der kan forekomme, afhænger af tabellen:

| Mærke | Hvor | Betingelse |
|---|---|---|
| *trend intact* | alle | 50-dages gennemsnit over et stigende 200-dages |
| *losing momentum* | beholdninger | Kursen under 50-dages gennemsnittet og negativt afkast over 1 måned |
| *below 200d* | beholdninger | Kursen under 200-dages gennemsnittet |
| *turning up* | watchlist, solgte | Over 50-dages gennemsnittet, positivt 1-måneds afkast og stærkere end ACWI over 3 måneder |
| *near 52w high* | alle | Mindre end 3 % fra 52-ugers høj (grænsen ligger i koden) |
| *no data* | alle | Ingen kurs |

De røde mærker kommer fra niveauet: *near review level* og *below review level*, *above highest analyst target* og, med ATR-stoppet, *near stop*, *stop hit*, *near target* og *stop breached* + dato (et brud inden for den seneste måned).

> **Tip:** *turning up* på watchlisten og *losing momentum* eller *below 200d* på beholdningerne er dem, `/market-brief` fremhæver. Brug dem som anledning til at kigge nærmere, ikke som handelssignaler.

## Gennemgangsniveau, stop og kursmål

Kun beholdninger får niveauer, og kun aktier samt sektor- og tema-ETF'er (med deres UCITS-tvillinger). Brede regionsfonde får ingen. Reglen er den samme som på tickerprofilen.

**Standard (`stops.mode: trend`):** niveauet er aktiens {{settings:stops.trend_sma}}-dages gennemsnit, og der er intet kursmål. En lukkekurs under det er en anledning til at se på positionen igen, ikke et salgssignal. I radarens test på tidligere momentumledere kostede faste stop og kursmål langt mere afkast, end de fjernede af risiko, mens det var billigere at lægge en del af pengene i en bred fond; se [Virker stop på momentumaktier?](laerebog/stop-og-storrelse#virker-stop-på-momentumaktier).

**Med `stops.mode: atr`** (reglen indtil oktober 2026):

- **Stop** = højeste lukkekurs siden første køb − k × ATR({{settings:stops.atr_days}}).
- **k** starter på {{settings:stops.k_base}}, og hvert signal flytter det: stærk momentum (score mindst {{settings:stops.strong_score}} og intakt trend) giver mere plads; brudt trend, tabt momentum, en kurs langt over 50-dages gennemsnittet, regimet og en kurs over analytikernes kursmål strammer. k holdes mellem {{settings:stops.k_min}} og {{settings:stops.k_max}}.
- **Kursmål** (kun med `stops.take_profit: true`) = det laveste af kursen + {{settings:stops.reward_risk}} × stopbredden og analytikernes middelkursmål (kræver mindst {{settings:stops.min_analysts}} analytikere).

Klik *why* i kolonnen *Flags* for at se niveauet og, med ATR-stoppet, k og hvert signal (▲ mere plads, ▼ strammere), og analytikernes konsensus, hvis den er brugt. Tærsklerne står i `config/settings.yaml` under `stops:`; se [Indstillinger](brugervejledning/indstillinger). Baggrunden står i [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

> **Bemærk:** Niveauerne er en mekanisk regel til eftertanke, ikke rådgivning.

## Hurtig import fra Yahoo Finance

Nederst på siden kan du folde *Import or re-import your portfolio from Yahoo Finance* ud. Eksportér din portefølje fra finance.yahoo.com (*Export*), og vælg filen med *Choose the exported CSV file*. Beholdninger, solgte positioner og watchlist-navne bliver importeret; en ny Yahoo-import erstatter den forrige, men dine watchlist-ændringer i appen bevares. Kurser for nye navne hentes ved næste opdatering.

Vil du indtaste handler selv, rette dem eller importere fra en bank, så brug linket *Add, correct or import trades on the Portfolio page →* og se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).
