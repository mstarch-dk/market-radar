# Kredit, renter og dollar

## Intuition

Aktiemarkedet er ikke det eneste sted, hvor risikovilje prissættes. Obligationsmarkedet er større, og dets investorer er ofte mere nøgterne: en virksomhedsobligation kan i bedste fald give renten og pengene tilbage, så obligationsinvestorer fokuserer på én ting, nemlig risikoen for at tabe. Når de bliver nervøse, kræver de mere i rente for at låne til svage selskaber. Den ekstra rente, kreditspændet, er et af de bedste realtidsmål for finansiel stress.

Renterne selv betyder også noget. Rentekurvens form siger noget om forventningerne til økonomien og pengepolitikken. Og et hurtigt rentehop gør fremtidig indtjening mindre værd og strammer de finansielle forhold for alle, der skal låne.

Endelig er dollaren verdens finansieringsvaluta. En stor del af verdens gæld uden for USA er i dollar. Når dollaren stiger kraftigt, bliver den gæld tungere, og globale finansielle forhold strammes. En svagere dollar virker modsat.

## Teori

### Kreditspænd

Et kreditspænd er forskellen mellem renten på en virksomhedsobligation og renten på en statsobligation med samme løbetid:

$$
s = y_{\text{virksomhed}} - y_{\text{stat}}
$$

Spændet kompenserer for tre ting: den forventede tabsrate (sandsynligheden for konkurs gange tabet ved konkurs), en risikopræmie for at bære den usikkerhed, og en likviditetspræmie. I *high yield* (HY), obligationer med kreditvurdering under BBB−, er konkursrisikoen så stor, at spændet reagerer stærkt på konjunkturen.

Indeksudbyderen ICE BofA beregner spændet som *option-adjusted spread* (OAS): spændet efter at der er korrigeret for indbyggede optioner (fx at udstederen kan indfri tidligt). FRED offentliggør OAS for det amerikanske HY-indeks (BAMLH0A0HYM2) og det europæiske HY-indeks i euro (BAMLHE00EHYIOAS) i procent.

Gilchrist og Zakrajšek (2012) viste, at den del af kreditspændet, der *ikke* forklares af forventede konkurser, "excess bond premium", er en stærk forudsiger af økonomisk aktivitet. Når långiverne bliver mere risikoaverse, strammes kreditten, og aktiviteten falder bagefter. Kreditspænd udvides typisk *før* eller *samtidig med* aktiemarkedsfald, og de snævrer ind igen, når stressen letter.

Det er retningen og hastigheden, der betyder mest. Et spænd på 3,5 % kan være rigeligt i én periode og stramt i en anden. Derfor sammenlignes spændet med sit eget nylige gennemsnit.

### Rentekurven

Rentekurven viser renten på statsobligationer mod løbetiden. Normalt stiger den med løbetiden: man kræver mere for at låne ud i ti år end i to. Spændet mellem 10-årig og 2-årig rente er det mest fulgte mål for kurvens hældning:

$$
\text{Kurve} = y_{10\text{Y}} - y_{2\text{Y}}
$$

Når kurven er *inverteret* (negativ), forventer markedet, at centralbanken vil sænke renten i fremtiden, typisk fordi den nu strammer for at bremse inflationen, og fordi økonomien ventes at svækkes. En inverteret amerikansk rentekurve er gået forud for alle amerikanske recessioner siden 1960'erne, typisk med 6–24 måneder (Harvey, 1988; Estrella og Mishkin, 1998). Men tidsforskydningen er lang og varierende, og signalet er ikke ufejlbarligt: kurven var inverteret fra midten af 2022 til efteråret 2024, uden at der kom en recession i den periode. Ofte er det først, når kurven bliver positiv igen (fordi korte renter falder i takt med, at centralbanken sænker), at recessionen rammer.

### Renteshock

Aktiekurser er nutidsværdien af fremtidig indtjening. Stiger den lange rente, falder nutidsværdien, mest for selskaber, hvis indtjening ligger langt ude i fremtiden (vækstaktier har lang "aktieduration"). En gradvis rentestigning i en stærk økonomi kan aktiemarkedet godt bære. Et *hurtigt* rentehop er anderledes: det strammer de finansielle forhold på kort tid, gør boliglån og virksomhedslån dyrere og tvinger investorer til at genprissætte. 2022 er det oplagte eksempel: den amerikanske 10-årige rente steg fra cirka 1,5 % til over 4 %, og både aktier og obligationer faldt.

### Realrente og inflationsforventninger

