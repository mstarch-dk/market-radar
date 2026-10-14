# Relativ værdiansættelse

## Intuition

Et P/E-tal på 18 siger ikke meget alene. Er 18 meget for en bank? For et softwareselskab? Relativ værdiansættelse besvarer spørgsmålet ved at sammenligne med noget, der burde ligne: andre selskaber i samme branche, det brede marked eller aktiens egen fortid.

Ideen er den samme, som når man vurderer en lejlighed ud fra kvadratmeterprisen i samme kvarter. Man behøver ikke at regne en fuld cash flow-model; man spørger, om prisen ligger over eller under det, sammenlignelige ting handles til. Styrken er, at metoden er hurtig og bruger markedets egen prissætning. Svagheden er den samme: hvis hele sektoren er overvurderet, ser den mindst overvurderede aktie billig ud.

Radaren bruger tre sammenligninger:

- **Aktier mod sektoren**: aktiens P/E divideret med medianen for samme sektor blandt dens jævnaldrende.
- **Fonde mod ACWI**: fondens P/E divideret med ACWI's P/E.
- **Fonde mod egen historik**: hvor fondens P/E ligger i sin egen gemte historik.

## Teori

### Multipler og deres forudsætninger

En multipel som P/E er en komprimeret værdiansættelsesmodel. Fra [P/E og indtjening pr. aktie](laerebog/pe-og-eps) ved vi, at $P/\text{EPS}_1 = b/(r-g)$: multiplen afhænger af udlodningsgrad $b$, krævet afkast $r$ og vækst $g$. Når man sammenligner to selskabers P/E, antager man implicit, at de ligner hinanden på de tre punkter. Det er derfor, sammenligningen skal ske inden for en gruppe, der er så ens som muligt.

Liu, Nissim og Thomas (2002) undersøgte, hvor godt forskellige multipler forklarer aktiekurser, når man bruger branchemedianen som sammenligning. Forward P/E klarede sig bedst blandt de multipler, de testede; multipler baseret på bogført værdi, salg eller cash flow klarede sig dårligere. Det er en del af begrundelsen for, at radaren bruger næste års P/E.

### Relativ P/E

For aktie $i$ i sektor $s$ i peergruppe $G$:

$$
\text{rel}_i = \frac{\text{P/E}_i}{\operatorname{median}\{\text{P/E}_j : j \in G,\ \text{sektor}(j) = s\}}
$$

Medianen bruges frem for gennemsnittet, fordi P/E-fordelinger er skæve: et par selskaber med P/E på 150 trækker gennemsnittet meget op, men flytter næsten ikke medianen. En værdi på 0,8 betyder, at aktien handles 20 % billigere end sin typiske sektorfælle; 1,25 betyder 25 % dyrere.

### Sektorsammensætning

Sektorer er grove kasser. "Sundhed" rummer både stabile medicinalgiganter, biotek med underskud og hospitalskæder. "Teknologi" rummer både halvlederproducenter (cykliske) og softwareselskaber (abonnementsindtægter). En aktie kan være billig i forhold til sin sektor, blot fordi den tilhører en billigere undergruppe. Det samme gælder på tværs af regioner: europæiske sektorer handles typisk til lavere multipler end amerikanske, delvis på grund af en anden branchesammensætning og lavere vækst. Derfor sammenligner radaren inden for samme region eller marked.

### Værdifælder

En værdifælde (value trap) er en aktie, der ser billig ud og bliver ved med at være det, eller bliver billigere, fordi indtjeningen falder. Den lave multipel var markedets korrekte vurdering af en dårlig fremtid. Typiske kendetegn:

- Analytikerne sænker skønnene (negative [estimatrevisioner](laerebog/estimatrevisioner)).
- Kursen er i en nedadgående trend.
- Branchen er strukturelt presset (teknologisk disruption, regulering).
- Høj gæld, som P/E ikke ser.

Piotroski (2000) viste, at man inden for billige aktier kan skille vindere fra tabere med simple regnskabssignaler om rentabilitet, gæld og effektivitet. Asness, Moskowitz og Pedersen (2013) viste, at værdi og momentum er negativt korrelerede og supplerer hinanden. Begge peger på det samme: billig alene er ikke nok. Det er netop kombinationen af en relativ værdiansættelse med momentum og revisioner, radaren lægger op til.

### Fonde: P/E for en kurv af aktier

En fonds P/E beregnes af dataleverandøren ud fra beholdningerne. Den korrekte metode er det *harmoniske* vægtede gennemsnit, svarende til at lægge earnings yields sammen:

