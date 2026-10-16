# Kvalitet og værdi

Siden [Quality & value](/quality) rangerer aktierne på deres regnskaber i stedet for deres kurser. Den stiller to spørgsmål: er det en god forretning (**kvalitetsscoren**), og hvad koster den i forhold til, hvad den tjener (**værdiscoren**)? Det er et andet blik end momentum, i ånden fra Graham, Buffett og Grantham: frit cash flow, høj og stabil forrentning af kapitalen, en sund balance, udbytte og en rimelig pris.

Baggrunden står i [Kvalitet og værdi: Graham, Buffett og Grantham](laerebog/kvalitet-og-vaerdi), og metoden præcist i [Radarens kvalitets- og værdiscore](laerebog/kvalitetsscore).

> **Bemærk:** En billig aktie kan være billig af en god grund (en værdifælde). Læs værdiscoren sammen med kvalitetsscoren, og begge med historien bag tallene. Det er analyse, ikke rådgivning.

## Før der er noget at se

Scorerne kræver regnskaber. Den daglige opdatering henter dem lidt ad gangen (højst {{settings:fundamentals.yahoo.max_per_run}} aktier fra Yahoo og {{settings:fundamentals.edgar.max_per_run}} fra SEC EDGAR pr. kørsel), så første gang tager det nogle dage, før alle regioner er dækket. Vil du have det hele med det samme:

```
uv run radar fundamentals update --all
uv run radar report
```

Amerikanske regnskaber fra EDGAR kræver, at du har skrevet en kontakt-e-mail på siden [Data & coverage](/data) (SEC beder om det). Uden den bruges Yahoos regnskaber for de amerikanske selskaber også. Se [Regnskaber](brugervejledning/data-og-daekning#regnskaber).

## Sådan læser du siden

Siden har én sektion pr. region, de samme fire som på [Momentum](/momentum). Øverst vælger du, hvad der rangeres efter (*Rank by*):

- *Quality + value* (standard): K+V, gennemsnittet af de to scorer.
- *Quality*: kun kvalitetsscoren.
- *Value*: kun værdiscoren.

Hver region viser sine top {{settings:fundamentals.top_n}}. Sæt flueben ved *every scored stock* for at se alle aktier med en score. Valget står i adressen (`?by=value`), så du kan gemme det som bogmærke.

Scorerne er percentiler blandt aktier i **samme sektor på tværs af alle regioner**: en dansk medicinalaktie sammenlignes med medicinalaktier i USA, Europa og Asien, ikke med danske banker. Har sektoren færre end {{settings:fundamentals.min_sector_peers}} aktier med et nøgletal, bruges alle aktier. Banker og forsikringsselskaber har deres eget sæt nøgletal og sammenlignes kun med hinanden; de er mærket *bank/insurer* i kolonnen *Sector*.

Under overskriften for hver region står dækningen: hvor mange af regionens aktier der har en kvalitets- og en værdiscore, og hvor mange der regnes fra EDGAR og fra Yahoo. *NEW* markerer navne, der er nye i top {{settings:fundamentals.top_n}} siden sidste øjebliksbillede, og under dækningen står de navne, der er faldet ud.

## Kolonnerne

| Kolonne | Indhold |
|---|---|
| *#* | Placering i regionen efter det valgte mål |
| *Company*, *Sector* | Navn, ticker og sektor |
| *K+V* | Gennemsnittet af kvalitets- og værdiscoren (kun når begge findes) |
| *Quality* | Kvalitetsscoren 0–100: lønsomhed, holdbarhed (moat), balance og udbytterække |
| *Value* | Værdiscoren 0–100: FCF yield, EBIT/EV, shareholder yield og prisen mod egen historik |
| *Basis* | Hvor mange af de fire søjler og fire værdinøgletal scorerne bygger på, fx *4/4 · 3/4* |
| *Momentum* | Aktiens momentumscore i regionen, så du kan læse de to sammen |
| *ROIC* | Afkast på den investerede kapital |
| *ND/EBITDA* | Nettogæld / EBITDA; negativ = flere kontanter end gæld |
| *Div. years* | År i træk med et udbytte, der ikke blev sat ned (højst 10) |
| *FCF yield* | Frit cash flow de seneste 12 måneder / markedsværdi |
| *EV/EBIT* | Hvad hele forretningen koster pr. krone driftsresultat |
| *Sh. yield* | Shareholder yield: udbytte + aktieopkøb − nyudstedelser, i forhold til markedsværdien |
| *Statements* | Kilden (EDGAR eller Yahoo) og den seneste periode, tallene når frem til |

Under *Columns* kan du slå søjlerne enkeltvis til (*Profit.*, *Durab.*, *Balance*, *Record*), og nøgletallene bag dem: FCF-margin, ROE, spredning i bruttoavance, jævn vækst, omsætningsvækst, rentedækning, EBIT/EV mod egen historik og P/B.

En manglende værdi er en streg, aldrig 0. En aktie uden regnskaber eller med for få tal er ikke på listen.

## Kvalitet og værdi andre steder

- **[Momentum](/momentum)** og **[Holdings & watchlist](/me)** har kolonnerne *Quality* og *Value*. *K+V*, *FCF yield*, *EV/EBIT*, *ROIC* og *Statements* kan slås til under *Columns*.
- **Tickerprofilen** har kortet *Quality & value* med alle nøgletallene, deres percentiler og regnskabsårene. Se [Tickerprofilen](brugervejledning/tickerprofil#quality-value-aktier).
- **Claude-skills** læser scorerne i `summary.json` og `uv run radar info TICKER`.

## A/B-testen

Nederst på siden står A/B-testen: tre virtuelle kurve, der købes på scorerne fremad i tid, så man kan se, om kvalitet og værdi klarer sig anderledes end momentum, og om de to spreder risikoen. Klik *Start the A/B test* for at starte den. Det svarer til `uv run radar abtest start`.

Når testen kører, viser panelet:

- kurvenes afkast mod ACWI fra første køb, som graf og tabel
- korrelationen mellem kurvenes ugentlige afkast (kræver {{settings:risk.min_weeks}} uger)
- hver kurvs seneste udvalg med datoen og omsætningen (*turnover*), og hvornår næste udvalg kommer

Linket *Open on the Returns page* åbner de tre kurve på siden [Returns](/returns) med tagget `ab-qvm`. Reglerne for testen står i [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum).

## Tips

- **Høj kvalitet, lav værdi** er ofte gode forretninger, som markedet allerede har set. **Lav kvalitet, høj værdi** er de billige, der kan være billige af en grund. Det interessante er ofte dem, der scorer højt på begge.
- **Kvalitet og momentum sammen.** En aktie med høj kvalitetsscore og stigende momentum er en god forretning, som markedet er ved at opdage. Sortér på *K+V*, og filtrér *Momentum* over 60.
- **Diversifikation.** Værdi og momentum har historisk været negativt korrelerede. Aktier fra denne side kan sprede en portefølje, der ellers er bygget på momentum. Se [Diversifikation og korrelation](laerebog/diversifikation#værdi-og-momentum-side-om-side).
- **Tjek kilden.** Står der *Yahoo* under *Statements* for et selskab uden for USA, bygger holdbarheden ofte på kun fire år. *Basis* viser, når en score hviler på færre dele.
