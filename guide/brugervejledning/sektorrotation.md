# Sektorrotation

Siden [Sector rotation](/rotation) viser, hvor pengene i aktiemarkedet flytter hen: hvilke sektorer og regioner der vinder frem mod verdensindekset, og hvilke der mister terræn. Det er andet trin i det ugentlige overblik, efter regimet og før de enkelte aktier.

Siden er delt i grupper: *US sectors*, *Europe sectors (STOXX 600)* og *Regions & countries*. Hurtiglinksene under sidehovedet springer til hver gruppe. Hver gruppe har en rotationsgraf (RRG) og en tabel, som er koblet sammen. Tema- og faktor-ETF'er har deres egen side; se [Temaer og faktorer](brugervejledning/temaer-og-faktorer).

Teorien bag står i [Relativ styrke](laerebog/relativ-styrke), [Rotationsgrafen (RRG)](laerebog/rrg) og [Sektorer, temaer, faktorer og konjunkturcyklussen](laerebog/rotation-og-cyklus).

## Rotationsgrafen

Hver ETF er en prik med en hale. Grafen har to akser:

- **x-aksen, RS-Ratio (relative trend):** hvor stærk ETF'ens relative trend mod ACWI er. Over 100 betyder, at den klarer sig bedre end sin egen nylige norm mod ACWI.
- **y-aksen, RS-Momentum (acceleration):** om den relative trend tager til eller aftager. Over 100 betyder, at den relative styrke vokser.

Begge akser er centreret om 100, og de deler grafen i fire kvadranter:

| Kvadrant | RS-Ratio | RS-Momentum | Betydning |
|---|---|---|---|
| *Leading* (fører) | over 100 | over 100 | Stærk og stadig stærkere |
| *Weakening* (svækkes) | over 100 | under 100 | Stærk, men farten aftager |
| *Lagging* (halter) | under 100 | under 100 | Svag og stadig svagere |
| *Improving* (forbedres) | under 100 | over 100 | Svag, men på vej op |

Rotation løber typisk **med uret**: *Improving* → *Leading* → *Weakening* → *Lagging* → *Improving*. Navne, der bevæger sig fra *Improving* ind i *Leading*, er klassiske tidlige momentumkandidater. Navne, der går fra *Leading* til *Weakening*, er værd at holde øje med, hvis du ejer dem.

### Data og hale
Grafen bygger på **ugedata** (fredagslukkekurser), let udglattet. RS-Ratio normaliseres over et vindue på {{settings:rotation.window}} uger, og halen viser de seneste {{settings:rotation.tail}} uger; prikken er den seneste uge. Grafens titel siger det samme, fx "US sectors vs ACWI – last {{settings:rotation.tail}} weeks". Fordi det er ugedata, ændrer grafen sig ikke meget fra dag til dag.

Halens form fortæller mere end prikken alene:

- En **lang hale** betyder store relative bevægelser; en kort hale, at ETF'en ligger tæt på indekset.
- En hale, der **krummer**, viser et skift i gang, fx en sektor, der stadig er i *Lagging*, men hvis hale peger op mod *Improving*.
- Prikker **tæt på midten** (100, 100) er tæt på at skifte kvadrant; her kan små bevægelser flytte dem.

### Sådan bruger du grafen
- Hold musen over en prik for at se navn, kvadrant, ugedato, RS-Ratio, RS-Momentum og det relative afkast over 1 og 3 måneder. De andre haler dæmpes, og den tilsvarende række i tabellen fremhæves.
- Klik på en prik for at åbne ETF'ens profil.
- Knapperne *Labels* og *Tails* slår navne og haler til og fra, når grafen bliver rodet.
- **Tabellens filtre bestemmer, hvilke haler grafen viser.** Filtrer fx *Quadrant* til *Improving* og *Leading*, så viser grafen kun dem.

## Hjemmemarkedet for europæiske sektorer

Europæiske sektorer måles to gange. Den første graf viser dem mod ACWI som alle andre. Den anden viser dem mod deres **hjemmemarked**, STOXX 600 (titlen er fx "Europe sectors (STOXX 600) vs STOXX 600 – last {{settings:rotation.tail}} weeks").

Det skelner mellem to forskellige historier:

- En europæisk sektor kan ligge i *Leading* mod ACWI, blot fordi hele Europa klarer sig godt mod verden. Mod STOXX 600 kan den være helt gennemsnitlig.
- Omvendt kan en sektor lede inden for Europa, selvom Europa som helhed halter efter verden.