$$
\text{P/E}_{\text{fond}} = \frac{1}{\sum_k w_k \cdot \frac{1}{\text{P/E}_k}} = \frac{1}{\sum_k w_k \cdot \text{EY}_k}
$$

hvor $w_k$ er vægten af beholdning $k$. Det aritmetiske gennemsnit af P/E-tallene ville give en for høj værdi, fordi enkelte dyre aktier vejer uforholdsmæssigt. Hvordan selskaber med underskud behandles, varierer mellem leverandører.

### Mod egen historik

At sammenligne en fond med sin egen fortid besvarer et andet spørgsmål: er dette marked, sektor eller tema dyrere end normalt *for det*? Det renser ud for strukturelle forskelle (teknologi er altid dyrere end energi), men forudsætter, at fortiden er en relevant målestok. Et percentil siger, hvor stor en andel af de historiske observationer der ligger under dagens værdi.

## Sådan gør radaren

### P/E mod sektoren

Radaren beregner for hver aktie i det ugentlige snapshot (`valuation.py`, `signals/valuation.py`):

$$
\text{pe\_vs\_sector} = \frac{\text{pe\_fy1}}{\text{median af pe\_fy1 i samme sektor og peergruppe}}
$$

- **Basen** er næste regnskabsårs P/E (`pe_fy1`, kolonnen *P/E next yr*).
- **Peergruppen** er aktiens region i radaren (de lister, der ligger bag [Momentum](/momentum) og dine beholdninger) eller dens marked i [Discover](/discover). En dansk aktie på Momentum-siden sammenlignes altså med de nordiske aktier i radarens liste, mens den samme aktie på Discover sammenlignes med sit Discover-marked.
- **Sektoren** er Yahoos sektorinddeling: fra Discovers screener eller radarens egen sektorcache (sidstnævnte vinder, hvor begge findes). En aktie uden kendt sektor får ingen sammenligning.
- **Mindst {{settings:valuation.min_peers}} navne** i samme sektor og gruppe skal have en P/E, ellers er feltet tomt. Aktien selv tæller med i medianen og i antallet.

Forholdet vises i kolonnen *vs sector* (slås til i tabellen) og bruges til at farve *P/E next yr*. Farven kommer fra en graderet måler (`gauges.pe_vs_sector` i `settings.yaml`) med ankerpunkter, der interpoleres lineært: billigere end sektoren giver grøn, dyrere giver rød, og skalaen har mærker ved $({{settings:gauges.pe_vs_sector.ticks|raw}})$. Ordene går fra *cheap vs sector* over *in line* til *rich vs sector*.

> **Bemærk:** `settings.yaml` har også nøglen `valuation.rel_band` ({{settings:valuation.rel_band}}) med kommentaren "below 1 − band = cheap, above 1 + band = rich". Koden læser den ikke; graderingen styres alene af ankerpunkterne under `gauges.pe_vs_sector`. Vil du ændre, hvornår en aktie kaldes billig eller dyr i forhold til sektoren, er det dér, du skal rette.

### Fonde: P/E mod ACWI

For fonde henter radaren Yahoos fonddata (`funds_data.equity_holdings`) i et ugentligt snapshot, ligesom for aktier. Yahoo gemmer fondens multipler *omvendt*: feltet "Price/Earnings" indeholder i virkeligheden en earnings yield, fx 0,0312 for en fond på 32 gange indtjeningen. Radaren vender tallet om ($1/0.0312 \approx 32$) og beholder kun en fond-P/E inden for [{{settings:valuation.fund_pe_range}}]; uden for intervallet udelades den med en note. Tilsvarende vendes P/B, pris/salg og pris/cash flow om og områdekontrolleres (grænserne for dem står i koden).

Sammenligningen med verdensindekset er:

$$
\text{pe\_vs\_acwi} = \frac{\text{P/E}_{\text{fond}}}{\text{P/E}_{\text{ACWI}}}
$$

hvor ACWI's P/E kommer fra den samme kilde og det samme snapshot. Det er vigtigt, fordi Yahoo ikke oplyser, om fondens P/E er trailing eller forward. Ved at dividere med ACWI's tal fra samme kilde sammenlignes i det mindste ens med ens. Kolonnen hedder *vs ACWI*; fondens egen P/E vises i kolonnen *P/E* og farves efter `gauges.pe_vs_acwi` med mærker ved $({{settings:gauges.pe_vs_acwi.ticks|raw}})$.

### Fonde: mod egen historik

Når der er gemt mindst {{settings:valuation.etf_history_weeks}} ugentlige snapshots af en fonds P/E (dagens medregnet), beregnes percentilen: andelen af de gemte uger, hvor P/E lå *strengt under* dagens værdi, gange 100. Indtil da er feltet tomt. Kolonnen hedder *P/E pct*; 0 betyder den laveste P/E i den gemte historik, tæt på 100 den højeste. Historikken starter med radarens første snapshot, ikke med fondens start.

