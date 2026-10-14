# CAPE, risikopræmie og yield gap

## Intuition

De to forrige kapitler handlede om enkelte aktier og fonde. Dette kapitel handler om markedet som helhed, i praksis det amerikanske S&P 500, fordi det er der, de lange og frie dataserier findes. Spørgsmålet er: hvor dyrt er aktiemarkedet, og hvor meget bliver man betalt for at bære risikoen ved at eje aktier frem for obligationer?

Tre målinger besvarer det fra hver sin vinkel:

- **Shiller CAPE** ser på prisen i forhold til ti års gennemsnitlig indtjening, renset for inflation. Det glatter konjunkturen ud og gør det muligt at sammenligne med over 150 års historie.
- **Damodarans implicitte risikopræmie** spørger omvendt: givet dagens kurs og de forventede udlodninger, hvilket afkast er markedet så prissat til at give, og hvor meget er det over den risikofri rente?
- **Yield gap** er en simpel, aktuel version: indtjeningsafkastet på forward-basis minus den reale obligationsrente.

Alle tre har det til fælles, at de siger noget om de næste ti år og meget lidt om de næste seks måneder. Et dyrt marked kan blive dyrere i årevis. Derfor stemmer de som standard ikke med i radarens regime.

## Teori

### Shiller CAPE

CAPE (cyclically adjusted price-to-earnings), også kaldet Shiller P/E eller P/E10, blev populær med Campbell og Shiller (1988, 1998). Ideen går tilbage til Graham og Dodd, der anbefalede at se på indtjeningen over flere år frem for ét. Definitionen:

$$
\text{CAPE}_t = \frac{P_t^{\text{real}}}{\bar{E}_t^{\text{real}}}, \qquad \bar{E}_t^{\text{real}} = \frac{1}{120}\sum_{k=0}^{119} E_{t-k}^{\text{real}}
$$

hvor $P_t^{\text{real}}$ er indeksets inflationsjusterede kurs, og $E_{t-k}^{\text{real}}$ er den løbende 12-måneders indtjening i måned $t-k$, også inflationsjusteret. Nævneren er altså gennemsnittet af ti års årlig indtjening. Inflationsjusteringen sker med forbrugerprisindekset, så indtjening fra for ti år siden regnes i dagens penge.

