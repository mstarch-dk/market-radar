# Discover

Siden [Discover](/discover) kaster et bredere net end resten af radaren. Hvor *Momentum* rangerer radarens faste lister (ca. 700 aktier og ETF'er), scanner Discover flere tusinde nordiske og europæiske aktier, alle aktier i S&P 500 og alle UCITS-ETF'er på SKATs positivliste. Formålet er at finde navne, **før** de når momentumlisterne: små og mellemstore selskaber, der er begyndt at bevæge sig, nye toppe, trendvendinger og fonde, du ikke kendte.

Siden har to dele: et **heatmap** øverst og en **screener** (en filtrerbar tabel) nedenunder. De viser de samme navne og er koblet sammen.

> **Bemærk:** Small caps er mere støjende, og tyndt handlede navne kan springe voldsomt. Behandl hvert hit som en grund til at undersøge, ikke som et købssignal.

## Scanningen

Discover bygger på sin egen scanning, adskilt fra den daglige opdatering, så den daglige opdatering forbliver hurtig. Scanningen rører ikke radarens øvrige data, og intet fra den indgår i regimet, bredden eller momentumsiden.

- **Første gang** viser siden en forklaring og knappen *Run the first discovery scan*. Den første scanning slår omkring 3.500 navne op og tager et stykke tid.
- **Senere** starter du en ny scanning med *Scan again* ved siden af markedsvælgeren, eller med `uv run radar discover` i terminalen. Det tager nogle minutter.
- **Listen over navne** bygges igen cirka månedligt; kurserne hentes ved hver scanning. Svarer Yahoo ikke for et navn, beholder det sine gemte kurser, og loggen siger det.
- Er scanningen ældre end {{settings:coverage.max_age.discovery_prices}} dage, viser siden et banner, *This scan is N days old*, med *Scan again*.

Kør den cirka en gang om ugen. Se [Data og opdatering](brugervejledning/data-og-opdatering#discover-scanningen-er-separat).

## Markederne

Øverst vælger du marked. Tallet ved hvert marked er antallet af navne med en score:

| Marked | Indhold |
|---|---|
| *Nordic* | Aktier noteret i København, Stockholm, Oslo og Helsinki (primærnotering), over en mindste markedsværdi |
| *Europe* | Alle medlemmer af STOXX Europe 600 plus større selskaber på de øvrige europæiske hovedbørser |
| *US (S&P 500)* | Alle medlemmer af S&P 500, uanset størrelse, og ingen andre amerikanske aktier |
| *UCITS ETFs* | ETF'er fra SKATs positivliste, fundet på Yahoo via deres ISIN |

Medlemmerne af S&P 500 kommer fra beholdningen i iShares' S&P 500-ETF (CSPX), og deres sektor er indeksets GICS-sektor, oversat til Yahoos navne. Markedsværdien kommer fra Yahoos screener; mangler den, står størrelsen som ukendt.

> **Bemærk:** Amerikanske aktier kan ikke ligge på en aktiesparekonto, kun i frie midler. Et hit i *US (S&P 500)* er derfor et kandidatnavn til de frie midler, eller en grund til at lede efter en UCITS-ETF med samme tema.

Markedet for UCITS-ETF'er kræver, at positivlisten ligger i `imports/positivliste.xlsx`; se [Installation og første start](brugervejledning/installation#skats-positivliste). Findes en fond i flere andelsklasser eller på flere børser, vælges én, så den samme fond ikke tæller flere gange.

## Scoren og Δ score

*Score* er den samme momentumscore som på [Momentum](brugervejledning/momentum#momentumscoren): gennemsnittet af percentilerne for 12-1-måneds-, 6-måneds- og 3-månedsafkast. Den rangeres **inden for hvert marked**, så en nordisk small cap konkurrerer med nordiske navne og ikke med de største europæiske selskaber. Står en aktie alene i sit marked, har den ingen score, for der er ingen at sammenligne den med.

*Δ score* er ændringen i scoren over den seneste måned (21 handelsdage): scoren i dag minus scoren regnet på kurserne for en måned siden. En stor stigning betyder, at navnet klatrer i rangeringen, også selvom det endnu ikke er blandt de højeste. Det er ofte det mest interessante tal på siden.

## Heatmappet

Hvert felt er et navn, grupperet i blokke. Tre vælgere styrer, hvad du ser:

- **Colour:** hvad farven viser: *1 week*, *1 month* (standard), *3 months*, *6 months*, *Score* eller *Δ score (1m)*. Grøn er positiv, rød negativ (for *Score*: over eller under 50). Forklaringen ved siden af viser skalaen, og grå med teksten *no data* betyder manglende data.
- **Size:** hvad feltets størrelse følger: *√ market cap* (standard for aktier), *Market cap*, *√ traded value* (standard for ETF'er) eller *Equal*. Kvadratroden af markedsværdien gør, at små selskaber stadig er synlige ved siden af de største. Navne uden kendt størrelse tegnes i den mindste størrelse, og antallet står over kortet.
- **Group:** hvordan felterne grupperes: *Sector* (standard for aktier), *Country*, *Size* eller *Rotation vs ACWI*; for ETF'er *Category* (standard) eller *Rotation vs ACWI*.

Hold musen over et felt for at se score og Δ score, afkast, markedsværdi, omsætning og en lille kursgraf; et klik åbner tickerprofilen. Feltet og den tilsvarende række i tabellen fremhæves samtidig.

**Heatmappet viser de samme navne som tabellen nedenunder.** Filtrerer du tabellen, krymper kortet med. Det er den bedste måde at bruge det på: vælg en genvej eller et filter, og se, hvor hittene ligger.

Marked, farve, størrelse og gruppering står i adressen (`mkt`, `color`, `size`, `by`), så en visning kan gemmes som bogmærke. Skifter du marked, beholdes farven, mens filtre, størrelse og gruppering nulstilles, fordi de hører til det marked, du forlod.

> **Tip:** Heatmappet kræver en vis skærmbredde. På en smal skærm (fx en telefon) vises kun tabellen.

## Genvejene

Over heatmappet ligger færdige screeninger, der sætter tabellens filtre og sortering:

| Genvej | Hvad den finder |
|---|---|
| *Under the radar* | Navne radaren ikke følger, small eller mid cap, score mindst 80 og ikke tyndt handlede (kun aktier) |
| *Emerging* | Score steget mindst 20 point på en måned, med intakt optrend |
| *Breakouts* | Ny 52-ugers top på mindst 1,5 gange normal volumen |
| *Turnarounds* | Krydset over 200-dages snit inden for de seneste 20 handelsdage, med stigende 50-dages snit |
| *Leaders* | Score mindst 80 i sit marked |
| *All names* | Fjerner alle filtre |

Den aktive genvej er fremhævet, og dens beskrivelse står ved siden af. Du kan justere filtrene bagefter; så er ingen genvej længere fremhævet.

## Tabellen

For aktier har tabellen disse kolonner (nogle er skjult fra start og kan slås til under *Columns*):

| Kolonne | Indhold |
|---|---|
| *Name* | Navn og ticker |
| *Country*, *Sector*, *Industry* | Land, sektor og branche |
| *Size* | Størrelsesgruppe efter markedsværdi i DKK |
| *Mkt cap* | Markedsværdi i DKK |
| *Score*, *Δ score* | Momentumscore og ændringen over en måned |
| *P/E next yr* m.fl. | Værdiansættelse som på momentumsiden, sammenlignet med sektoren i samme marked |
| *1w*, *1m*, *3m*, *6m*, *12-1m* | Afkast |
| *From high* | Afstand til 52-ugers top |
| *Traded/day* | Median daglig omsætning i DKK over 20 handelsdage |
| *vs ACWI* | Rotationskvadrant mod ACWI |
| *Trend* | ✓ for intakt optrend (over 200-dages snit, 50 over 200) |
| *Flags* | Mærker, se nedenfor |

For ETF'er erstattes land, sektor og størrelse af *Category*, *Positive list* og *ISIN*, og værdiansættelsen er fondens P/E mod ACWI. Har du markedssyn, får tabellen også kolonnen *Views*.

### Størrelsesgrupper
| Gruppe | Markedsværdi |
|---|---|
| *large* | fra 50 mia. DKK |
| *mid* | fra 5 mia. DKK |
| *small* | under 5 mia. DKK |

Har Yahoo ingen markedsværdi, er størrelsen ukendt (–). Grænserne står under tabellen og ligger i `config/discovery.yaml`.

### Flagene
| Mærke | Betydning |
|---|---|
| *new to radar* | Navnet er ikke i radarens egne lister, dine beholdninger eller din watchlist |
| *52w high* | Ny 52-ugers lukketop, og volumen de seneste 20 dage er mindst 1,5 gange 120-dages gennemsnittet |
| *trend turn* | Krydset over 200-dages snit inden for de seneste 20 handelsdage, mens 50-dages snit stiger |
| *RS high* | Kursen divideret med ACWI (hver i sin egen valuta) har sat en ny 52-ugers top inden for de seneste 5 handelsdage |
| *thin* | Median daglig omsætning under 1 mio. DKK: brede spreads og store udsving på små ordrer |
| *check data* | En daglig kursbevægelse på over 60 % i det seneste års historik, ofte en datafejl (fx en split, der ikke er justeret) |
| *stale* | Ingen ny kurs i over en uge |

Tærsklerne ligger i `config/discovery.yaml`. *New to radar*, *52w high*, *Trend turn*, *RS high* og *Thin* findes også som skjulte ja/nej-kolonner, så du kan filtrere på dem.

> **Bemærk:** Et navn med *check data* bør du ikke stole på, før du har set kursgrafen. Et urealistisk spring i historikken forvrænger både afkast og score.

## Sådan bruger du siden

1. **Vælg marked**, og start med en genvej, fx *Emerging* eller *Under the radar*.
2. **Se på heatmappet**, grupperet efter sektor. Klumper hittene sig i én sektor, er det et tegn på en bredere bevægelse; sammenlign med [Sector rotation](/rotation).
3. **Sortér tabellen** efter *Δ score* eller *Score*, og fjern tyndt handlede navne med filteret *Thin* på *✗ No*.
4. **Åbn de interessante navne.** Tickerprofilen viser graf, regnskabsdato, analytikere og risiko.
5. **Sæt dem på watchlist (☆).** Så kommer de med i den daglige opdatering og på [Holdings & watchlist](/me), og de er ikke længere *new to radar*.

Momentum i små selskaber er stærkere, men også mere skrøbelig end i store. Læs [Momentumeffekten](laerebog/momentumeffekten) og [Radarens momentumscore](laerebog/momentumscore), før du lægger meget vægt på et enkelt hit.
