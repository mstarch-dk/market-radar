# Kobber, guld og olie

## Intuition

Råvarer er økonomiens fysiske side. Kobber bruges i alt fra elnet og huse til biler og elektronik, så efterspørgslen følger den globale industriproduktion. Den har givet metallet tilnavnet "Dr. Copper": metallet med en ph.d. i økonomi. Guld bruges næsten ikke til noget produktivt; det købes som værdiopbevaring og forsikring, når investorerne frygter inflation, finansiel uro eller politisk kaos.

Sætter du de to over for hinanden, får du et simpelt mål for markedets humør: stiger kobber mere end guld, satser markedet på vækst. Stiger guld mere end kobber, søger markedet sikkerhed. Kobber/guld-ratioen er et vækst-mod-frygt-barometer, der handles døgnet rundt på tværs af verden.

Olie er anderledes. Lidt stigende olie er et tegn på efterspørgsel og vækst. Men en *kraftig* stigning er en skat på forbrugere og virksomheder: den presser inflationen op, æder realindkomsten og marginerne, og den har gået forud for mange recessioner. Derfor ser radaren kun efter olieshock, ikke efter almindelige stigninger.

## Teori

### Kobber som vækstindikator

Kobberprisen bestemmes af global industriefterspørgsel, især fra Kina, der bruger omkring halvdelen af verdens raffinerede kobber, og af udbuddet fra relativt få store miner (Chile, Peru, DR Congo). Fordi udbuddet reagerer langsomt (en ny mine tager 10–20 år), slår ændringer i efterspørgslen hurtigt igennem i prisen. Det gør kobber til en tidlig og global vækstindikator.

I de seneste år har kobber desuden fået en strukturel efterspørgselshistorie: elektrificering, elnet, elbiler og datacentre bruger meget kobber. Det betyder, at prisen også kan stige af grunde, der ikke har med konjunkturen at gøre.

### Guld som frygtindikator

Guld giver intet afkast i form af renter eller udbytte. Alternativomkostningen ved at holde guld er derfor den reale rente: når realrenten falder, bliver guld relativt mere attraktivt, og omvendt (Erb og Harvey, 2013). Ud over det efterspørges guld i perioder med finansiel stress, geopolitisk uro og tvivl om centralbankernes troværdighed. Siden 2022 har centralbankers opkøb, især i emerging markets, været en stor og vedvarende ekstra efterspørgsel, der har svækket den klassiske sammenhæng med realrenten.

### Kobber/guld-ratioen

Ratioen er

$$
CG_t = \frac{P_{\text{kobber}}(t)}{P_{\text{guld}}(t)}
$$

og ændringen over en periode er, ligesom ved [relativ styrke](laerebog/relativ-styrke):

$$
\frac{CG_t}{CG_{t-n}} - 1 = \frac{1 + r_{\text{kobber}}}{1 + r_{\text{guld}}} - 1
$$

En stigende ratio er et pro-cyklisk signal: forventninger om højere vækst og ofte højere renter. Ratioen har historisk fulgt den amerikanske 10-årige rente tæt, hvilket blev populariseret af obligationsforvalteren Jeffrey Gundlach. Det er ingen naturlov, men en konsekvens af, at begge reagerer på vækst- og inflationsforventninger.

Ratioens *niveau* er uden betydning (det afhænger af enhederne: kobber i dollar pr. pund, guld i dollar pr. ounce). Det er ændringen, der tæller.

### Olieshock

Hamilton (2009) dokumenterede, at de fleste amerikanske recessioner efter Anden Verdenskrig blev indledt af en kraftig oliepris-stigning, og at det især er stigninger til nye højder, der skader. Mekanismen: forbrugerne bruger mere på energi og mindre på alt andet, virksomhedernes marginer presses, og centralbanken kan blive tvunget til at stramme for at holde inflationen nede.

Men ikke alle prisstigninger er ens. Kilian (2009) skelnede mellem:

- **Udbudschok** (krig, OPEC-beslutninger, sanktioner): prisen stiger, fordi der er mindre olie. Det er klart negativt for økonomien.
- **Efterspørgselschok** (global vækst): prisen stiger, fordi økonomien er stærk. Det er i sig selv et tegn på vækst, og aktier kan stige samtidig.
- **Forsigtighedsefterspørgsel** (frygt for fremtidig mangel): lagre opbygges, og prisen stiger hurtigt.

En stor stigning over kort tid er oftest et udbudschok eller et frygtdrevet hop, og det er den situation, der er farligst for aktiemarkedet. Eksempler er 1973, 1979, 1990 (Kuwait) og 2022 (Ukraine).

### Olie og aktier: en skiftende sammenhæng

Sammenhængen mellem olie og aktier er ikke fast. I 1970'erne og omkring 1990 var den klart negativ: olieprisen steg på grund af udbudschok, og aktierne faldt. Efter finanskrisen i 2008 blev korrelationen i lange perioder positiv: både olie og aktier blev drevet af den samme vækstforventning, og et oliefald blev læst som et tegn på svag efterspørgsel. I 2022 vendte den igen: et udbudschok sendte olien op, inflationen steg, centralbankerne strammede, og aktierne faldt.

Det betyder, at en almindelig ændring i olieprisen er tvetydig for aktiemarkedet. Det er kun i halerne, at retningen er nogenlunde klar: en meget hurtig og stor stigning har oftere været et problem end et tegn på sundhed, uanset årsagen, fordi den rammer forbrugernes købekraft og inflationsforventningerne på kort tid.

### Hvorfor 3 måneder?