Hvorfor ti år? En konjunkturcyklus varer typisk fem til ti år. Et etårigt P/E er lavt på toppen af en cyklus (høj indtjening) og højt i bunden (indtjeningen kollapser, som i 2009, hvor S&P 500's trailing P/E kortvarigt var over 100). Tiårsgennemsnittet udglatter det.

Den omvendte værdi, $1/\text{CAPE}$, er et cyklisk justeret indtjeningsafkast. Med en CAPE på 35 er det $1/35 \approx 2.9\ \%$; det er et groft skøn over det reale langsigtede afkast, hvis multiplen holder sig.

### Hvad CAPE kan, og hvad den ikke kan

Campbell og Shiller (1998) viste, at CAPE har betydelig forklaringskraft for de følgende ti års reale afkast: høj CAPE har historisk været fulgt af lave tiårsafkast og omvendt. Forklaringsgraden over et år er derimod lille. Goyal og Welch (2008) gennemgik en lang række af den slags prædiktorer og fandt, at de fleste klarer sig dårligt uden for den periode, de er estimeret på; det gælder især på korte horisonter.

Som timingværktøj har CAPE en dårlig rekord. Den var over sit historiske gennemsnit stort set uafbrudt fra begyndelsen af 1990'erne, og en investor, der reducerede aktieandelen hver gang CAPE var "høj", ville have misset en stor del af afkastet. Der er også strukturelle indvendinger (Siegel, 2016):

- Ændrede regnskabsregler (fx krav om nedskrivning af goodwill og immaterielle aktiver) har trykket den rapporterede indtjening, især i recessioner, og dermed løftet CAPE.
- Lavere udlodningsgrad og flere tilbagekøb giver højere indtjeningsvækst pr. aktie, hvilket gør tiårsgennemsnittet "for gammelt".
- Sektorsammensætningen er ændret mod teknologi med højere marginer.
- Lavere renter retfærdiggør højere multipler (se yield gap nedenfor).

Det taler for at sammenligne med en nyere periode end 1871 også. Radaren viser derfor både percentilen siden 1871 og siden 1990.

### Implicit risikopræmie (Damodaran)

Aktierisikopræmien (equity risk premium, ERP) er det ekstra afkast, investorer kræver for at eje aktier frem for en risikofri obligation. Den historiske præmie måles bagud (realiseret afkast minus obligationsafkast) og er meget følsom over for perioden. Den *implicitte* præmie måles fremad: man finder den diskonteringsrente $r$, der får nutidsværdien af de forventede udlodninger til at svare til dagens indeksniveau, og trækker den risikofri rente fra.

Damodaran opdaterer sit skøn månedligt for S&P 500. Hans model har to faser:

$$
P_0 = \sum_{t=1}^{5} \frac{CF_0 (1+g)^t}{(1+r)^t} + \frac{CF_5 \,(1+g_\infty)}{(r - g_\infty)(1+r)^5}
$$

- $P_0$ er indeksniveauet i dag.
- $CF_0$ er de samlede kontante udlodninger (udbytter plus aktietilbagekøb) de seneste tolv måneder ("T12m"). Andre varianter i hans regneark bruger fx et normaliseret gennemsnit over ti år.
- $g$ er analytikernes forventede indtjeningsvækst de næste fem år.
- $g_\infty$ er den langsigtede vækst, sat lig med den risikofri rente.
- $r$ løses numerisk, og $\text{ERP} = r - r_f$, hvor $r_f$ er renten på den amerikanske tiårige statsobligation.

En lav implicit ERP betyder, at investorerne accepterer en tynd belønning for aktierisiko, typisk efter lange stigninger. En høj ERP betyder, at aktier er prissat til at give et pænt merafkast, typisk efter kraftige fald (fx primo 2009, hvor præmien var over 6 %).

### Yield gap og Fed-modellen

Den såkaldte Fed-model sammenligner indtjeningsafkastet på aktier med renten på statsobligationer:

$$
\text{yield gap} = \frac{100}{\text{forward P/E}} - y_{10}
$$

Navnet stammer fra en analyse i Federal Reserves Humphrey-Hawkins-rapport fra 1997; Fed har aldrig brugt den som officiel model. Den klassiske version bruger den *nominelle* tiårige rente. Asness (2003) kritiserede netop det: indtjening er en real størrelse, der følger med inflationen, mens den nominelle rente indeholder en inflationskompensation. At sammenligne de to er at sammenligne et realt med et nominelt tal. Empirisk har den nominelle Fed-model ingen god evne til at forudsige langsigtede aktieafkast.

Bruges i stedet den *reale* rente (fx renten på inflationsbeskyttede statsobligationer, TIPS), bliver sammenligningen konsistent: indtjeningsafkastet er en grov approksimation af det reale forventede aktieafkast, og den reale obligationsrente er det reale risikofri afkast. Forskellen er en simpel, aktuel udgave af risikopræmien. Det er den variant, radaren viser.

## Sådan gør radaren

### Kilder

| Måling | Kilde | Frekvens | Historik |
|---|---|---|---|
| CAPE | multpl.com (Shillers metode, uofficiel) | månedlig, første række er et løbende skøn for måneden | siden 1871 |
| Implicit ERP | Damodarans regneark `ERPbymonth.xlsx`, kolonnen "ERP (T12m)" | månedlig | siden 2008 |
| Forward P/E | FactSet Earnings Insight (S&P 500, næste 12 måneder) | ugentlig | radarens egne rapporter |
| Real tiårig rente | FRED-serien `DFII10` (10-årige TIPS) | daglig | |

Shillers egen offentlige fil stoppede ved september 2024; multpl.com følger hans metode og stemmer med hans fil, hvor begge har endelige tal. Begge parsere fejler højlydt, hvis kilden har ændret format (for få rækker, manglende kolonner, ERP-værdier uden for −5 % til 20 %), og det seneste gemte data bliver stående.

### Percentiler

Radaren rangerer den seneste værdi mod historikken *før* den:

$$
\text{percentil} = 100 \cdot \frac{\#\{\text{tidligere værdier} < \text{seneste værdi}\}}{\#\{\text{tidligere værdier}\}}
$$

Den seneste observation er altså udeladt af sammenligningsgrundlaget, og der tælles kun værdier, der er *strengt* lavere. For CAPE beregnes to percentiler: siden 1871 og siden 1. januar 1990. Medianen, der vises ved siden af, er medianen over hele serien.

### Regimeafstemningen

CAPE og ERP indgår som rækker i gruppen *valuation* i [risk-on/risk-off-afstemningen](laerebog/afstemningsmodellen). Gruppen er som udgangspunkt slået {{settings:regime.votes.valuation}} (`regime.votes.valuation` i `settings.yaml`), fordi målingerne bevæger sig langsomt og ikke er et 1–6-måneders timingsignal. Du kan slå den til på [Regime](/regime)-siden. Når gruppen er slået fra, vises rækkerne stadig med deres måler, men tæller ikke med.

Når gruppen stemmer:

- **CAPE** (percentilen siden 1871): $\geq$ {{settings:regime.cape_rich_pct}} giver risk-off (strakt værdiansættelse), $\leq$ {{settings:regime.cape_cheap_pct}} giver risk-on, ellers neutral.
- **ERP** (percentilen siden 2008): $\leq$ {{settings:regime.erp_low_pct}} giver risk-off (tynd præmie), $\geq$ {{settings:regime.erp_high_pct}} giver risk-on, ellers neutral.

Yield gap stemmer ikke; den vises kun. Er CAPE- eller ERP-data ældre end {{settings:coverage.max_age.cape}} henholdsvis {{settings:coverage.max_age.erp}} dage, bliver rækken forældet (*stale*) og stemmer ikke, uanset indstillingen.

### Yield gap

$$
\text{yield gap} = \frac{100}{\text{FactSet forward P/E}} - \text{DFII10}
$$

begge i procent, så resultatet er i procentpoint. Mangler FactSet-rapporten eller FRED-serien, er feltet tomt. Måleren `gauges.yield_gap` grader resultatet fra *thin* til *wide* med mærker ved $({{settings:gauges.yield_gap.ticks|raw}})$ procentpoint.

Alle tre ses i afsnittet *Valuation* på [Positioning & cycle](/positioning), med grafer over historikken; se også [brugervejledningen](brugervejledning/positionering).

## Regneeksempel

> **Eksempel:** Tallene er opfundne, men i en realistisk størrelsesorden.

**CAPE.** S&P 500 står i 6.300. De seneste ti års inflationsjusterede indtjening er i gennemsnit 180 indekspoint om året:

$$
\text{CAPE} = \frac{6300}{180} = 35.0, \qquad \frac{1}{\text{CAPE}} = 2.86\ \%
$$

Serien har 1.850 tidligere månedsværdier, og 1.795 af dem ligger under 35,0:

$$
\text{percentil siden 1871} = 100 \cdot \frac{1795}{1850} = 97.0
$$

Siden 1990 er der 429 tidligere måneder, og 380 ligger under:

$$
\text{percentil siden 1990} = 100 \cdot \frac{380}{429} = 88.6
$$

Med standardindstillingerne er 97,0 over grænsen på {{settings:regime.cape_rich_pct}}, så rækken ville stemme risk-off, hvis gruppen var slået til. Bemærk, at percentilen siden 1990 ville ligge lige under grænsen; afstemningen bruger tallet siden 1871.

**Implicit ERP, forenklet.** Damodarans model har to faser og løses numerisk. For at se mekanikken kan vi bruge en etfaset (Gordon) version, hvor udlodningerne vokser med $g_\infty = r_f$ fra start. Udlodningerne de seneste tolv måneder er 3,0 % af indekset, altså $0.030 \cdot 6000 = 180$ point ved et indeks på 6.000, og den tiårige rente er 4,2 %:

$$
r = \frac{CF_0 (1 + g_\infty)}{P_0} + g_\infty = \frac{180 \cdot 1.042}{6000} + 0.042 = 0.03126 + 0.042 = 0.0733
$$

$$
\text{ERP} = r - r_f = 7.33\ \% - 4.20\ \% = 3.13\ \%
$$

Med højere forventet vækst de første fem år (Damodarans første fase) ville $r$ og dermed ERP blive højere.

**Yield gap.** FactSets forward P/E er 22,5, og `DFII10` er 1,85 %:

$$
\frac{100}{22.5} = 4.44\ \%, \qquad \text{yield gap} = 4.44 - 1.85 = 2.59 \text{ procentpoint}
$$

Det ligger mellem de to nederste mærker på måleren, i den tynde ende. Havde man brugt den nominelle tiårige rente på 4,2 % (den klassiske Fed-model), ville gabet være $4.44 - 4.20 = 0.24$ procentpoint, og konklusionen langt mere alarmerende. Valget af rente betyder altså meget.

## Faldgruber og begrænsninger

- **Lang horisont, ikke timing.** CAPE og ERP forklarer en del af tiårsafkastene og meget lidt af de næste måneder. Det er grunden til, at gruppen er slået fra i afstemningen som udgangspunkt.
- **Kun USA.** Alle tre målinger gælder S&P 500. Europæiske og nordiske aktier handles typisk til lavere multipler; en høj amerikansk CAPE siger ikke direkte noget om dem.
- **Strukturelle skift.** Regnskabsregler, udlodningspolitik og sektorsammensætning har ændret sig siden 1871. Sammenlign percentilen siden 1871 med percentilen siden 1990, før du konkluderer.
- **Uofficielle kilder.** multpl.com er ikke Shiller selv, og den seneste måned er et løbende skøn, der revideres. Damodarans regneark kan ændre layout.
- **ERP afhænger af antagelser.** Vækstskøn, valg af cash flow (T12m eller normaliseret) og terminal vækst flytter tallet. Damodaran publicerer flere varianter; radaren bruger hans hovedtal.
- **Kort ERP-historik.** Percentilen siden 2008 dækker én lang periode med lave renter og én med stigende. "Høj" og "lav" er relativt til netop den periode.
- **Blandede baser i yield gap.** FactSets forward P/E er for de næste 12 måneder, mens Yahoos aktie-P/E i radaren er for næste regnskabsår. Sammenlign ikke de to direkte.
- **Percentilen udelader den seneste værdi**, men medianen gør ikke. Det har kun betydning for korte serier.

## Videre læsning

- John Y. Campbell og Robert J. Shiller: "Stock Prices, Earnings, and Expected Dividends", *Journal of Finance* 43(3), 1988.
- John Y. Campbell og Robert J. Shiller: "Valuation Ratios and the Long-Run Stock Market Outlook", *Journal of Portfolio Management* 24(2), 1998.
- Robert J. Shiller: *Irrational Exuberance*, Princeton University Press, 2000 (3. udgave 2015).
- Jeremy J. Siegel: "The Shiller CAPE Ratio: A New Look", *Financial Analysts Journal* 72(3), 2016.
- Amit Goyal og Ivo Welch: "A Comprehensive Look at the Empirical Performance of Equity Premium Prediction", *Review of Financial Studies* 21(4), 2008.
- Aswath Damodaran: "Equity Risk Premiums (ERP): Determinants, Estimation, and Implications", SSRN-arbejdspapir, opdateres årligt. Data: https://pages.stern.nyu.edu/~adamodar/
- Clifford S. Asness: "Fight the Fed Model", *Journal of Portfolio Management* 30(1), 2003.
