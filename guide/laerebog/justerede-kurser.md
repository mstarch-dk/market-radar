# Justerede kurser, udbytter og valuta

En kursgraf ser ud til at være det mest objektive tal i finansverdenen. Men den kurs, der handles på børsen, er ikke nødvendigvis det rigtige grundlag for at måle afkast. Udbytter, aktiesplit og valuta ændrer alle forholdet mellem kurs og formue. Dette kapitel forklarer, hvordan man korrigerer for dem, og hvordan radaren gør det.

## Intuition

Forestil dig en aktie, der koster 100 kr. dagen før den udbetaler 2 kr. i udbytte. Næste morgen handler den til 98 kr. Har du tabt 2 %? Nej. Du har 98 kr. i aktien og 2 kr. på kontoen. Men en graf over den handlede kurs viser et fald.

Det samme sker ved et aktiesplit. Deler et selskab hver aktie i fire, falder kursen fra 400 til 100 kr. på en dag, men du ejer fire gange så mange aktier. Uden korrektion ville et split ligne et krak på 75 %.

Løsningen er en *justeret kurs*: en kursserie, hvor alle historiske kurser er omregnet, så forholdet mellem to datoer svarer til det afkast, en ejer faktisk fik, med udbyttet geninvesteret. På den måde bliver afkast beregnet på justerede kurser til totalafkast.

Den sidste korrektion er valuta. En dansk investor, der ejer en amerikansk aktie, får afkastet i dollar *og* ændringen i dollarkursen. Stiger aktien 10 % i dollar, mens dollaren falder 5 % over for kronen, er gevinsten i kroner kun omkring 4,5 %.

## Teori

### Handlet kurs og justeret kurs

Lad $C_t$ være den handlede lukkekurs og $D_t$ et udbytte, der går ex på dag $t$. Den udbyttejusterede kurs $A_s$ for alle dage *før* ex-dagen ganges med en faktor

$$
f = 1 - \frac{D_t}{C_{t-1}}
$$

hvor $C_{t-1}$ er lukkekursen dagen før ex-dagen. Kurser fra ex-dagen og frem ændres ikke. Så gælder

$$
\frac{A_t}{A_{t-1}} = \frac{C_t}{f \cdot C_{t-1}} = \frac{C_t}{C_{t-1} - D_t}
$$

Det er præcis afkastet for en investor, der geninvesterer udbyttet til lukkekursen dagen før (en god tilnærmelse til at geninvestere på ex-dagen). Hvert nyt udbytte ganger hele den tidligere historie med en ny faktor, så de justerede kurser ændrer sig bagud i tid, hver gang der kommer et udbytte. Det er den vigtigste praktiske egenskab ved justerede kurser: *de er ikke faste tal*. Kun forholdet mellem dem er meningsfuldt.

Et split med forholdet $k$ til 1 justeres ved at dividere alle tidligere kurser med $k$ (og gange volumen med $k$). Det er den samme idé: forholdet mellem to datoer skal afspejle ejerens værdiudvikling.

Denne metode bruges af blandt andre CRSP og Yahoo Finance. Yahoo leverer to serier:

- **Close**: den handlede lukkekurs, korrigeret for split, men *ikke* for udbytter.
- **Adj Close**: korrigeret for både split og udbytter.

### Totalafkastindeks

Indeksudbydere offentliggør typisk tre varianter af samme indeks:

| Variant | Udbytter | Typisk brug |
|---|---|---|
| Kursindeks (*price*) | ikke medregnet | nyheder, grafer |
| Brutto totalafkast (*gross*) | geninvesteret før skat | teoretisk maksimum |
| Netto totalafkast (*net*) | geninvesteret efter kildeskat | benchmark for fonde |

MSCI's netto-indeks fratrækker kildeskat med en sats for udenlandske investorer uden dobbeltbeskatningsaftale. De fleste aktiefonde måles mod netto-varianten, fordi fonden selv betaler kildeskat. En ETF's kurs er i sig selv et slags totalafkast efter omkostninger: fondens formue vokser med udbytterne (akkumulerende fond) eller udlodder dem (udloddende fond, hvor den justerede kurs så lægger dem tilbage).

### Re-basering

Ordet *re-basering* bruges om to beslægtede ting:

1. **Når udbyderen re-baserer historikken.** Et nyt udbytte eller split ændrer alle tidligere justerede kurser. Har man gemt de gamle tal og henter nye, passer de to dele ikke sammen. Man kan ikke klistre en serie på den gamle basis sammen med en på den nye uden et kunstigt spring.
2. **Når man selv re-baserer for at sammenligne.** To serier sættes til 100 på samme startdato: $I_t = 100 \cdot P_t / P_{t_0}$. Så kan de tegnes i samme graf, og forskellen mellem kurverne er forskellen i afkast siden start.

### Valuta

Med $S_t$ som prisen i DKK for én enhed udenlandsk valuta er kursen i DKK $P^{\text{DKK}}_t = P_t \cdot S_t$, og afkastet bliver

$$
1 + R^{\text{DKK}} = (1 + R^{\text{lokal}})(1 + R^{\text{valuta}})
$$

