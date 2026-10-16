# Test momentumscoren på historikken

Hvor god er [momentumscoren](laerebog/momentumscore) egentlig til at finde aktier, der klarer sig godt bagefter? Radaren har fire værktøjer til at svare:

| Værktøj | Spørgsmål | Hvor stærkt er svaret? |
|---|---|---|
| `radar study score` | Hvordan klarede de bedst placerede aktier sig de følgende måneder, hver måned, så langt kurshistorikken rækker ({{settings:history_years}} år)? | Bevis (med forbehold) |
| `radar study longrun` | Holder scorens regel over årtier, på brancher og lande uden survivorship bias? | Bevis for reglen, ikke for de enkelte aktier |
| `radar sim picks` og `/hindsight` | Hvad var der sket med en kurv valgt for 1, 3, 6 eller 12 måneder siden? | Et eksempel, til inspiration |
| Papirsporet (`picks-live`) | Hvordan klarer en kurv valgt i dag sig fremover? | Det eneste svar helt uden bagklogskab, men det tager tid |

Det hele er simulering og analyse, ikke rådgivning. Kurvene lander i virtuelle porteføljer og tæller aldrig som dine.

## Testen over alle måneder

```
uv run radar study score                  # 1, 3, 6 og 12 måneder, alle varianter
uv run radar study score --exits 6        # også stopreglen på hver dags top 15 (tager nogle minutter)
uv run radar study score --horizons 3,6 --variants score,r12_1 --no-regime
uv run radar study score --seasoned       # uden aktier noteret under et år på datoen
```

Kommandoen skriver `score-study.json` i cache-mappens `reports/` og viser én tabel pr. horisont:

- **IC** og **t**: rangkorrelationen mellem scoren og afkastet bagefter, i gennemsnit, med et t-tal, der tager højde for overlappende perioder. Et t-tal over cirka 2 betyder, at gennemsnittet næppe er 0 ved et tilfælde.
- **IC>0**: andelen af måneder, hvor scoren pegede den rigtige vej.
- **Q1, Q3, Q5** og **Q5-Q1**: merafkastet mod gennemsnitsaktien for den dårligste, midterste og bedste femtedel, og forskellen mellem bedste og dårligste.
- **top N** og **hit**: merafkastet for de N bedste (standard 15) og andelen af dem, der slog gennemsnitsaktien.
- **holdout IC** og **verdict**: en variants IC i holdout-perioden (fra {{settings:backtest.study_holdout_from}}) og dommen mod scoren. Kun *candidate improvement* tæller som en mulig forbedring.

Under tabellen står scorens IC pr. regime og pr. region, top N i DKK mod ACWI, hvor hurtigt signalet aftager (IC pr. horisont) og hvor stor en del af toppen der skiftes ud hver måned.

Med `--exits 6` følger stopreglen: hver dags 15 bedste beholdt i 6 måneder mod reglen fulgt, med kun stop og kun take-profit, med kurtage på {{settings:backtest.fee_bps}} basispoint pr. handel. Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering).

Metoden og forbeholdene står i [Test af momentumscoren](laerebog/test-af-scoren). Den vigtigste: universet er dagens, så aktier, der er røget ud, mangler, og det får momentum til at se bedre ud.

### Kvalitet og værdi

Den samme test kan køres på [kvalitets- og værdiscoren](laerebog/kvalitetsscore) i stedet for momentum:

```
uv run radar study score --signal qv        # K+V
uv run radar study score --signal quality   # kvalitetsscoren
uv run radar study score --signal value     # værdiscoren
```