## Regneeksempel

> **Eksempel:** En industriaktie i radarens europæiske liste og en temafond. Tallene er opfundne.

**Aktien.** I den europæiske region har seks industriaktier en `pe_fy1` (inklusive aktien selv, som har 12):

| Aktie | A | B | C | D | E | F (vores) |
|---|---|---|---|---|---|---|
| P/E next yr | 14 | 16 | 18 | 20 | 25 | 12 |

Sorteret: 12, 14, 16, 18, 20, 25. Der er seks værdier, så medianen er gennemsnittet af nummer tre og fire:

$$
\operatorname{median} = \frac{16 + 18}{2} = 17
$$

Seks navne er mindst {{settings:valuation.min_peers}}, så forholdet beregnes:

$$
\text{pe\_vs\_sector} = \frac{12}{17} = 0.706
$$

Aktien handles knap 30 % under sin typiske sektorfælle, under det laveste mærke på måleren, og *P/E next yr* farves grøn. Havde en af de seks manglet en P/E (fx på grund af underskud), og havde min_peers været 6, ville feltet være tomt.

Bemærk, hvor lidt medianen påvirkes af E's P/E på 25: hvis E i stedet havde 60, var medianen stadig 17. Gennemsnittet ville springe fra 17,5 til 23,3.

**Fonden.** Yahoos fonddata viser "Price/Earnings" 0,0400 for temafonden og 0,0500 for ACWI:

$$
\text{P/E}_{\text{fond}} = \frac{1}{0.0400} = 25.0, \qquad \text{P/E}_{\text{ACWI}} = \frac{1}{0.0500} = 20.0
$$

$$
\text{pe\_vs\_acwi} = \frac{25.0}{20.0} = 1.25
$$

Temaet handles 25 % over verdensindekset. Radaren har 30 ugentlige snapshots af fonden; i 27 af dem lå P/E under 25,0:

$$
\text{pe\_pct} = 100 \cdot \frac{27}{30} = 90.0
$$

Fonden er altså både dyr i forhold til markedet og dyr i forhold til sin egen (korte) historik. Det kan være berettiget, hvis indtjeningen i temaet vokser hurtigt; det er et spørgsmål til analysen, ikke et svar.

## Faldgruber og begrænsninger

- **Relativt billig kan være absolut dyr.** Er hele sektoren overvurderet, er den billigste aktie stadig dyr. Se [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie) for markedets niveau.
- **Billig af en grund.** Lav relativ P/E følger ofte med lavere vækst, højere gæld eller højere risiko. Tjek [estimatrevisioner](laerebog/estimatrevisioner) og trend, før du tolker "billig" som en mulighed.
- **Peergruppen er et udsnit.** Radarens regioner er kuraterede lister, og Discovers markeder er det, Yahoos screener returnerer. Medianen af fem amerikanske forsyningsselskaber er et tyndt grundlag. Samme aktie kan få to forskellige tal på Momentum og Discover, fordi peergrupperne er forskellige.
- **Sektorer er grove.** Undergrupper med strukturelt forskellige multipler (biotek mod medicinal, software mod halvledere) blandes.
- **Fondens P/E-base er ukendt.** Yahoo oplyser ikke, om det er trailing eller forward, og metoden for underskudsgivende beholdninger er uoplyst. Sammenlign fondes P/E med hinanden og med ACWI fra samme kilde, ikke med FactSets forward P/E eller med en aktie-P/E fra screeneren.
- **Kort historik.** Percentilen i egen historik bygger kun på radarens egne snapshots. Et halvt års historik siger intet om, hvad der er "normalt" over en cyklus.
- **Regnskabsårsskift.** Omkring årsregnskaberne ruller `pe_fy1` til et nyt år for nogle selskaber før andre, så sektormedianen kan flytte sig, uden at noget har ændret sig.

## Videre læsning

- Jing Liu, Doron Nissim og Jacob Thomas: "Equity Valuation Using Multiples", *Journal of Accounting Research* 40(1), 2002.
- Joseph D. Piotroski: "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", *Journal of Accounting Research* 38 (supplement), 2000.
- Clifford S. Asness, Tobias J. Moskowitz og Lasse Heje Pedersen: "Value and Momentum Everywhere", *Journal of Finance* 68(3), 2013.
- Aswath Damodaran: *Damodaran on Valuation*, 2. udgave, Wiley, 2006 (kapitlerne om relativ værdiansættelse).
