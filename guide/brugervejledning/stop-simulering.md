# Simulér stop og take-profit på dine handler

Radaren beregner et trailing stop og en take-profit for hver aktie og sektor- eller temafond, du ejer (se [Stop, take-profit og positionsstørrelse](laerebog/stop-og-storrelse)). `radar sim exits` svarer på spørgsmålet: hvad var der sket, hvis du havde fulgt reglen på dine egne handler, med de niveauer radaren ville have beregnet på hver dag?

Svaret bliver til virtuelle porteføljer, som du kan sammenligne med dine rigtige og med ACWI på siden [Returns](/returns), og en rapport over hvert salg, reglen ville have foretaget. Det er en simulering af en mekanisk regel, ikke en anbefaling.

## Sådan kører du den

```
uv run radar update            # første gang: henter kurser langt nok tilbage
uv run radar sim exits         # hver af dine rigtige porteføljer, begge varianter
uv run radar sim exits "ASK" --variant overlay
uv run radar sim exits --start 2025-01-02 --end 2026-06-30
uv run radar sim exits --fill same --json
```

- `--variant`: `overlay`, `rules` eller `both` (standard).
- `--start`: start fra det, porteføljen ejede ved lukkekursen den dag (som en [fork](brugervejledning/portefoljer-og-tags#fork-en-kopi-ved-en-dags-lukkekurs)).
- `--end`: stop den dag.
- `--fill`: hvornår et udløst salg handles (se nedenfor).
- `--json` / `--out FIL`: hele rapporten som JSON.

Kommandoen skriver rapporten til `sim-exits.json` i cache-mappens `reports/` og afslutter med et link til *Returns* med de rigtige og de simulerede porteføljer valgt.

## To varianter

| | `overlay` | `rules` |
|---|---|---|
| Dine køb | Som de skete | Som de skete |
| Dine salg | Som de skete | Ignoreres |
| Reglens salg | Kommer oveni | Er de eneste salg |
| Spørgsmålet | Ville reglen have forbedret det, du faktisk gjorde? | Reglen mod din egen salgsdømmekraft |

I `overlay` springes et af dine salg over, hvis reglen allerede har solgt positionen. Har reglen solgt en del, sælges kun resten. Køber du igen senere, starter en ny position med sit eget stop.

Hver rigtig portefølje får én simuleret portefølje pr. variant. De hedder fx *ASK · exits overlay*, har samme skattetype som den rigtige og har tagget `exits-overlay` eller `exits-rules`. En ny kørsel erstatter den forrige kørsel i de samme porteføljer. Omdøber du dem, finder radaren dem stadig.

## Sådan følger simuleringen reglen

Simuleringen følger reglen, som den står i `config/settings.yaml`. Med standarden (`stops.mode: trend`) sælger den ved en lukkekurs under {{settings:stops.trend_sma}}-dages gennemsnittet og har intet kursmål; i appen er samme niveau kun en anledning til gennemgang, men simuleringen viser, hvad det havde givet at handle på det. ATR-stoppet med kursmål, som var reglen indtil oktober 2026, afspilles med `uv run radar sim exits --rule-spec atr-tp`. Resten af dette afsnit beskriver ATR-stoppet.

- **Stop**: højeste justerede lukkekurs siden købet minus k × ATR. Både k og ATR beregnes hver dag ud fra det, radaren vidste den dag.
- **Take-profit**: låses ved lukkekursen på købsdagen og låses igen ved hvert tilkøb. Reglen måler kursmålet fra den aktuelle kurs, så et kursmål, der blev regnet om hver dag, ville altid ligge over kursen og aldrig blive ramt.
- **Udløsning**: en lukkekurs på eller gennem et niveau udløser salg af hele positionen. Niveauerne sammenlignes med justerede kurser, så et udbytte ikke udløser noget.
- **Handel**: med `fill: {{settings:backtest.fill}}` sælges der til næste handelsdags handlede lukkekurs; med `same` til samme dags. Ingen handel sker til en kurs, der ikke var kendt, da beslutningen blev taget.
- **Hvilke beholdninger**: kun dem, radaren giver niveauer i dag, altså aktier og sektor- og temafonde. Brede indeksfonde beholdes som i den rigtige portefølje.
- **Pengene efter et salg** står i {{settings:backtest.park}}, indtil dit næste køb skal betales. Et køb betales først af kontanter, så af de parkerede andele og først derefter af nye penge.
- **Kurtage**: hvert af reglens salg og hver handel med de parkerede penge betaler kurtage efter kontoens kurtageskema (se nedenfor). Dine egne handler beholder de gebyrer, de havde.

### Kurtagen i simuleringen

Har den rigtige konto et kurtageskema (*fees: …* under fanen *Accounts*, se [Kurtage-estimatet](brugervejledning/portefolje#kurtage-estimatet)), betaler simuleringen det, kontoens mægler ville tage:

- procentsatsen for handlens marked, med mindste- og maksimalkurtagen omregnet til handlens valuta med dagens kurs;
- plus mæglerens vekselgebyr (*Currency exchange surcharge*) på handler i en anden valuta end kroner. Simuleringen handler til Yahoos midtkurs, så gebyret er ikke allerede med i kursen, som det er i dine egne rækker.

Uden et skema koster hver handel {{settings:backtest.fee_bps}} basispoint af værdien (`backtest.fee_bps`, kurtage og valutaspread). Det samme gælder en enkelt handel, skemaet ikke kan prissætte: et marked uden regel og uden en regel for *Other markets*, eller ingen valutakurs til at omregne mindstekurtagen. Den handel bliver aldrig gratis, og rapporten tæller den.

En mindstekurtage gør små handler dyre. Dækker pengene fra et salg ikke kurtagen på købet af parkeringsfonden (eller et genkøb), købes der ikke: pengene står som kontanter, og rapporten siger det (*not parked*, *re-entry skipped*). Beholdningerne ved `--start` kopieres uden kurtage, som i en fork.

Hvilken kurtage en kørsel brugte, står i kørslens parametre (`fee_model`): `schedule` med kontoens navn, skabelonen og dens dato og de handler, der faldt tilbage på `fee_bps`, eller `bps` med satsen. Tallet ændrer sig, når du retter skemaet; kør `radar sim exits` igen bagefter.

### Det, radaren vidste på dagen

Hvert input til k er skåret ved dagen:

- **Kurser**: kun til og med dagen. Momentumscoren beregnes mod hele aktieuniverset den dag.
- **Regime**: beregnet ved ugens sidste lukkekurs og brugt hele den følgende uge.
- **Makrodata**: FRED-serier tæller først {{settings:backtest.fred_lag_days}} dag efter deres dato, OECD's ledende indikatorer {{settings:backtest.oecd_lag_days}} dage efter og CAPE og risikopræmie {{settings:backtest.valuation_lag_days}} dage efter.
- **Analytikerkonsensus**: kun den, der var hentet senest den dag.

Mangler et input, flytter det ikke k. Det står som en grund i rapporten og tælles i opsummeringen; det tælles aldrig som 0. Analytikerdata findes kun fra den dag, radaren begyndte at hente dem, så de mangler i det meste af historikken.

### Kurser langt nok tilbage

Reglen skal bruge omkring et års kurser før købet (200-dages gennemsnit, 12-måneders momentum). Derfor henter `radar update` nu kurser fra {{settings:backtest.warmup_days}} dage før din første handel, dog højst {{settings:backtest.max_years}} år tilbage og altid mindst {{settings:history_years}} år. Første gang hentes de berørte tickere forfra; derefter er opdateringen igen trinvis.

## Sådan læser du resultatet

For hver portefølje viser kommandoen tre linjer: den rigtige portefølje og de to simuleringer, med værdi, tidsvægtet afkast (TWR), forskel til ACWI og største fald (drawdown). Derefter følger hvert salg, reglen foretog:

- dagen, niveauet blev ramt, symbolet og om det var stop eller take-profit;
- k den dag, salgsdagen og salgskursen;
- beløbet i kroner;
- **saved**: værdien af de parkerede ACWI-andele minus værdien af positionen, hvis den var beholdt. Begge regnes med udbytte geninvesteret. Et positivt tal betyder, at reglen hjalp.

*saved* opgøres to steder: ved slutningen af perioden og ved dit næste rigtige salg af symbolet (hvis der var et). Opsummeringen tæller, hvor mange salg der hjalp, og hvor ofte et input manglede.

På [Returns](/returns) vælger du porteføljerne med linket fra kommandoen, eller tagget `exits-overlay` mod `exits-rules`.

## Hvilken halvdel af reglen hjælper?

På dine egne handler er der for få salg til at sige meget. `uv run radar study score --exits 6` tester reglen på scorens 15 bedste aktier på hver månedsafslutning i historikken, med begge halvdele, kun stop og kun take-profit. Se [Test momentumscoren på historikken](brugervejledning/scoretest).

## Andre udgaver af reglen

`uv run radar study exits` prøver en fast liste af varianter af reglen på de samme kurve og måler både afkast og risiko (se [Test momentumscoren på historikken](brugervejledning/scoretest#varianter-af-stopreglen)). En variant kan du også afspille på dine egne handler:

```
uv run radar sim exits --rule-spec k5
uv run radar sim exits --rule-spec sma200 --variant rules
```

Varianten får sine egne simulerede porteføljer, fx *ASK · exits rules k5* med tagget `exits-rules-k5`, og sin egen rapport, `sim-exits-k5.json`. Den almindelige kørsel og dens porteføljer røres ikke.

## Begrænsninger

- **Aktieuniverset er dagens liste.** Aktier, der er gået ud af det, mangler i momentumscoren (overlevelsesbias).
- **Makrodata er dagens version.** FRED og OECD reviderer tal, og simuleringen bruger de reviderede.
- **Afstemningen bruger dine nuværende valg** af grupper i regimet.
- **Ingen skat**, og kurtagen er aldrig bedre end skemaet: uden et kurtageskema på kontoen er den et fast skøn ({{settings:backtest.fee_bps}} basispoint), og skabelonerne er mæglernes prislister på en bestemt dato. Skatter som fransk FTT og britisk stempelafgift er ikke med. ACWI står ikke på positivlisten, så parkeringen ville ikke være mulig på en aktiesparekonto som den er. Sæt `backtest.park` til en UCITS-fond på positivlisten, hvis det skal være realistisk.
- **Reglen er ikke tunet til dine handler.** Et godt eller dårligt resultat på få handler siger mere om perioden end om reglen.
