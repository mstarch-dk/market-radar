# Test momentumscoren på historikken

Hvor god er [momentumscoren](laerebog/momentumscore) egentlig til at finde aktier, der klarer sig godt bagefter? Radaren har tre værktøjer til at svare:

| Værktøj | Spørgsmål | Hvor stærkt er svaret? |
|---|---|---|
| `radar study score` | Hvordan klarede de bedst placerede aktier sig de følgende måneder, hver måned i fem år? | Bevis (med forbehold) |
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

Kommandoen skriver `reports/score-study.json` og viser én tabel pr. horisont:

- **IC** og **t**: rangkorrelationen mellem scoren og afkastet bagefter, i gennemsnit, med et t-tal, der tager højde for overlappende perioder. Et t-tal over cirka 2 betyder, at gennemsnittet næppe er 0 ved et tilfælde.
- **IC>0**: andelen af måneder, hvor scoren pegede den rigtige vej.
- **Q1, Q3, Q5** og **Q5-Q1**: merafkastet mod gennemsnitsaktien for den dårligste, midterste og bedste femtedel, og forskellen mellem bedste og dårligste.
- **top N** og **hit**: merafkastet for de N bedste (standard 15) og andelen af dem, der slog gennemsnitsaktien.
- **holdout IC** og **verdict**: en variants IC i holdout-perioden (fra {{settings:backtest.study_holdout_from}}) og dommen mod scoren. Kun *candidate improvement* tæller som en mulig forbedring.

Under tabellen står scorens IC pr. regime og pr. region, top N i DKK mod ACWI, hvor hurtigt signalet aftager (IC pr. horisont) og hvor stor en del af toppen der skiftes ud hver måned.

Med `--exits 6` følger stopreglen: hver dags 15 bedste beholdt i 6 måneder mod reglen fulgt, med kun stop og kun take-profit, med kurtage på {{settings:backtest.fee_bps}} basispoint pr. handel. Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering).

Metoden og forbeholdene står i [Test af momentumscoren](laerebog/test-af-scoren). Den vigtigste: universet er dagens, så aktier, der er røget ud, mangler, og det får momentum til at se bedre ud.

## Varianter af stopreglen

```
uv run radar study exits                        # alle varianter, 3 og 6 måneder (tager 10–20 minutter)
uv run radar study exits --variants k5,sma200 --no-reentry
```

Hver månedsafslutnings 15 bedste aktier beholdes og sammenlignes med de samme køb, hvor en variant af reglen sælger, og pengene står i {{settings:backtest.park}} bagefter. Varianterne er reglen som i dag, uden take-profit, med bredere $k$, med ATR over 63 dage, uden strammere stop, når kursen er strakt, med et fast fald på 20 eller 30 % fra toppen og med salg ved en lukkekurs under 100- eller 200-dages gennemsnittet. Den variant, der klarer sig bedst før holdout-perioden, prøves også med genkøb: når aktien igen er i optrend med en stærk score, købes den tilbage for de parkerede penge. Til sammenligning vises to rækker helt uden salgsregel, hvor kun en del af pengene står i kurven og resten i {{settings:backtest.park}} fra starten (*mix75* og *mix50*): de viser, hvad den samme risikoreduktion koster ved at gøre positionen mindre i stedet. Se [Virker stop på momentumaktier?](laerebog/stop-og-storrelse#virker-stop-på-momentumaktier).

For hver variant vises afkastet og forskellen til at beholde, med t-tal, andelen af datoer hvor den hjalp, det 10 % dårligste udfald, gennemsnitligt og værste største fald (max drawdown) og antal salg pr. kurv. En variant **består**, når den både før og i holdout-perioden højst koster 2 procentpoint afkast pr. 6 måneder (1 pr. 3 måneder), skærer mindst en fjerdedel af det gennemsnitlige største fald væk og løfter det 10 % dårligste udfald. Ellers står der, hvorfor den ikke består. Rapporten ligger i `reports/exit-study.json`.

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

For hver variant vises afkastet og forskellen til at beholde kurven, **Sharpe** og **Sortino** (afkast over ECB's indlånsrente pr. enhed risiko, Sortino kun med udsvingene nedad), **Calmar** (årligt afkast pr. største fald), største fald, **IR** (informationsratio: merafkast mod ACWI pr. enhed afvigelse fra ACWI), antal handler og kurtage, og Sharpe mod tvillingen (*redeploy* mod *park*, en rotation med regel mod rotationen alene) med t-tal. En variant er **better**, når dens gennemsnitlige Sharpe både før og i holdout-perioden er højere end at beholde kurven og højere end tvillingens, og den højst koster 2 procentpoint afkast pr. 6 måneder. Rapporten ligger i `reports/redeploy-study.json`.

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

Hver kurv bliver til virtuelle porteføljer med tagget `picks`: *‹navn› · hold* (beholdt), *‹navn› · exits* (stopreglen fulgt) og *‹navn› · control* (scorens egne N bedste med de samme lofter, når din kurv er en anden). Kommandoen viser afkastet i DKK med alle omkostninger mod ACWI og mod gennemsnitsaktien, kurvens placering blandt {{settings:backtest.random_baskets}} tilfældige kurve af samme størrelse og med samme lofter, og scorens test på netop den dag. Linket går til [Returns](/returns) med porteføljerne valgt. Rapporten ligger i `reports/sim-picks/`.

> **Bemærk:** Aktier i en valuta uden en kurs til DKK i radaren kan ikke købes i en simulering. De står i listen med `dkk: false` og springes over.

### Hindsight-kurve med Claude

`/hindsight` i Claude Code (se [Claude Code-skills](brugervejledning/claude-code#hindsight)) stiller spørgsmålene for dig: hvor langt tilbage, om kurven skal vælges af scoren alene, af scoren og dine markedssyn eller af scoren og Claudes vurdering, hvor mange aktier og hvor spredt. Derefter vælger, kører og beskriver Claude kurven i `research/hindsight/`.

Claude kender markedet frem til sin egen vidensgrænse. En kurv valgt af Claude til en dag *før* den grænse kan være påvirket af, hvad Claude ved skete bagefter. Derfor vælger Claude på sådan en dag blindt (aktierne hedder C001, C002 …), og notatet siger, at det ikke helt kan udelukkes. Dage efter grænsen er rene. Dine markedssyn bruges kun, hvis de var oprettet senest på dagen.

## Papirsporet

Den eneste test helt uden bagklogskab og overlevelsesbias er at vælge i dag og vente. Den månedlige brief (se [Månedsbriefen](brugervejledning/maanedsbrief)) opretter derfor en gang om måneden en kurv af scorens 15 bedste, højst 4 pr. sektor, med tagget `picks-live`, og bringer de tidligere kurve up to date. Du kan gøre det samme selv:

```
uv run radar sim picks --asof today --rule top-n --n 15 --max-per-sector 4 --name live-2026-10 --tag picks-live
uv run radar sim picks --rerun tag:picks-live
uv run radar performance --tag picks-live
```

Med `--asof today` rangeres kurven ved den forrige lukkekurs og købes ved den seneste, så intet købes til en kurs, der ikke var kendt.