Den nominelle rente kan deles i to dele (Fisher-relationen, tilnærmet):

$$
y_{\text{nominel}} \approx y_{\text{real}} + \pi^{e}
$$

Den *reale* rente aflæses af inflationsindekserede statsobligationer (TIPS); FRED-serien DFII10 er den 10-årige. Forskellen mellem nominel og real rente er *breakeven-inflationen* (T10YIE): markedets forventning til inflationen over ti år, plus en risikopræmie. Opdelingen fortæller, *hvorfor* renten bevæger sig. En stigende realrente betyder strammere pengepolitik eller højere vækstforventninger, og den rammer især vækstaktier og guld. Stigende breakevens betyder inflationsfrygt.

### Euroområdets rente

For en dansk investor er de europæiske renter mindst lige så relevante, både for obligationer og for den danske kronekurs, der er bundet til euroen. ECB offentliggør en rentekurve for euroområdets statsobligationer med AAA-rating; den 10-årige rente fra den kurve er et rent mål for det lange europæiske renteniveau uden kreditrisiko fra lande med lavere rating.

### Dollaren

Det brede dollarindeks (DTWEXBGS, Federal Reserve) måler dollaren mod en handelsvægtet kurv af valutaer. Bruno og Shin (2015) viste, at en stærkere dollar strammer de globale finansielle forhold: banker og virksomheder uden for USA, der har lånt i dollar, får tungere gæld og låner mindre. Derfor falder emerging markets og råvarer typisk, når dollaren stiger hurtigt, og omvendt. En svagere dollar er historisk gået sammen med bredere global vækst og risk-on.

For en dansk investor har dollaren desuden en direkte virkning: amerikanske aktier og ACWI (der er cirka 60–65 % amerikansk) mister værdi i kroner, når dollaren falder. Se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).

## Sådan gør radaren

Alle serier hentes som CSV fra FRED uden API-nøgle (`macro.fred` i `config/universe.yaml`), undtagen euroområdets 10-årige rente, der hentes fra ECB's Data Portal (`external.ecb`). FRED-serier er daglige (bankdage). "Observationer" nedenfor betyder datapunkter i serien, ikke kalenderdage; 63 observationer er cirka 3 måneder, 126 cirka 6. Tærsklerne 0,97, 1,03 og ±3 % ligger fast i koden (`src/radar/signals/regime.py`).

| Række | Serie | Regel | Kan stemme |
|---|---|---|---|
| *Credit (US HY spread)* | BAMLH0A0HYM2 | risk-on hvis seneste < 0,97 × gennemsnittet af de seneste 126 obs.; risk-off hvis > 1,03 × | begge veje |
| *Euro credit (HY spread)* | BAMLHE00EHYIOAS | samme regel; kræver over 63 obs. | begge veje, gruppe `credit_eu` |
| *Yield curve (10Y-2Y)* | T10Y2Y | risk-off hvis under 0, ellers neutral | kun risk-off |
| *US 10Y yield* | DGS10 | risk-off hvis stigningen over 63 obs. er over {{settings:regime.rates_shock}} procentpoint | kun risk-off |
| *US dollar (broad)* | DTWEXBGS | ændring over 63 obs.: over +3 % risk-off, under −3 % risk-on | begge veje |

Bemærk:

- **Euro-kreditrækken kan slås fra.** Den tilhører gruppen `credit_eu`, der som standard er slået {{settings:regime.votes.credit_eu}} (`regime.votes.credit_eu`), og som du kan slå til og fra på [Regime](/regime). Er den slået fra, vises aflæsningen, men den stemmer ikke. FRED har kun cirka tre års historik for den europæiske serie.
- **Envejsrækker.** Rentekurven og den 10-årige rente kan kun stemme risk-off. En positiv kurve eller en rolig rente er normaltilstanden og tæller som neutral, ikke som et risk-on-tegn.
- **Friskhed.** FRED-rækker bliver *stale* og holder op med at stemme, hvis seneste datapunkt er mere end {{settings:coverage.max_age.fred}} dage ældre end rapportens dato. Grænsen er så rummelig, fordi dollarindekset offentliggøres med 1–2 ugers forsinkelse.

**Informerer uden at stemme.** Realrenten (DFII10), breakeven-inflationen (T10YIE) og euroområdets 10-årige AAA-rente (ECB) vises sammen med den amerikanske 10-årige rente på [Positionering](/positioning) under *Rates: US and euro area*, som graf og seneste værdier. De indgår ikke i afstemningen. Realrenten bruges desuden i *yield gap* (se [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie)).