eller tilnærmet $R^{\text{DKK}} \approx R^{\text{lokal}} + R^{\text{valuta}}$ for små tal. Valutabidraget kan være stort over en kortere periode. Da kronen er bundet til euroen i ERM II, er valutarisikoen på euroaktiver lille, mens dollar, pund, svenske kroner og yen svinger frit over for kronen.

### Pence og pund

London-noterede aktier handles ofte i *pence* (GBp eller GBX), ikke pund (GBP). 100 pence er et pund. Yahoo angiver valutaen som `GBp` med lille p. En aktie til 2.500 GBp koster altså 25 pund. Det er en klassisk fejlkilde: en købskurs indtastet i pund mod en kursserie i pence ser ud som et tab på 99 %, eller omvendt en gevinst på 9.900 %.

## Sådan gør radaren

### Justerede high, low og close

Radaren henter daglige data fra Yahoo uden automatisk justering og laver justeringen selv i `ingest.py`:

$$
\text{faktor}_t = \frac{\text{Adj Close}_t}{\text{Close}_t}
$$

Kolonnerne `high` og `low` ganges med faktoren, `close` er Adj Close, og den handlede lukkekurs gemmes som `raw_close`. Bemærk, at `raw_close` er Yahoos *Close*, altså korrigeret for split men ikke for udbytter. Den bruges, hvor det er den handlede kurs, der tæller:

- til at skalere dine handler, så et køb før en ex-dag får sit udbytte med (se nedenfor),
- til handlet værdi (`raw_close × volume`) i [Discover](/discover),
- til at omregne analytikernes kursmål til radarens prisenheder.

Alle momentum-, trend- og rotationsberegninger bruger de justerede kurser, så afkastene er totalafkast med bruttoudbytte (Yahoo trækker ikke kildeskat).

### Inkrementel opdatering og fuld genhentning

Hver `radar update` henter kun det nye:

- En ny ticker får {{settings:history_years}} års historik (`history_years` i `settings.yaml`).
- Kendte tickers hentes fra den tidligste "seneste dato" blandt dem minus 7 dage. Overlappet fanger sene rettelser fra Yahoo.
- For hver ticker sammenlignes den *tidligste* fælles dato i overlappet mellem den gemte og den nye justerede lukkekurs. Afviger de relativt mere end $10^{-5}$, har Yahoo re-baseret historikken (et nyt udbytte eller split), og tickeren hentes **helt forfra** og erstatter den gemte serie. To justeringsbaser blandes aldrig.

Tærsklen $10^{-5}$ og de 7 dages overlap står i koden (`RESCALE_TOL` og `OVERLAP_DAYS`). Den tidligste fælles dato bruges, fordi sene rettelser typisk rammer de nyeste dage, mens en re-basering flytter hele historikken.

### Huller og helligdage

Til beregninger stiller `ingest.wide()` kurserne op i en matrix med én række pr. dato og én kolonne pr. ticker. Datoerne er foreningsmængden af alle tickers' handelsdage, inklusive valutakurser, så i praksis alle hverdage. Mangler en ticker en kurs (en lukket børs), fyldes hullet med seneste kurs, **højst 5 rækker** i træk. Længere huller forbliver tomme. Det er rigtigt for afkastvinduer: en helligdag er en dag uden kursændring. Men alt, der vises som en enkelt handelsdag (seneste kurs, dagsændring, grafen på tickerprofilen), bruger tickerens egne bars, så en manglende Yahoo-dag ses som et hul, ikke som en flad dag.

### Omregning til DKK

Omregning sker med Yahoos valutakryds mod DKK (`fxrates.fx_to_dkk`): `USDDKK=X`, `EURDKK=X`, `GBPDKK=X`, `SEKDKK=X`, `NOKDKK=X`, `CHFDKK=X`, `PLNDKK=X`, `JPYDKK=X`, `HKDDKK=X` og `CADDKK=X`. Yahoo har ingen kurs mellem DKK og koreanske won eller taiwanske dollar, så de regnes om via dollar: `USDDKK=X` divideret med `USDKRW=X` eller `USDTWD=X`. Valutakursen fremskrives over huller. For pence-noterede aktier (`GBp`) bruges `GBPDKK=X` ganget med 0,01, så faktoren er "DKK pr. kursenhed". DKK-noterede aktier får faktor 1. En valuta uden et kryds (fx CNY) giver intet DKK-beløb: hellere et manglende tal end et forkert.

Hvor bruges DKK, og hvor ikke?

| Beregning | Valuta |
|---|---|
| Momentum (`r1m`, `r3m`, `r6m`, `r12_1`), trend, tekniske indikatorer | noteringsvalutaen |
| Rotation og `rel_r*` mod ACWI | noteringsvalutaen; ACWI er den USA-noterede ETF i USD |
| Dine beholdninger: afkast siden køb, skygge-ACWI | DKK |
| Porteføljer over tid (TWR, MWR) | DKK |
| Risikostatistik (beta, volatilitet) | DKK, ugentlige afkast |

### Udbytter i dine beholdninger

