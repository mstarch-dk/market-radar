# Put/call og AAII: kontrær sentiment

## Intuition

Sentiment er markedsdeltagernes stemning: hvor optimistiske eller bange de er. Den kontrære idé er gammel og enkel. Når næsten alle er bange, har de fleste allerede solgt eller afdækket sig, og der er få sælgere tilbage; når næsten alle er begejstrede, har de fleste allerede købt, og der er få købere tilbage. Ekstrem frygt har derfor en tendens til at komme før bedre afkast, og ekstrem eufori før svagere.

Radaren måler sentiment på to måder:

- **Put/call-forholdet** fra optionsbørsen CBOE måler, hvad folk *gør*: hvor mange salgsoptioner (puts, en forsikring mod fald) der handles i forhold til købsoptioner (calls, en satsning på stigning).
- **AAII-undersøgelsen** måler, hvad folk *siger*: andelen af amerikanske privatinvestorer, der forventer stigning, minus andelen, der forventer fald.

Begge er kontrære: højt put/call og lav AAII-stemning er *støttende* for aktier, lavt put/call og høj stemning er en advarsel. Ingen af dem stemmer i radarens regime. Evidensen for dem er svagere end for trend og momentum, og den er bedst ved ekstremerne. Midt i fordelingen siger de næsten intet.

## Teori

### Hvorfor sentiment kan forudsige afkast

I en verden med fuldt rationelle investorer burde stemning ikke påvirke priserne. Baker og Wurgler (2006, 2007) argumenterer for, at to ting tilsammen gør sentiment relevant: der findes investorer, hvis efterspørgsel svinger med stemningen, og der er grænser for arbitrage, så rationelle investorer ikke fuldt ud kan modvirke dem. Resultatet er perioder, hvor priserne er for høje, fordi stemningen er for god, efterfulgt af lavere afkast, og omvendt. De fandt effekten stærkest for aktier, der er svære at værdiansætte og svære at arbitrere: små, unge, volatile og ulønsomme selskaber.

### Put/call-forholdet

$$
\text{P/C} = \frac{\text{antal handlede puts}}{\text{antal handlede calls}}
$$

CBOE offentliggør flere varianter:

- **Equity**: kun optioner på enkeltaktier. Domineret af privatinvestorer og spekulanter.
- **Index**: optioner på indeks (fx SPX). Domineret af institutioner, der afdækker porteføljer; ligger strukturelt højt, fordi indeks-puts bruges som forsikring.
- **Total**: alle sammen.

Equity-forholdet er det, der oftest bruges som kontrær indikator, netop fordi det afspejler spekulativ efterspørgsel mere end strukturel afdækning. Et højt forhold betyder mange køb af beskyttelse: frygt. Et lavt forhold betyder mange køb af calls: optimisme, til tider eufori (som i optionsboomet i 2020–2021).

Dagstallene er støjende, så man bruger et glidende gennemsnit, typisk over 5, 10 eller 21 dage.

Simon og Wiggins (2001) fandt, at put/call-forholdet sammen med VIX og andre "frygtmål" havde statistisk signifikant kontrær forudsigelsesevne for S&P 500-futures over de følgende uger. Pan og Poteshman (2006) fandt derimod for *enkeltaktier*, at put-køb fra informerede investorer forudsiger *lavere* afkast i den pågældende aktie. Den kontrære fortolkning gælder altså markedsniveauet, ikke den enkelte aktie.

### AAII-undersøgelsen

American Association of Individual Investors har siden juli 1987 hver uge spurgt sine medlemmer, om de tror, aktiemarkedet stiger, er uændret eller falder de næste seks måneder. Svarene giver tre andele, der summerer til 100 %:

$$
\text{spread} = \text{andel bullish} - \text{andel bearish}
$$

Den neutrale andel indgår ikke direkte. Spreadet har et historisk gennemsnit lidt over nul, fordi privatinvestorer i gennemsnit er en smule optimistiske.

Fisher og Statman (2000) fandt, at sentiment blandt privatinvestorer (AAII) og blandt Wall Street-strateger var negativt korreleret med det følgende afkast på S&P 500: høj optimisme blev fulgt af lavere afkast. Brown og Cliff (2004) fandt, at sentimentmål hænger stærkt sammen med det *samtidige* og *foregående* afkast (stemningen følger kurserne), men har ringe evne til at forudsige afkast over de næste uger. Brown og Cliff (2005) fandt en tydeligere sammenhæng over et til tre år.