Tabellen har en ekstra kolonne, *vs home mkt*, med kvadranten mod STOXX 600. Er en sektor *Leading* i begge kolonner, er styrken både regional og sektorspecifik.

## Tabellen

| Kolonne | Indhold |
|---|---|
| *Name* | ETF'ens navn og ticker (link med hover-kort) |
| *#* | Rang i gruppen (1 = stærkest) |
| *Δ rank* | Ændring i rang siden et tidligere øjebliksbillede |
| *Quadrant* | Kvadranten mod ACWI |
| *vs home mkt* | Kvadranten mod hjemmemarkedet (kun europæiske sektorer) |
| *Rel 1m*, *Rel 3m*, *Rel 6m* | Afkast minus ACWI's afkast over 1, 3 og 6 måneder, i procentpoint |
| *Abs 3m* | Det almindelige afkast over 3 måneder, ikke relativt |
| *>200d* | ✓ når kursen er over sit 200-dages snit |
| *P/E* | Fondens P/E fra Yahoo, farvet i forhold til ACWI's P/E |
| *Signals* | Prikker for RS-Ratio og RS-Momentum, farvet efter styrke |

Skjulte kolonner, som du kan slå til under *Columns*: *vs ACWI* (fondens P/E divideret med ACWI's), *P/E pct* (P/E i forhold til fondens egen historik), *RS-Ratio* og *RS-Mom* (grafens koordinater som tal).

### Rangering
Rangen *#* bygger på en sammensat relativ styrke, der vægter 3 og 6 måneder tungest:

$$
\text{RS-score} = 0.2 \cdot \text{Rel 1m} + 0.4 \cdot \text{Rel 3m} + 0.4 \cdot \text{Rel 6m}
$$

Vægtene ligger fast i koden. Rangen og kvadranten måler forskellige ting: rangen siger, hvem der har klaret sig bedst over de seneste måneder; kvadranten siger, hvordan den relative trend ser ud lige nu, og om den accelererer. En sektor med høj rang i *Weakening* har haft en god periode, men farten er ved at gå af.

### Ændring i rang
*Δ rank* sammenligner med det seneste øjebliksbillede, der er mindst {{settings:snapshot_min_gap_days}} dage gammelt. Datoen står i sidehovedet ("Rank change is compared with the snapshot from …"). ▲3 betyder rykket tre pladser op, ▼2 to pladser ned, – uændret, og *new* betyder, at ETF'en ikke var med i det tidligere øjebliksbillede. Er der endnu intet tidligere øjebliksbillede, står det i sidehovedet.

### Filtre
*Quadrant* (og *vs home mkt*) filtreres ved at vælge kvadranter, *Rel 3m* med et interval og *>200d* med ja/nej. Filtrene står i adressen, så en visning kan gemmes som bogmærke; se [Sådan finder du rundt](brugervejledning/navigation#tabellerne).

## Sådan bruger du siden

En typisk ugentlig gennemgang:

1. **Se efter skift.** Hvilke sektorer har bevæget sig fra *Improving* til *Leading*, eller fra *Leading* til *Weakening*? Haler, der krydser en akse, er de interessante.
2. **Tjek bekræftelsen.** Er *Rel 3m* og *Rel 6m* positive, og er *>200d* ✓? En sektor i *Leading* under sit 200-dages snit er i en svag absolut trend, selvom den slår ACWI.
3. **Sammenlign med regimet.** I et *Risk-on*-regime fører typisk cykliske sektorer (teknologi, industri, finans); i *Risk-off* defensive (forsyning, sundhed, basisforbrug). Afviger rotationen fra regimet, er det værd at forstå hvorfor.
4. **Gå fra sektor til navne.** Fører en sektor, så se på [Momentum](/momentum), om de stærkeste aktier klumper sig i samme branche.

> **Tip:** Læs grafen med valutaen i baghovedet. Afkast og relativ styrke regnes i hver ETF's handelsvaluta, og ACWI handles i USD. Regionerne er amerikansk noterede ETF'er i USD, så en regions valuta mod dollaren er en del af dens relative styrke. De europæiske sektor-ETF'er handles i EUR, så en stigende euro får dem til at se stærkere ud mod ACWI. Grafen mod STOXX 600 har ikke det problem.

> **Bemærk:** En sektor i *Leading* er ikke en købsanbefaling. Rotation er ofte hurtigere end man tror, og en hale kan vende på få uger. Brug grafen til at vælge, hvor du leder, ikke hvad du køber.
