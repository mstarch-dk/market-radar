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

Kommandoen skriver rapporten til `reports/sim-exits.json` og afslutter med et link til *Returns* med de rigtige og de simulerede porteføljer valgt.

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

- **Stop**: højeste justerede lukkekurs siden købet minus k × ATR. Både k og ATR beregnes hver dag ud fra det, radaren vidste den dag.
- **Take-profit**: låses ved lukkekursen på købsdagen og låses igen ved hvert tilkøb. Reglen måler kursmålet fra den aktuelle kurs, så et kursmål, der blev regnet om hver dag, ville altid ligge over kursen og aldrig blive ramt.
- **Udløsning**: en lukkekurs på eller gennem et niveau udløser salg af hele positionen. Niveauerne sammenlignes med justerede kurser, så et udbytte ikke udløser noget.
- **Handel**: med `fill: {{settings:backtest.fill}}` sælges der til næste handelsdags handlede lukkekurs; med `same` til samme dags. Ingen handel sker til en kurs, der ikke var kendt, da beslutningen blev taget.
- **Hvilke beholdninger**: kun dem, radaren giver niveauer i dag, altså aktier og sektor- og temafonde. Brede indeksfonde beholdes som i den rigtige portefølje.
- **Pengene efter et salg** står i {{settings:backtest.park}}, indtil dit næste køb skal betales. Et køb betales først af kontanter, så af de parkerede andele og først derefter af nye penge.

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

## Begrænsninger

- **Aktieuniverset er dagens liste.** Aktier, der er gået ud af det, mangler i momentumscoren (overlevelsesbias).
- **Makrodata er dagens version.** FRED og OECD reviderer tal, og simuleringen bruger de reviderede.
- **Afstemningen bruger dine nuværende valg** af grupper i regimet.
- **Ingen skat og ingen kurtage** på reglens handler. ACWI står ikke på positivlisten, så parkeringen ville ikke være mulig på en aktiesparekonto som den er. Sæt `backtest.park` til en UCITS-fond på positivlisten, hvis det skal være realistisk.
- **Reglen er ikke tunet til dine handler.** Et godt eller dårligt resultat på få handler siger mere om perioden end om reglen.