Samlet billede: AAII-stemningen er for en stor del et ekko af de seneste ugers kursudvikling. Den har mest information ved ekstremerne, fx i marts 2009 eller efteråret 2022, hvor andelen af bearish investorer var usædvanlig høj.

### Percentiler frem for niveauer

Både put/call og AAII-spreadet har niveauer, der flytter sig over tid. Equity put/call-forholdet faldt fx markant i årene med massiv privat call-handel. En fast tærskel ("over 0,8 er frygt") bliver derfor forældet. En percentil i et rullende eller langt vindue tilpasser sig.

## Sådan gør radaren

### Put/call

Radaren henter CBOE's daglige markedsstatistik (en JSON-fil pr. handelsdag, `sources/sentiment.py`) med det totale, det equity- og det indeksbaserede forhold. Første gang hentes {{settings:sentiment.putcall_backfill_days}} dages historik (`sentiment.putcall_backfill_days`); derefter hver hverdag siden den seneste gemte. En dag, CBOE svarer 403 eller 404 på, springes over (helligdag eller endnu ikke offentliggjort). Kommer der intet for en hel uges hverdage, fejler opdateringen højlydt, og de gemte data bliver stående. Forhold uden for 0,05–10 afvises (fast i koden).

Beregningen (`signals/valuation.py`):

1. Equity-forholdets **10-dages glidende gennemsnit** (fast i koden).
2. **Percentilen** af dagens 10-dagesgennemsnit mod de foregående 10-dagesgennemsnit i et vindue på {{settings:sentiment.putcall_lookback_days}} handelsdage (`sentiment.putcall_lookback_days`, omkring tre år). Dagens værdi indgår ikke i sammenligningsgrundlaget; der tælles værdier, der er strengt lavere.
3. Percentilen beregnes først, når der er mindst 60 tidligere 10-dagesgennemsnit (fast i koden).

Høj percentil = meget put-handel = frygt = kontrært støttende. Måleren `gauges.putcall_pct` farver høje værdier grønne og lave røde, med mærker ved $({{settings:gauges.putcall_pct.ticks|raw}})$ og ord fra *complacent* over *normal* til *fearful*. Data er forældede efter {{settings:coverage.max_age.putcall}} dage.

### AAII

Radaren henter AAII's ugentlige regneark med alle målinger siden 1987. Overskriften skal være *Bullish / Neutral / Bearish*, og de tre andele skal summere til cirka 100 % (mellem 97 og 103 %); ellers fejler opdateringen, og de gemte data bliver stående.

Beregningen:

- **Spread** = bullish − bearish for den seneste uge.
- **Percentil** af den seneste uges spread mod alle tidligere ugers spread siden 1987 (den seneste udeladt, strengt lavere værdier talt).
- **Flag**: percentil $\leq$ {{settings:sentiment.aaii_extreme_pct}} giver *extreme fear*; percentil $\geq 100 -$ {{settings:sentiment.aaii_extreme_pct|raw}} giver *euphoria* (`sentiment.aaii_extreme_pct`).
- **8-ugers gennemsnit** af spreadet vises ved siden af som en mere rolig læsning. Bemærk, at det er den enkelte uges spread, ikke 8-ugersgennemsnittet, der rangeres.

Måleren `gauges.aaii_pct` er vendt modsat put/call: lav percentil (frygt) er grøn, høj (eufori) er rød, med mærker ved $({{settings:gauges.aaii_pct.ticks|raw}})$. En graf viser spreadet de seneste tre år. Data er forældede efter {{settings:coverage.max_age.aaii}} dage.

Begge står under *Sentiment* på [Positioning & cycle](/positioning). De stemmer ikke i [regimeafstemningen](laerebog/afstemningsmodellen): evidensen er for svag til et 1–6-måneders signal, og begge måler kun det amerikanske marked.

## Regneeksempel

> **Eksempel:** En uge med uro. Tallene er opfundne.

**AAII.** Ugens undersøgelse viser 22 % bullish, 30 % neutral og 48 % bearish. Andelene summerer til 100 %:

$$
\text{spread} = 0.22 - 0.48 = -0.26 = -26 \text{ procentpoint}
$$

Der er 2.000 tidligere uger i historikken, og i 120 af dem var spreadet lavere end $-26$:

$$
\text{percentil} = 100 \cdot \frac{120}{2000} = 6.0
$$

Med standardindstillingen er 6,0 under grænsen på {{settings:sentiment.aaii_extreme_pct}}, så læsningen får flaget *extreme fear*, og måleren er grøn: kontrært støttende.

