# Sådan finder du rundt

Dette kapitel er en tur rundt i brugerfladen: topbjælken, menuen, søgningen, tickerlinks og tabellerne, som går igen på næsten alle sider. Til sidst forklares, hvordan du bruger selve guiden. Appens brugerflade er på engelsk; knapper og kolonner står derfor på engelsk i kursiv her.

## Topbjælken og menuen

Øverst på hver side er en topbjælke med:

- **Market Radar** (logoet) til venstre, som fører tilbage til forsiden.
- **Søgefeltet**, på alle sider undtagen forsiden, hvor søgefeltet i stedet står midt på siden.
- Linket ***Guide***, som åbner denne guide.

Under topbjælken er menuen i to rækker. Den øverste har tre grupper, og den nederste viser siderne i den gruppe, du er i:

| Gruppe | Sider |
|---|---|
| *Markets* | *Regime*, *Sector rotation*, *Themes & factors*, *Momentum*, *Discover*, *Positioning & cycle* |
| *Mine* | *Holdings & watchlist*, *Portfolio*, *Returns*, *Market views*, *Notebook* |
| *System* | *Data & coverage*, *Operations* |

Klikker du på en gruppe, kommer du tilbage til den side, du sidst så i gruppen (første gang til dens første side). Rækkefølgen følger arbejdsgangen: først markedet, så dig selv og dine noter, og til sidst data og drift. Står du på en tickerprofil, er *Markets* markeret. Til højre i grupperækken står *? Om denne side*. Et kort over siderne står i [Hvad er Market Radar?](brugervejledning/hvad-er-market-radar#et-kort-over-siderne).

### Forsiden
Forsiden har et stort søgefelt, det aktuelle regime (fx *Risk-on* med dato) og fliser til alle sider, ordnet i de samme tre grupper som menuen. Under fliserne står:

- *Recently viewed*: de tickers, du senest har åbnet.
- *Holdings* og *Watchlist*: genveje til dine egne navne.

### Sidehovedet
Hver markedsside begynder med en overskrift og en linje som "Data as of 13 Oct 2026 · built 2026-10-14 08:12 · benchmark MSCI ACWI". Datoen er den seneste handelsdag i data; "built" er, hvornår dashboardet blev regnet. Under den står ofte en kort forklaring af siden. Er data for gamle, kommer et gult banner med en opdateringsknap; se [Data og opdatering](brugervejledning/data-og-opdatering#advarsler-om-gamle-data).

Lange sider (fx *Sector rotation* og *Momentum*) har en række hurtiglinks under sidehovedet, som springer til hver gruppe eller region.

## Søgning

Søgefeltet slår op i Yahoo Finance, så du kan finde stort set alle aktier og ETF'er, også dem radaren ikke følger.

- **Tast `/`** hvor som helst (uden for et tekstfelt) for at hoppe til søgefeltet.
- Skriv et firmanavn, et fondsnavn eller et Yahoo-symbol. Resultaterne viser symbol, navn, børs og type. Navne, radaren allerede følger, er mærket *tracked* og står først.
- Brug piletasterne og Enter, eller klik. Trykker du Enter på fri tekst, åbnes teksten direkte som et symbol.

Nordiske og europæiske symboler har et suffiks for børsen, fx `NOVO-B.CO` (København), `RHM.DE` (Xetra) og `ASML.AS` (Amsterdam). En ticker, radaren ikke følger, hentes første gang du åbner den (omkring 10 sekunder). Profilsiden er beskrevet i [Tickerprofilen](brugervejledning/tickerprofil).

## Tickerlinks og hover-kort

Alle tickers i appen er links til deres profil. Holder du musen over et link et øjeblik, åbner et lille hover-kort med:

- navn, symbol, gruppe og type (aktie eller ETF)
- seneste kurs, dagens ændring og dato
- en sparkline over de seneste seks måneder
- afkast over 1 og 3 måneder, momentumscore eller rotationskvadrant
- en *Watch*-knap og *Open profile →*

Du kan bevæge musen ind i kortet og klikke på knapperne. Ved siden af linket står en lille markering, hvis navnet er dit: *held* for en beholdning og *watch* for et navn på din watchlist.

### Watchlist-stjernen
I tabellerne står en stjerne yderst til højre. ☆ sætter navnet på din watchlist, ★ tager det af igen. En udfyldt prik (●) betyder, at du ejer navnet; beholdninger kan ikke sættes på watchlist. Et navn på watchlist kommer med i den daglige opdatering og på siden [Holdings & watchlist](/me).

## Tabellerne

Næsten alle tabeller i appen fungerer ens. Over hver tabel ligger en værktøjslinje.

### Sortering
Klik på en kolonneoverskrift for at sortere. Tal sorteres første gang fra højeste til laveste (det sædvanlige spørgsmål er "hvem fører?"), tekst fra A til Å. Klik igen for at vende rækkefølgen. En pil viser, hvilken kolonne der er sorteret efter. **Manglende værdier står altid sidst**, uanset retning, så de aldrig blandes sammen med nul.

### Søgning og filtre
- **Search…** søger i de tekstkolonner, der giver mening (navn, ticker, branche, ISIN osv.).
- **Filterknapper:** hver filtrerbar kolonne har en knap med kolonnens navn og en lille pil. Der er tre slags filtre:
  - *Valg* (fx *Quadrant* eller *Industry*): sæt flueben ved de værdier, du vil se. Antallet af rækker med hver værdi står ved siden af.
  - *Ja/nej* (fx *Trend*): vælg *Any*, *✓ Yes* eller *✗ No*.
  - *Interval* (fx *Score* eller *3m*): skriv *Min* og/eller *Max* og klik *Apply*. Procentkolonner skrives i procent.
- Et aktivt filter vises på knappen (fx "Score: ≥ 80") med et × til at fjerne det. *Clear all* fjerner alle.
- Til højre står antallet af rækker, fx "Showing 12 of 20". Et intervalfilter udelader rækker uden data og siger hvor mange ("· 3 without data left out"), så du ved, hvad du ikke ser.

### Filtrene står i adressen
Sortering, søgning og filtre gemmes i sidens adresse (URL). Det betyder:

- En filtreret visning overlever, når du genindlæser siden.
- Browserens tilbage-knap fortryder det seneste filter.
- Du kan gemme en bestemt screening som bogmærke og åbne den igen senere.

> **Tip:** Tabeller, der hører sammen, deler én værktøjslinje. På *Momentum* gælder søgning, filtre og kolonner for alle regioner på én gang.

### Kolonner
Menuen *Columns* viser alle tabellens kolonner. Nogle er skjult fra start (fx de ekstra værdiansættelseskolonner og RS-Ratio); sæt flueben for at vise dem. Den første kolonne kan ikke skjules. Dit valg huskes i din browser, og *Reset* går tilbage til standard.

### Eksport
*Export CSV* henter de rækker, du ser, som en CSV-fil: med de synlige kolonner, i den sorterede rækkefølge og med dine filtre anvendt. Tallene eksporteres som rå værdier med punktum som decimaltegn og komma mellem felterne (fx `0.053` i stedet for "5,3 %"), så de er lette at regne videre på. Åbner dit regneark filen forkert, så brug dets importfunktion og vælg komma som skilletegn og punktum som decimaltegn.

### Farver i cellerne
- Afkastkolonner er svagt tonet grønt eller rødt efter fortegn og størrelse.
- Graderede tal (fx *Score*, *From 52w high*, P/E) er farvet efter, hvor tæt de er på en tærskel. Hold musen over for at se ordet og den nærmeste tærskel.
- Kolonnen *Signals* viser én prik pr. graderet aflæsning, så du hurtigt kan skimme en række. Sorterer du på den, kommer de mest bekymrende rækker først eller sidst.

## Forklaringer ved musen

Kolonneoverskrifter og fagudtryk med en **prikket understregning** forklarer sig selv: hold musen over (eller tab dig hen til dem med tastaturet), så kommer en kort forklaring. Det samme gælder farvede mærker som *Leading* eller *stale*. Esc lukker forklaringen.

Forklaringerne er korte. Den fulde baggrund står i lærebogen; se fx [Momentumeffekten](laerebog/momentumeffekten) eller [Rotationsgrafen (RRG)](laerebog/rrg).

## Guiden

Guiden, du læser nu, åbnes med linket *Guide* i topbjælken. Den består af to bøger:

- **Brugervejledning:** appen side for side, fra første start til drift og fejlfinding.
- **Lærebog:** teorien bag, fra afkast og statistik til momentum, rotation, regime, værdiansættelse, risiko og skat.

### Sidepanelet
Til venstre står begge bøger med deres dele og kapitler. Klik på et kapitel for at åbne det. Nederst i hvert kapitel er der links til forrige og næste kapitel, så du kan læse bøgerne fra ende til anden.

### På denne side
Til højre står *På denne side*: kapitlets overskrifter. Klik på en overskrift for at springe til den. Overskrifterne har deres egne adresser, så du kan linke direkte til et afsnit.

### Søgning i guiden
Guiden har sin egen søgning, der søger i begge bøger. Den finder afsnit, der indeholder alle de ord, du skriver, og viser kapitel, afsnit og et uddrag. Træffere i titler og overskrifter står først.

### Om denne side
På hver side i appen er der et link, *? Om denne side* yderst til højre i grupperækken, der åbner det kapitel i brugervejledningen, der handler om netop den side. På forsiden fører det hertil.

### Levende tal
Tærskler og vinduer i guiden (fx at regimet regner VIX under {{settings:regime.vix_calm}} som roligt, eller at momentumlisten viser top {{settings:momentum.top_n}}) læses direkte fra `config/settings.yaml`. Ændrer du en indstilling, følger teksten med.