Den bruger kun amerikanske aktier med regnskaber fra SEC EDGAR, fordi det er den eneste kilde, der fortæller, hvornår hvert tal blev offentliggjort. På hver månedsafslutning regnes scorerne med appens egen kode af de tal, der var indleveret senest {{settings:backtest.fundamentals_lag_days}} dag før, og kurserne indtil da. En senere rettelse af et regnskab ændrer ikke en tidligere dato. Hent regnskaberne først med `uv run radar fundamentals update --source edgar --all` (kræver en kontakt-e-mail til SEC; se [Regnskaber](brugervejledning/data-og-daekning#regnskaber)). Testen tager 10–15 minutter.

Rapporten hedder `score-study-qv.json` (eller `-quality`, `-value`) og har samme tabeller. Varianterne er de fire kvalitetssøjler hver for sig, de enkelte nøgletal (ROIC, FCF-margin, FCF yield, EBIT/EV, shareholder yield, EBIT/EV mod egen historik), gross profitability (Novy-Marx), Greenblatts magic formula, K+V blandet 1:1 med momentum og momentumscoren selv på de samme aktier. Under tabellerne står rangkorrelationen med momentumscoren: ligger den nær 0 eller under, vælger de to scorer forskellige aktier, og det er den spredning, en portefølje kan få ud af at bruge begge.

> **Bemærk:** Regnskaberne bevæger sig langsomt, og kurshistorikken er kort ({{settings:history_years}} år), så testen bygger på få uafhængige perioder. Dagens S&P 500 er universet, og sektorerne er dagens. Den rene test er [A/B-testen](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum), som kører fremad i tid.

## Testen over årtier

```
uv run radar study longrun                       # begge paneler, 1, 3, 6 og 12 måneder (et halvt minuts tid pr. panel)
uv run radar study longrun --panel countries --horizons 6
uv run radar study longrun --fetch               # hent de lange serier først (det gør radar update også, en gang om måneden)
```

`radar study score` bygger på få år og på dagens aktier. Det er for lidt til at sige, om scorens vægte er de rigtige, og aktier, der er røget ud, mangler. `radar study longrun` stiller derfor det samme spørgsmål til lange månedsserier, som forskere har bygget af alle de aktier, der var noteret på hvert tidspunkt, så de ikke har survivorship bias:

| Panel | Hvad scoren rangerer | Fra | Kilde |
|---|---|---|---|
| *french49* | 49 amerikanske brancher, værdivægtet | 1926 | Kenneth R. French Data Library |
| *countries* | 23 udviklede aktiemarkeder, værdivægtet, i USD | 1986 | JKP Global Factor Data |

Scoren regnes præcis som i appen, bare på måneder: gennemsnittet af percentilerne for 12-1-, 6- og 3-måneders afkast. Varianterne ændrer delene og vægtene (hver del for sig, 12 måneder med den seneste måned, den seneste måned sprunget over, uden 3-måneders delen, vægtene 2:1:1 og 1:1:2). Dommen er den samme som i `radar study score`: en variant er kun en mulig forbedring, når den er bedre både før og i holdout-perioden (fra {{settings:longrun.holdout_from}}), med et t-tal over 2 i holdout-perioden.

Tabellerne har de samme kolonner som `radar study score` plus:

- **eff N**: antallet af uafhængige perioder (datoer divideret med horisonten). Med 6 måneders horisont over 99 år er det omkring 200, mod omkring 15 i `radar study score`.
- **vs mkt**: top N mod panelets marked (det amerikanske marked eller JKP's verdensmarked) i stedet for gennemsnittet af panelet.

Under tabellerne står scorens IC pr. årti, i op- og nedtrend (markedet over eller under sit {{settings:longrun.regime_months}}-måneders gennemsnit) og i og uden for amerikanske recessioner.

Derefter følger **basisrater** for momentum, værdi og kvalitet som lang-kort-faktorer: afkast og t-tal over hele historikken og de seneste 10 år, hvor ofte et 6- og et 12-måneders vindue tabte, det største fald og hvor længe det tog at komme tilbage. Det er de tal, en tilt mod momentum eller værdi bør måles mod, når de korte tests ser lovende ud.

Til sidst en grov **måling af survivorship bias**: den bedste femtedels merafkast i `radar study score` (dagens univers) ved siden af det samme for alle amerikanske aktier uden survivorship bias i de samme måneder (Frenchs momentumdeciler), og den nedskrivning, forskellen svarer til, mod den faste nedskrivning på {{settings:propose.survivorship_haircut|pct}} i porteføljeforslagene.

Rapporten hedder `longrun-study.json` i cache-mappens `reports/`. Den har også de **priorer**, porteføljeforslagene trækker deres forventede merafkast mod: for hver hældning og horisont, hvad den bedste tredjedel af aktierne på de samme egenskaber har givet over gennemsnittet i udviklede markeder, uden for USA og i USA siden {{settings:propose.prior.since}}, i alt og pr. trend. Se [Porteføljeforslag](laerebog/portefoeljeforslag#sådan-gør-radaren).

> **Bemærk:** Det er brancher og lande, ikke aktier. Det, der kan overføres, er reglen (vinduer og vægte), basisraterne og ideen om rotation, ikke et tal for en aktiekurv: enkeltaktier svinger mere, og deres momentum er stærkere og krakker hårdere. JKP-serierne opdateres omkring en gang om året og slutter derfor tidligere end Frenchs. Kilderne står i [Datakilder og licenser](brugervejledning/datalicenser).

## Varianter af stopreglen

```
uv run radar study exits                        # alle varianter, 3 og 6 måneder (tager 10–20 minutter)
uv run radar study exits --variants k5,sma200 --no-reentry
```

Hver månedsafslutnings 15 bedste aktier beholdes og sammenlignes med de samme køb, hvor en variant af reglen sælger, og pengene står i {{settings:backtest.park}} bagefter. Varianterne er reglen som i dag, uden take-profit, med bredere $k$, med ATR over 63 dage, uden strammere stop, når kursen er strakt, med et fast fald på 20 eller 30 % fra toppen og med salg ved en lukkekurs under 100- eller 200-dages gennemsnittet. Den variant, der klarer sig bedst før holdout-perioden, prøves også med genkøb: når aktien igen er i optrend med en stærk score, købes den tilbage for de parkerede penge. Til sammenligning vises to rækker helt uden salgsregel, hvor kun en del af pengene står i kurven og resten i {{settings:backtest.park}} fra starten (*mix75* og *mix50*): de viser, hvad den samme risikoreduktion koster ved at gøre positionen mindre i stedet. Se [Virker stop på momentumaktier?](laerebog/stop-og-storrelse#virker-stop-på-momentumaktier).

For hver variant vises afkastet og forskellen til at beholde, med t-tal, andelen af datoer hvor den hjalp, det 10 % dårligste udfald, gennemsnitligt og værste største fald (max drawdown) og antal salg pr. kurv. En variant **består**, når den både før og i holdout-perioden højst koster 2 procentpoint afkast pr. 6 måneder (1 pr. 3 måneder), skærer mindst en fjerdedel af det gennemsnitlige største fald væk og løfter det 10 % dårligste udfald. Ellers står der, hvorfor den ikke består. Rapporten ligger i `exit-study.json` i cache-mappens `reports/`.

## Pengene fra et salg i en ny aktie

```
uv run radar study redeploy                          # 6 og 12 måneder, alle varianter (tager 30–60 minutter)
uv run radar study redeploy --horizons 6 --max-per-sector 4 --buffer 2
uv run radar study redeploy --arms tp-only-redeploy,rotate-tp-only
```

`radar study exits` parkerer pengene fra et salg i {{settings:backtest.park}}. Det er en ulempe for reglen, især for take-profit: den flytter penge fra en aktie, der stiger, til et marked, der i gennemsnit stiger mindre. `radar study redeploy` stiller spørgsmålet anderledes: hvad nu, hvis pengene i stedet købte den næste aktie med høj momentumscore?

Kurvene er de samme: hver månedsafslutnings 15 bedste, lige vægte, kurtage på {{settings:backtest.fee_bps}} basispoint pr. handel. Ved et salg købes den aktie med højest score den dag, salget blev udløst, som ikke allerede er i kurven, ikke er solgt inden for de seneste 21 handelsdage (`--cooldown`), er i optrend (slå fra med `--no-trend`) og passer ind under lofterne pr. sektor og region (`--max-per-sector`, `--max-per-group`). Alle pengene fra salget går i den ene aktie. Er der ingen kandidat, parkeres pengene, og det står i rapporten.

Varianterne kommer i par, så hver gevinst kan føres tilbage til sin årsag:

| Variant | Salg | Pengene | Månedlig rotation |
|---|---|---|---|
| *sma200-park* / *sma200-redeploy* | lukkekurs under 200-dages gennemsnittet (som i dag) | {{settings:backtest.park}} / ny aktie | nej |
| *atr-tp-park* / *atr-tp-redeploy* | ATR-stop og take-profit | {{settings:backtest.park}} / ny aktie | nej |
| *tp-only-park* / *tp-only-redeploy* | kun take-profit | {{settings:backtest.park}} / ny aktie | nej |
| *rotate* | intet salg på reglen | ny aktie | ja |
| *rotate-sma200*, *rotate-atr-tp*, *rotate-tp-only* | som ovenfor | ny aktie | ja |
| *mix50*, *acwi* | ingen (til sammenligning) | – | nej |

Rotationen sælger ved hver månedsafslutning en aktie, der er faldet uden for de 3 × 15 = 45 bedste (`--buffer`), og køber den næste på samme måde. Bufferen gør, at en aktie ikke sælges, fordi den falder et par pladser.

For hver variant vises afkastet og forskellen til at beholde kurven, **Sharpe** og **Sortino** (afkast over ECB's indlånsrente pr. enhed risiko, Sortino kun med udsvingene nedad), **Calmar** (årligt afkast pr. største fald), største fald, **IR** (informationsratio: merafkast mod ACWI pr. enhed afvigelse fra ACWI), antal handler og kurtage, og Sharpe mod tvillingen (*redeploy* mod *park*, en rotation med regel mod rotationen alene) med t-tal. En variant er **better**, når dens gennemsnitlige Sharpe både før og i holdout-perioden er højere end at beholde kurven og højere end tvillingens, og den højst koster 2 procentpoint afkast pr. 6 måneder. Rapporten ligger i `redeploy-study.json` i cache-mappens `reports/`.

> **Bemærk:** Universet er dagens. Hver aktie, pengene flyttes til, er en, der overlevede til i dag, og det får det at flytte pengene til at se bedre ud end at beholde. Skat er ikke regnet med: i frie midler realiserer hvert salg en gevinst eller et tab, på aktiesparekontoen (lagerbeskatning) koster flere handler ikke ekstra skat. Antallet af handler står i tabellen, så du kan vurdere det. Baggrunden står i [Virker stop på momentumaktier?](laerebog/stop-og-storrelse#pengene-fra-et-salg).

## En kurv valgt på en dag i fortiden

```
uv run radar sim picks-candidates --asof 6M                       # universet, som radaren så det for 6 måneder siden
uv run radar sim picks --asof 6M --rule top-n --n 15 --max-per-sector 3 --name test-6m
uv run radar sim picks --asof 2026-04-15 --picks mine.json --name min-kurv
uv run radar sim picks --rerun test-6m                            # samme kurv igen på nyere kurser
```

- `--asof`: `1M`, `3M`, `6M`, `1Y` tilbage fra de seneste kurser, `today` eller en dato.
- `--rule top-n` tager scorens egne N bedste; `--picks FIL` tager din egen liste (JSON med `ticker` eller et blindt `id`, valgfrit `weight` og `why`).
- `--max-per-sector`, `--max-per-group` (pr. region), `--trend` og `--weighting equal|score` styrer sammensætningen.
- Kurven købes til næste handelsdags lukkekurs med kurtage på {{settings:backtest.fee_bps}} basispoint.

Hver kurv bliver til virtuelle porteføljer med tagget `picks`: *‹navn› · hold* (beholdt), *‹navn› · exits* (stopreglen fulgt) og *‹navn› · control* (scorens egne N bedste med de samme lofter, når din kurv er en anden). Kommandoen viser afkastet i DKK med alle omkostninger mod ACWI og mod gennemsnitsaktien, kurvens placering blandt {{settings:backtest.random_baskets}} tilfældige kurve af samme størrelse og med samme lofter, og scorens test på netop den dag. Linket går til [Returns](/returns) med porteføljerne valgt. Rapporten ligger i `sim-picks/` i cache-mappens `reports/`.

> **Bemærk:** Aktier i en valuta uden en kurs til DKK i radaren kan ikke købes i en simulering. De står i listen med `dkk: false` og springes over.

### Hindsight-kurve med Claude

`/hindsight` i Claude Code (se [Claude Code-skills](brugervejledning/claude-code#hindsight)) stiller spørgsmålene for dig: hvor langt tilbage, om kurven skal vælges af scoren alene, af scoren og dine markedssyn eller af scoren og Claudes vurdering, hvor mange aktier og hvor spredt. Derefter vælger, kører og beskriver Claude kurven i `research/hindsight/` i datamappen.

Claude kender markedet frem til sin egen vidensgrænse. En kurv valgt af Claude til en dag *før* den grænse kan være påvirket af, hvad Claude ved skete bagefter. Derfor vælger Claude på sådan en dag blindt (aktierne hedder C001, C002 …), og notatet siger, at det ikke helt kan udelukkes. Dage efter grænsen er rene. Dine markedssyn bruges kun, hvis de var oprettet senest på dagen.

## Papirsporet

Den eneste test helt uden bagklogskab og overlevelsesbias er at vælge i dag og vente. Den månedlige brief (se [Månedsbriefen](brugervejledning/maanedsbrief)) opretter derfor en gang om måneden en kurv af scorens 15 bedste, højst 4 pr. sektor, med tagget `picks-live`, og bringer de tidligere kurve up to date. Du kan gøre det samme selv:

```
uv run radar sim picks --asof today --rule top-n --n 15 --max-per-sector 4 --name live-2026-10 --tag picks-live
uv run radar sim picks --rerun tag:picks-live
uv run radar performance --tag picks-live
```

Med `--asof today` rangeres kurven ved den forrige lukkekurs og købes ved den seneste, så intet købes til en kurs, der ikke var kendt.