Antag, at de seneste otte ugers spread var $-5, -8, -12, -10, -15, -18, -22, -26$ procentpoint. 8-ugersgennemsnittet er:

$$
\frac{-5 - 8 - 12 - 10 - 15 - 18 - 22 - 26}{8} = \frac{-116}{8} = -14.5
$$

Den rolige læsning er altså klart negativ, men mindre ekstrem end den seneste uge; stemningen er blevet gradvist dårligere, ikke slået om på én uge.

**Put/call.** Equity-forholdet de seneste ti handelsdage:

| Dag | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| P/C | 0,70 | 0,72 | 0,75 | 0,74 | 0,78 | 0,80 | 0,82 | 0,79 | 0,83 | 0,87 |

$$
\overline{\text{P/C}}_{10} = \frac{0.70 + 0.72 + 0.75 + 0.74 + 0.78 + 0.80 + 0.82 + 0.79 + 0.83 + 0.87}{10} = \frac{7.80}{10} = 0.780
$$

I sammenligningsgrundlaget (de foregående 755 10-dagesgennemsnit med standardvinduet på 756 dage) ligger 700 under 0,780:

$$
\text{percentil} = 100 \cdot \frac{700}{755} = 92.7
$$

Put-handlen er usædvanlig høj; måleren står over det øverste mærke og er grøn.

**Samlet.** Begge målinger peger på frygt. Det er ikke et købssignal, men det er den situation, hvor den kontrære evidens er stærkest: mange har allerede afdækket sig eller solgt, og en positiv overraskelse møder få sælgere. Kombinér med trend, [markedsbredde](laerebog/markedsbredde) og [VIX](laerebog/vix), før du tillægger det vægt.

## Faldgruber og begrænsninger

- **Svag evidens midt i fordelingen.** En percentil på 40 eller 60 betyder næsten intet. Se kun på ekstremerne.
- **Frygt kan blive til mere frygt.** I 2008 var stemningen ekstremt negativ i måneder, før bunden kom. Et *extreme fear*-flag er ikke en bund.
- **Sentiment følger kurserne.** AAII-stemningen er for en stor del en reaktion på de seneste ugers afkast. Den fortæller mere om, hvor vi har været, end hvor vi skal hen.
- **Kort put/call-historik i starten.** Radaren henter kun {{settings:sentiment.putcall_backfill_days}} dages historik første gang. Indtil der er gået omkring to år mere, er vinduet kortere end de nominelle {{settings:sentiment.putcall_lookback_days}} handelsdage, og percentilen rangerer mod et kortere og måske uregelmæssigt stykke historie.
- **Strukturelle skift i optionsmarkedet.** Udbredelsen af kortløbede optioner (0DTE) og privat call-handel har ændret niveauet for put/call-forholdet. Percentilen tilpasser sig over tid, men ikke med det samme.
- **Kun USA.** Begge målinger er amerikanske. Europæisk og dansk sentiment ses ikke.
- **AAII er en lille, selvselekteret gruppe.** Undersøgelsen dækker medlemmer, der vælger at svare; det er ikke et repræsentativt udsnit af investorer.
- **Den enkelte uge rangeres.** AAII-percentilen bygger på den seneste uges spread, som er støjende. Se 8-ugersgennemsnittet og grafen for at vurdere, om ekstremet er vedvarende.

## Videre læsning

- Malcolm Baker og Jeffrey Wurgler: "Investor Sentiment and the Cross-Section of Stock Returns", *Journal of Finance* 61(4), 2006.
- Malcolm Baker og Jeffrey Wurgler: "Investor Sentiment in the Stock Market", *Journal of Economic Perspectives* 21(2), 2007.
- Kenneth L. Fisher og Meir Statman: "Investor Sentiment and Stock Returns", *Financial Analysts Journal* 56(2), 2000.
- Gregory W. Brown og Michael T. Cliff: "Investor Sentiment and the Near-Term Stock Market", *Journal of Empirical Finance* 11(1), 2004.
- Gregory W. Brown og Michael T. Cliff: "Investor Sentiment and Asset Valuation", *Journal of Business* 78(2), 2005.
- David P. Simon og Roy A. Wiggins III: "S&P Futures Returns and Contrary Sentiment Indicators", *Journal of Futures Markets* 21(5), 2001.
- Jun Pan og Allen M. Poteshman: "The Information in Option Volume for Future Stock Prices", *Review of Financial Studies* 19(3), 2006.