Både kobber/guld og olie måles over cirka 3 måneder (63 handelsdage). Horisonten er lang nok til at filtrere daglig støj og korte spekulative hop fra, og kort nok til at fange skift, der betyder noget for radarens horisont på 1–6 måneder. Den matcher også de øvrige rækker i afstemningen (renteshock, dollar, RSP/SPY), så rækkerne beskriver samme tidsrum.

## Sådan gør radaren

Radaren bruger de kontinuerlige frontmånedsfutures fra Yahoo: kobber (`HG=F`), guld (`GC=F`) og WTI-råolie (`CL=F`), daglige lukkekurser (`macro.yahoo` i `config/universe.yaml`). To rækker i afstemningen (`src/radar/signals/regime.py`):

**Copper/gold ratio:** ændringen i ratioen kobber/guld over 63 handelsdage (cirka 3 måneder).

- **risk-on**, hvis den er over +{{settings:regime.copper_gold_band|pct}} (`regime.copper_gold_band`),
- **risk-off**, hvis den er under −{{settings:regime.copper_gold_band|pct}},
- **neutral** ellers.

**Oil (WTI):** ændringen i olieprisen over 63 handelsdage.

- **risk-off**, hvis den er over +{{settings:regime.oil_shock|pct}} (`regime.oil_shock`): et olieshock.
- **neutral** ellers.

Olierækken kan **kun stemme risk-off**. En faldende oliepris tæller ikke som risk-on, fordi den både kan betyde billigere energi (godt) og svag efterspørgsel (dårligt).

Har en serie under 63 dages historik, bliver rækken *n/a* ("less than 3 months of history"). Begge rækker har kilden "prices" og bliver *stale* efter {{settings:coverage.max_age.prices}} dage uden nye data.

På [Regime](/regime) vises kobber/guld-ratioen som graf (ganget med 1.000 for læsbarhedens skyld). Se [brugervejledningen til regimet](brugervejledning/regime).

## Regneeksempel

**Kobber/guld.** For 63 handelsdage siden: kobber 5,00 dollar/pund, guld 4.000 dollar/ounce. I dag: kobber 5,40, guld 4.080.

- Kobber: 5,40 / 5,00 − 1 = +8,0 %
- Guld: 4.080 / 4.000 − 1 = +2,0 %
- Ratio før: 5,00 / 4.000 = 0,001250 (1,250 i grafen, ×1.000)
- Ratio nu: 5,40 / 4.080 = 0,001324 (1,324 i grafen)
- Ændring: 1,08 / 1,02 − 1 = **+5,88 %**

Med et bånd på 5 % (din opsætning: {{settings:regime.copper_gold_band|pct}}) er 5,88 % over grænsen → **risk-on**. Bemærk, at begge metaller steg; ratioen siger kun, at vækstmetallet steg mest.

**Et modeksempel.** Kobber stiger 6 %, men guld stiger 12 % (fx under geopolitisk uro, hvor kobber samtidig drives op af en strejke i Chile). Ratioændringen er 1,06 / 1,12 − 1 = −5,36 % → **risk-off**, selv om kobberprisen steg. Ratioen fanger, at frygten voksede mere end vækstforventningerne.

**Olie.** WTI var 62 dollar for 63 handelsdage siden og er nu 82 dollar: 82 / 62 − 1 = **+32,3 %**. Med en grænse på 30 % (din opsætning: {{settings:regime.oil_shock|pct}}) → **risk-off** ("Oil shock: inflation and margin risk"). Var den steget til 78 dollar (+25,8 %), ville rækken være neutral.

## Faldgruber og begrænsninger

- **Udbudschok forvirrer ratioen.** En minestrejke, eksportforbud eller toldsatser kan sende kobberprisen op uden nogen ændring i væksten. Centralbankers guldkøb kan sende guld op uden ændring i frygten.
- **Kina dominerer.** Kobberprisen siger meget om kinesisk byggeri og industri og mindre om Europa eller USA.
- **Dollaren påvirker begge.** Begge metaller handles i dollar. Ratioen ophæver en del af dollareffekten, men ikke al: guld reagerer typisk stærkere på dollaren og realrenten end kobber.
- **Strukturelle skift.** Elektrificering (kobber) og centralbankernes opkøb (guld) kan give ratioen en vedvarende tendens, der ikke har med konjunkturen at gøre.
- **Futures ruller.** Den kontinuerlige frontmånedskontrakt skifter til næste kontrakt ved udløb. Er der stor forskel mellem kontrakterne (contango eller backwardation), giver rullet et kunstigt spring i serien, som påvirker 3-måneders ændringen. Effekten er størst for olie.
- **Olie kun som risiko.** Rækken ser kun efter stigninger. Et oliekollaps (som i 2014–2015 eller april 2020) kan være et tegn på svag efterspørgsel og finansiel stress i energisektoren, men det stemmer ikke.
- **Efterspørgselsdrevet olie.** En stigning på over {{settings:regime.oil_shock|pct}} i en stærk økonomi stemmer risk-off, selv om den delvis er et vækstsignal. Reglen kan ikke skelne mellem Kilians typer af chok.

## Videre læsning

- Hamilton, J. D. (2009): "Causes and Consequences of the Oil Shock of 2007–08", *Brookings Papers on Economic Activity*, forår 2009.
- Kilian, L. (2009): "Not All Oil Price Shocks Are Alike: Disentangling Demand and Supply Shocks in the Crude Oil Market", *American Economic Review* 99(3).
- Erb, C. B. og Harvey, C. R. (2013): "The Golden Dilemma", *Financial Analysts Journal* 69(4).
- Murphy, J. J. (2004): *Intermarket Analysis: Profiting from Global Market Relationships*, Wiley.