Da radaren regner med justerede kurser, er udbytter allerede med. Men et køb foretaget til den handlede kurs skal omregnes til samme basis. Hvert køb skaleres derfor med forholdet mellem justeret og handlet kurs på handelsdagen: antal aktier "i justerede termer" er $q / f$, hvor $f = A/C$ på handelsdagen. En aktie købt før en ex-dag får dermed udbyttet med; en aktie købt efter gør ikke. Med standardpolitikken `reinvested` tælles DIVIDEND-rækker i porteføljen derfor ikke med i afkastet, for så ville udbyttet tælle to gange. Se [Afkast over tid](brugervejledning/afkast).

### Advarsler om enheder

Radaren markerer et køb, hvis afkastet siden køb ligger uden for −95 % til +2.000 % (*check purchase price units*), fordi det næsten altid er en pence/pund-forveksling. Editoren og importen advarer også, når en pris er omkring 100 gange forkert. Grænserne står i koden.

## Regneeksempel

### Udbyttejustering

En aktie lukker på 100 kr. dagen før ex-dag. Udbyttet er 2 kr. På ex-dagen lukker den på 98, og en måned senere på 105.

- Faktor for alle kurser før ex-dagen: $f = 1 - 2/100 = 0.98$. Den justerede kurs dagen før bliver $100 \cdot 0.98 = 98$.
- Kursafkast: 105/100 − 1 = 5,0 %.
- Totalafkast på justerede kurser: 105/98 − 1 = 7,14 %.
- Kontrol: geninvester 2 kr. til 98 kr.: 1 + 2/98 = 1,020408 aktier. Værdi: 1,020408 · 105 = 107,14 kr., altså 7,14 %. Samme tal.

### Split

En aktie splittes 4:1. Dagen før lukker den på 400, dagen efter på 102. Uden justering: −74,5 %. Med justering divideres 400 med 4: afkastet er 102/100 − 1 = +2,0 %.

### Opdagelse af re-basering

Radaren har gemt en justeret lukkekurs på 98,000 for den 1. oktober. Den 14. oktober går aktien ex med et udbytte på 1 % af kursen, og Yahoo ganger hele historikken med 0,99. Næste opdatering henter fra den 7. oktober (seneste gemte dato minus 7 dage) og ser 97,020 for den tidligste overlappende dag. Relativ ændring: 97,020/98,000 − 1 = −1,0 %, langt over $10^{-5}$. Tickeren hentes helt forfra.

### Valuta

En amerikansk aktie stiger fra 200 til 220 dollar (+10 %). Samtidig falder USDDKK fra 6,80 til 6,46 (−5 %).

$$
1 + R^{\text{DKK}} = 1.10 \cdot 0.95 = 1.045
$$

Afkastet i DKK er 4,5 %. I DKK: 200 · 6,80 = 1.360 kr. bliver til 220 · 6,46 = 1.421,20 kr., altså +4,5 %.

### Pence

En London-aktie står i 2.500 GBp, og GBPDKK er 8,60. Faktoren er 8,60 · 0,01 = 0,086 DKK pr. pence, og aktien koster 2.500 · 0,086 = 215 kr. Indtastes købskursen som 25 (pund) mod en serie i pence, ser værdien ud til at være 100 gange købsprisen.

## Faldgruber og begrænsninger

- **Justerede kurser ændrer sig bagud.** Et gammelt skærmbillede eller en gemt kurs passer ikke længere efter næste udbytte. Sammenlign aldrig en justeret kurs med en handlet kurs fra en kontoudskrift.
- **Bruttoudbytte.** Yahoos justering medregner hele udbyttet. En dansk investor betaler typisk udenlandsk kildeskat, og hvis den ikke kan modregnes fuldt, er dit faktiske afkast lidt lavere. Se [Dansk skat for investorer](laerebog/skat).
- **Yahoo er uofficielle data** uden kvalitetsgaranti. Fejl i udbyttedatoer eller split slår direkte igennem i de justerede kurser. Radarens genhentning beskytter mod blandede baser, ikke mod fejl hos kilden.
- **Lokal valuta i momentum.** En europæisk og en amerikansk aktie rangeres på hver sit afkast i egen valuta. Det er fair inden for en region, men en svag dollar kan gøre en amerikansk vinder mindre attraktiv i DKK.
- **Fremskrivning maskerer huller.** Op til 5 dage uden kurs ser ud som flade dage i afkastvinduerne. Et længere stop (suspension, afnotering) giver manglende tal.
- **Pence og pund** er den hyppigste enhedsfejl i manuelle handler. Tjek valutaen på Yahoo, før du indtaster.

## Videre læsning

- Center for Research in Security Prices (CRSP): *CRSP US Stock and Index Databases: Data Descriptions Guide* (afsnittet om kursfaktorer og totalafkast).
- MSCI: *MSCI Index Calculation Methodology* (pris-, brutto- og netto-totalafkastindeks), MSCI Inc., løbende opdateret.
- S&P Dow Jones Indices: *Index Mathematics Methodology*, løbende opdateret.
- Elroy Dimson, Paul Marsh og Mike Staunton: *Triumph of the Optimists: 101 Years of Global Investment Returns*, Princeton University Press, 2002 (om udbytternes andel af det lange afkast).