Graferne på [Regime](/regime) viser HY-spændene for USA og euroområdet i samme figur.

## Regneeksempel

**Amerikansk HY-spænd.** Gennemsnittet over de seneste 126 observationer er 3,20 %. Grænserne er 0,97 × 3,20 = 3,104 % og 1,03 × 3,20 = 3,296 %. Seneste værdi er 3,05 %: 3,05 / 3,20 = 0,953, under 0,97 → **risk-on** ("tightening").

**Europæisk HY-spænd.** Gennemsnit 3,50 %, seneste 3,45 %: 3,45 / 3,50 = 0,986, mellem 0,97 og 1,03 → **neutral**.

**Rentekurven.** 10Y − 2Y = +0,45 procentpoint. Ikke negativ → **neutral**.

**10-årig rente.** For 63 observationer siden 4,05 %, nu 4,62 %. Stigning: 4,62 − 4,05 = 0,57 procentpoint. Antag en tærskel på 0,5 (din opsætning: {{settings:regime.rates_shock}}): 0,57 > 0,5 → **risk-off** ("rate shock").

**Dollaren.** Indekset var 120,0 for 63 observationer siden og er nu 116,1: 116,1 / 120,0 − 1 = −3,25 %. Under −3 % → **risk-on**.

**Opdeling af renten.** Er realrenten 2,20 % og breakeven 2,42 %, er den nominelle rente cirka 2,20 + 2,42 = 4,62 %. Stiger den nominelle rente med 0,57 procentpoint, og 0,45 af det er realrente, er det primært strammere reale forhold, ikke inflationsfrygt, der driver stigningen. Det rammer typisk vækstaktier og guld hårdest.

**Samlet** fra disse fem rækker: 2 risk-on, 1 risk-off, 2 neutrale. Billedet er blandet på en karakteristisk måde: kreditmarkedet er roligt, og dollaren svækkes (begge positive), men renterne stiger hurtigt. Det er typisk for en periode med stærk vækst og stramnings-frygt.

## Faldgruber og begrænsninger

- **Relativt til eget gennemsnit.** Kreditreglen måler ændringen mod de seneste 6 måneder, ikke niveauet. Efter en lang periode med stramme spænd er et lille hop nok til at stemme risk-off; efter en krise kan et højt spænd stemme risk-on, fordi det falder.
- **Rentekurven er langsom og upræcis i tid.** En inversion siger "recession inden for nogle år, måske", ikke "sælg nu". Derfor kan den kun stemme risk-off i radaren, og derfor bør den vejes let.
- **Renteshock har forskellige årsager.** En rentestigning på grund af stærk vækst er mindre farlig end en på grund af inflation eller statsgæld. Radaren skelner ikke; se opdelingen i realrente og breakeven på [Positionering](/positioning).
- **USA-tungt.** Fire af fem rækker er amerikanske. Europæisk stress ses kun gennem det europæiske HY-spænd.
- **Dollaren er tvetydig.** En stigende dollar kan være risk-off (flugt til sikkerhed) eller afspejle stærk amerikansk vækst. Ved ±3 % over 3 måneder er bevægelsen stor nok til, at den globale finansieringseffekt typisk dominerer, men ikke altid.
- **Datahuller.** FRED-serier har huller på amerikanske helligdage, og HY-indeksene kan blive revideret. Det europæiske spænd har kort historik på FRED.
- **Korrelation.** I en krise udvides begge HY-spænd, dollaren stiger, og kurven ændrer sig samtidig. Det kan blive fire risk-off-stemmer fra én begivenhed.

## Videre læsning

- Gilchrist, S. og Zakrajšek, E. (2012): "Credit Spreads and Business Cycle Fluctuations", *American Economic Review* 102(4).
- Estrella, A. og Mishkin, F. S. (1998): "Predicting U.S. Recessions: Financial Variables as Leading Indicators", *Review of Economics and Statistics* 80(1).
- Harvey, C. R. (1988): "The Real Term Structure and Consumption Growth", *Journal of Financial Economics* 22(2).
- Bruno, V. og Shin, H. S. (2015): "Cross-Border Banking and Global Liquidity", *Review of Economic Studies* 82(2).
- Federal Reserve Bank of St. Louis: FRED, https://fred.stlouisfed.org (seriebeskrivelser for BAMLH0A0HYM2, BAMLHE00EHYIOAS, T10Y2Y, DGS10, DFII10, T10YIE og DTWEXBGS).
