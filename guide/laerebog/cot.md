# Futurespositionering (CFTC COT)

## Intuition

Priser fortæller, hvad markedet har gjort. Positionering fortæller, hvem der står hvor. Hvis næsten alle hurtige spekulanter allerede har satset på, at olieprisen stiger, er der få købere tilbage, og mange, der skal sælge, hvis noget går galt. Markedet er *crowded*: en position, mange deler, og som kan vende hurtigt, når de alle vil ud ad den samme dør.

Den amerikanske tilsynsmyndighed for futuresmarkeder, Commodity Futures Trading Commission (CFTC), offentliggør hver uge, hvordan forskellige typer af handlende er positioneret i de vigtigste futureskontrakter. Rapporten hedder Commitments of Traders (COT). Den er gratis, har en lang historik og er et af de få direkte vinduer ind i, hvad professionelle investorer faktisk gør, i modsætning til hvad de siger.

COT-data bruges typisk på to måder:

- **Bekræftelse af en trend**: langsomme penge (pensionskasser, kapitalforvaltere) bygger positioner gradvist op, og deres retning følger ofte trenden.
- **Kontrær advarsel**: hurtige penge (hedgefonde, trendfølgende CTA'er) har det med at ligge mest ekstremt lige før en vending. En ekstrem position er ikke et timingsignal i sig selv, men den fortæller, hvilken vej en vending vil gøre mest ondt.

## Teori

### Rapporterne

CFTC indsamler positioner fra alle store handlende over en rapporteringsgrænse og offentliggør aggregater pr. kontrakt. Der findes flere rapporttyper:

| Rapport | Markeder | Grupper |
|---|---|---|
| Legacy | alle | commercial, non-commercial, non-reportable |
| Disaggregated | råvarer (energi, metaller, landbrug) | producer/merchant, swap dealers, managed money, other reportables |
| Traders in Financial Futures (TFF) | finansielle futures (aktieindeks, renter, valuta, VIX) | dealer/intermediary, asset manager/institutional, leveraged funds, other reportables |

De grupper, der er mest brugt i analyse:

- **Asset managers** (TFF): pensionskasser, forsikring, investeringsforeninger. Langsomme, ofte lange aktieindeks for at styre eksponering. Deres position afspejler strukturel allokering mere end kortsigtede synspunkter.
- **Leveraged funds** (TFF): hedgefonde og CTA'er i finansielle futures. Hurtige og ofte trendfølgende; deres positioner svinger meget.
- **Managed money** (disaggregated): registrerede råvarerådgivere (CTA'er) og puljer i råvarer. Den gruppe, der typisk omtales som "spekulanterne" i olie, guld og kobber.

Hver rapport findes i to varianter: *futures only* og *futures and options combined*, hvor optioner omregnes til futures-ækvivalenter via deres delta. De to kan ikke blandes.

### Tidspunkt

Positionerne opgøres om **tirsdagen** og offentliggøres om **fredagen** kl. 15.30 amerikansk østkysttid. Når du læser rapporten, er den altså tre dage gammel, og i en uge med store bevægelser kan billedet have ændret sig meget.

### Nettoposition i procent af open interest

Open interest (OI) er antallet af udestående kontrakter. Nettopositionen for en gruppe er dens lange minus dens korte kontrakter. For at kunne sammenligne over tid og mellem markeder normaliseres med OI:

$$
\text{net \% OI} = 100 \cdot \frac{\text{long} - \text{short}}{\text{OI}}
$$

Normaliseringen er vigtig: open interest vokser og falder over årene, så et absolut antal kontrakter fra 2020 kan ikke sammenlignes direkte med i dag.

### Hvornår er en position ekstrem?

Niveauet i sig selv siger lidt, fordi hver gruppe har sin egen normale position. Asset managers er næsten altid nettolange S&P 500-futures; leveraged funds er ofte nettokorte, fordi de bruger futures til at afdække lange aktieposter eller til basishandler. Derfor sammenligner man med gruppens egen historik, typisk som en percentil over et vindue på et til tre år. Det kaldes ofte et COT-indeks.

### Evidens

Evidensen for COT som signal er blandet. Wang (2003) fandt, at spekulanters positioner i flere futuresmarkeder havde en svag tendens til at forudsige fortsættelse, mens hedgeres positioner forudsagde det modsatte. Sanders, Boris og Manfredo (2004) fandt i energimarkederne, at positionerne følger afkastene mere, end de leder dem: spekulanterne køber, *efter* prisen er steget. De fleste studier er enige om, at nettopositioner ikke forudsiger ugentlige eller månedlige afkast pålideligt, men at ekstremer kan markere øget risiko for skarpe vendinger. Det er den brug, radaren lægger op til.

### Crowding

Når en gruppe er ekstremt positioneret, er to ting sande på én gang:

1. Gruppen har haft ret indtil nu (positionen er ofte bygget op i takt med en trend).
2. Der er få nye købere (eller sælgere) tilbage i gruppen, og hvis trenden knækker, skal mange lukke positioner samtidig.

Det giver en asymmetri: fortsættelsen er mindre sandsynlig, end trenden antyder, og vendingen er voldsommere. Et eksempel er kortpositioneringen i VIX-futures op til februar 2018, hvor en hurtig stigning i volatilitet tvang en masseafvikling.

## Sådan gør radaren

### Kilde og markeder

Radaren henter rapporterne fra CFTC's åbne API (`sources/external.py`): TFF for finansielle futures og den disaggregerede rapport for råvarer. Kun rækker med **futures only** bruges, så to baser aldrig blandes. Markederne står i `config/universe.yaml` under `external.cot`:

| Rapport | Marked | Grupper |
|---|---|---|
| TFF | S&P 500, Nasdaq-100, Russell 2000, US 10Y note, Euro FX, VIX | *Asset managers*, *Leveraged funds* |
| Disaggregated | Gold, WTI crude, Copper | *Managed money* |

Første gang et marked hentes, hentes fire års historik (fast i koden); derefter kun nye uger. Returnerer CFTC rækker uden de forventede kolonner, fejler opdateringen højlydt, og de gemte data bliver stående.

### Beregningerne

For hver kombination af marked og gruppe (`external.cot_table`):

- **Nettoposition**: $100 \cdot (\text{long} - \text{short}) / \text{OI}$, kolonnen *Net % of OI*.
- **4-ugersændring**: dagens nettoposition minus nettopositionen fire rapporter tidligere, i procentpoint, kolonnen *4w change*.
- **Percentil**: de seneste {{settings:positioning.lookback_weeks}} uger (`positioning.lookback_weeks`, omkring tre år) inklusive den seneste. Percentilen er andelen af ugerne i vinduet, hvor nettopositionen var *strengt* lavere end i dag, gange 100. Med mindst 52 uger (fast i koden) beregnes den; ellers vises markedet ikke. Kolonnen hedder *3y percentile*.
- **Flag**: percentil $\leq$ {{settings:positioning.extreme_pct}} giver *3y low*; percentil $\geq 100 -$ {{settings:positioning.extreme_pct|raw}} giver *3y high* (`positioning.extreme_pct`).

Fordi den seneste uge selv indgår i nævneren, kan percentilen aldrig blive præcis 100: med {{settings:positioning.lookback_weeks}} uger er maksimum $100 \cdot ({{settings:positioning.lookback_weeks|raw}} - 1)/{{settings:positioning.lookback_weeks|raw}}$.

Percentilen farves af måleren `gauges.cot_pct`, som er *sekventiel* og måler afstanden fra midten (50) i begge retninger: jo tættere på et ekstrem, jo mere orange eller rød, uanset om det er lang eller kort. Den bliver aldrig grøn; crowding er en risiko, ikke en mulighed. Ordene går fra *crowded short* over *normal* til *crowded long*.

Tabellen står under *Futures positioning (CFTC)* på [Positioning & cycle](/positioning); se også [brugervejledningen](brugervejledning/positionering). Data er forældede efter {{settings:coverage.max_age.cftc}} dage. COT-data stemmer ikke i regimeafstemningen.

> **Bemærk:** Et *3y low* betyder lavt i forhold til gruppens egne tre år, ikke nødvendigvis nettokort. Asset managers kan have et *3y low* og stadig være solidt nettolange S&P 500.

## Regneeksempel

> **Eksempel:** Leveraged funds i S&P 500-futures. Tallene er opfundne.

Tirsdagens opgørelse:

- Leveraged funds lange: 150.000 kontrakter
- Leveraged funds korte: 330.000 kontrakter
- Open interest i alt: 2.000.000 kontrakter

**Nettoposition:**

$$
\text{net \% OI} = 100 \cdot \frac{150000 - 330000}{2000000} = 100 \cdot \frac{-180000}{2000000} = -9.0\ \%
$$

**4-ugersændring.** For fire rapporter siden var nettopositionen $-5.5\ \%$:

$$
-9.0 - (-5.5) = -3.5 \text{ procentpoint}
$$

Gruppen har altså øget sin korte position.

**Percentil.** Antag et vindue på 156 uger (dagens medregnet, som standardindstillingen i skrivende stund). Heraf lå nettopositionen lavere end $-9.0\ \%$ i 8 uger:

$$
\text{percentil} = 100 \cdot \frac{8}{156} = 5.1
$$

Med standardindstillingen på {{settings:positioning.extreme_pct}} er 5,1 under grænsen, så rækken får flaget *3y low*, og måleren viser *crowded short*.

**Fortolkning.** Hurtige penge er mere korte end i 95 % af de seneste tre år. Hvis aktiemarkedet stiger, skal de købe tilbage, hvilket kan forstærke en stigning (en *short squeeze*). Det er ikke et signal om, at markedet *vil* stige, men et argument for, at risikoen ved et fald allerede er delvist afdækket, og at en opadgående overraskelse kan blive voldsom. Husk også, at leveraged funds' korte S&P 500-futures ofte er den ene ben af en afdækket handel, ikke en ren nedtursspekulation.

## Faldgruber og begrænsninger

- **Forsinkelse.** Data er fra tirsdag og offentliggøres fredag. I hurtige markeder kan positionerne have vendt, inden du ser dem.
- **Kategorierne er grove.** "Leveraged funds" rummer både trendfølgende CTA'er og relative-value-fonde, der er korte futures som afdækning af aktier eller obligationer. En stor kort position kan være en basishandel, ikke et synspunkt på retningen.
- **Kun futures.** Positioner i aktier, ETF'er, swaps og OTC-optioner ses ikke. En kapitalforvalter kan sagtens være lang via ETF'er og kort via futures.
- **Percentilen er relativ.** Vinduet på {{settings:positioning.lookback_weeks}} uger definerer, hvad der er "ekstremt". Et regimeskifte (fx nye regler eller en ny type deltager) kan flytte niveauet varigt.
- **Ekstremer kan vare.** Crowdede positioner kan blive mere crowdede i måneder, mens trenden fortsætter. Brug flaget som et risikomål, ikke som en udløser.
- **Kun amerikanske kontrakter.** Euro FX er det eneste direkte europæiske mål; danske og europæiske aktieindeks er ikke med.
- **Delvis rangering.** Fordi der kræves 52 uger, vises et nyt marked først efter et år; percentilen er baseret på færre end {{settings:positioning.lookback_weeks}} uger, indtil historikken er lang nok.

## Videre læsning

- Commodity Futures Trading Commission: "Commitments of Traders: Explanatory Notes" og beskrivelsen af TFF- og Disaggregated-rapporterne, https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- Changyun Wang: "The Behavior and Performance of Major Types of Futures Traders", *Journal of Futures Markets* 23(1), 2003.
- Dwight R. Sanders, Keith Boris og Mark Manfredo: "Hedgers, Funds, and Small Speculators in the Energy Futures Markets: An Analysis of the CFTC's Commitments of Traders Reports", *Energy Economics* 26(3), 2004.
- Stephen Briese: *The Commitments of Traders Bible*, Wiley, 2008.
