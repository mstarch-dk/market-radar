# Afkast over tid

Siden [Returns](/returns) viser, hvordan dine porteføljer har udviklet sig over tid i DKK, ved siden af MSCI ACWI over samme periode. Du kan sammenligne rigtige og virtuelle porteføljer og grupper af porteføljer med samme tag, fra en fælles startdato. Det er siden til spørgsmål som "slår min aktiesparekonto verdensindekset?" og "klarede min momentumtest sig bedre end originalen?".

## Det viser siden

Siden har to faner: *Returns* med grafen og tabellen nedenfor, og *Attribution*, der forklarer forskellen til ACWI (se [Attribution](#attribution-hvorfor-du-slog-eller-haltede-efter-acwi)). Afkrydsningen af porteføljer og datoen *From* gælder for begge.

- **Grafen** *Growth of 100 (time-weighted, DKK)*: hver linje er et tidsvægtet indeks, der starter på 100 på den fælles startdato. Linjen *ACWI (DKK)* er verdensindekset fra samme dag. En linje over ACWI's har klaret sig bedre.
- **Tabellen** med én række pr. linje:

| Kolonne | Betyder |
|---|---|
| *Portfolio* | Porteføljen eller tagget (et tag viser sine porteføljer i parentes) |
| *From* | Første dag, porteføljen kunne værdisættes i perioden |
| *Value (DKK)* | Værdien ved seneste lukkekurs |
| *TWR* | Tidsvægtet afkast i perioden |
| *TWR p.a.* | Det samme pr. år (kun med mindst et års data) |
| *MWR p.a.* | Pengevægtet afkast pr. år (kun med mindst et års data) |
| *ACWI* | ACWI's afkast i DKK over samme periode |
| *vs ACWI* | TWR minus ACWI's, i procentpoint |
| *Max drawdown* | Største fald fra en top i det tidsvægtede indeks |
| *Cash* | `ledger` eller `implicit` (se [Med eller uden kontantrækker](#med-eller-uden-kontantrækker)) |

Kolonnerne *Volatility p.a.*, *3m*, *YTD* og *1y* er skjult og kan slås til i tabellens værktøjslinje.

- **Noter** under tabellen: huller i data, en senere start, en pengestrøm med ukendt værdi og lignende, pr. linje.

## Tidsvægtet og pengevægtet afkast

**Tidsvægtet afkast (TWR)** måler, hvordan investeringerne klarede sig, uafhængigt af hvornår og hvor mange penge du satte ind eller tog ud. Det er den retfærdige måde at sammenligne to porteføljer på, eller en portefølje med ACWI. Radaren regner afkastet dag for dag og kæder dagene sammen til et indeks. Penge, der kommer ind, tæller fra dagens start, og penge, der går ud, ved dagens slutning. Køber du for nye penge ved lukkekursen, står de altså stille den dag: en dags "kontantslæb", ikke en fejl.

**Pengevægtet afkast (MWR)** er den årlige rente, dine faktiske penge har givet, med timingen medregnet (beregnet som XIRR). Er MWR højere end TWR, satte du penge ind før gode perioder; er den lavere, før dårlige. Radaren viser først MWR, når porteføljen har mindst et års historik (grænsen ligger i koden), fordi en årlig rente beregnet på få uger mest er støj.

Teorien står i [Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr).

## ACWI med de samme pengestrømme

Ud over ACWI's eget afkast regner radaren også, hvad "ACWI med de samme pengestrømme" ville være værd: de samme ind- og udbetalinger (eller køb og salg, hvis porteføljen ikke har kontantrækker) lagt i ACWI på de samme dage. Det er den passive tvilling til din portefølje og grundlaget for ACWI's pengevægtede afkast.

Tallene er med i `uv run radar performance --json` (`acwi_mwr_ann` og serien `acwi_same_flows_dkk`). Tabellen på siden viser ACWI's tidsvægtede afkast, som er det samme uanset pengestrømmene. Er en udbetaling større end tvillingens værdi, eller er værdien af en pengestrøm ukendt, stopper serien, og noterne siger hvorfor.

## Med eller uden kontantrækker

Kolonnen *Cash* fortæller, hvordan pengene ind og ud er opgjort:

- `ledger`: porteføljen har ind- eller udbetalinger. Værdien er beholdning plus kontanter, og kun ind- og udbetalinger tæller som penge ind og ud. Køb og salg flytter blot penge mellem kontanter og papirer.
- `implicit`: porteføljen har ingen kontantrækker. Hvert køb regnes som nye penge og hvert salg (og hver indtægt) som penge taget ud.

Begge giver et korrekt TWR. Kontantrækker gør især MWR og værdien mere retvisende, hvis du har penge stående uinvesteret. Se [Portefølje: handler, kontanter og import](brugervejledning/portefolje).

## Huller, aldrig nuller

Radaren værdisætter hver portefølje ved hver lukkekurs i ACWI's kalender. Mangler et papir en kurs (radaren fylder højst fem handelsdage frem) eller en valutakurs til DKK, er dagens værdi ukendt. Den dag bliver et hul i grafen, og afkastet kædes hen over hullet. En manglende kurs tælles aldrig som 0.

- Kurshistorikken går mindst {{settings:history_years}} år tilbage og ellers til {{settings:backtest.warmup_days}} dage før din første handel (højst {{settings:backtest.max_years}} år). Rækker fra før den kan ikke værdisættes. Serien begynder den første dag, alt kan værdisættes, med det, du ejede da.
- En handel, hvis værdi i DKK er ukendt, bryder kæden den dag. Radaren siger det i noterne, og de pengevægtede tal udelades.
- Med udbyttepolitikken `reinvested` (standard) bruges udbyttejusterede kurser; med `cash` de handlede kurser plus dine udbytterækker.

## Sammenlign porteføljer og grupper

Linjen *Compare:* over grafen har et flueben for hver portefølje med rækker og for hvert tag:

- **Porteføljer**: sæt flueben ved dem, du vil se. Uden valg viser siden hver af dine rigtige porteføljer.
- **Tags**: et tag lægger sine porteføljer sammen til én linje (*pooled*). To tags giver en A/B-test.
- *your real portfolios* nulstiller valget.

Alle linjer starter fra en **fælles dato**: som standard den seneste af linjernes første dage, så ingen linje mangler data i begyndelsen. Med feltet *From* vælger du selv en dato; *the common start* nulstiller den. En portefølje, der fandtes før startdatoen, starter med sin værdi den dag, som om den var sat ind da.

Valget står i adressen: `?pf=` for linjerne (fx `?pf=3,7` eller `?pf=tag:momentum-a,tag:momentum-b`) og `?from=` for startdatoen (fx `?from=2026-06-30`). Laver du en fork på siden [Portfolio](/portfolio), åbner siden selv med originalen og kopien fra forkens dato. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

> **Tip:** En fork og originalen starter lige, fordi kopien bygges af originalens beholdninger ved samme lukkekurs. Derfor er det en ren måde at teste en ændring på: lav ændringen i kopien, og se hvilken linje der ligger højest efter nogle måneder.

## Attribution: hvorfor du slog eller haltede efter ACWI

Fanen *Attribution* forklarer forskellen mellem de afkrydsede porteføljers tidsvægtede afkast og ACWI's i perioden fra *From* (tom: hele historikken). Flere afkrydsede porteføljer eller tags lægges sammen til én. Det hele er i DKK.

- **Fra ACWI til dit afkast** (*From ACWI to your return*) er et vandfald, hvor søjlerne lægges oven i hinanden og ender i forskellen til ACWI:
  - *Trading and fees*: det, der sker inden for en dag (køb over eller salg under lukkekursen) og gebyrerne.
  - *Benchmark proxies vs ACWI*: ACWI's segmenter måles med ETF'er, der følger MSCI World-sektorer og landeindeks, ikke ACWI's egne segmenter. Forskellen mellem de ETF'er og ACWI står for sig selv i stedet for at gemme sig i effekterne.
  - *Allocation* (allokering): at have mere eller mindre end ACWI i et segment, der gik bedre eller dårligere end ACWI som helhed. Kontanter er et segment med 0 % afkast, så deres træk på afkastet tæller her.
  - *Selection* (udvælgelse): at vælge papirer inden for et segment, der slog segmentet, målt i lokal valuta.
  - *Interaction* (samspil): udvælgelse i et segment, du samtidig over- eller undervægtede.
  - *Currency* og *Cross*: valutaeffekten mod DKK og den lille rest, der opstår, når valuta og lokale afkast forrentes sammen.
- **Efter sektor og efter region** (*By sector*, *By region*): tabellen viser hvert segment med gennemsnitsvægt, afkast og effekter, de største først. Under den viser et søjlediagram effekterne måned for måned, over nul når de hjalp og under nul når de trak ned. Tallene står i tabellen under diagrammet.
- **Valuta** (*Currency*): effekten pr. valuta.
- **Dygtighed eller held** (*Skill or luck*): alfa pr. år fra en ugentlig regression på French's faktorer for udviklede markeder, med t-tal og antal uger. Feltet viser også, hvor mange måneder mere det vil tage at nå t = 2, hvis alfaen og støjen holder sig. Under t = 2 kan alfa ikke skelnes fra held.

Der er ingen attribution under {{settings:attribution.min_months}} måneders historik i perioden og ingen regression under {{settings:attribution.min_weeks}} uger; noterne siger hvorfor. Hver beholdning placeres, som den er i dag, også for tidligere måneder. En fond, der ikke kan ses igennem, er sit eget segment med sit eget afkast. En dag, hvor en kurs, en vægt eller en valutakurs mangler, tælles ikke med, og antallet står under tabellen. Før den første ugentlige optegnelse af ACWI's vægte regnes vægtene tilbage fra den (*back-drifted*); de måneder er markeret.

## Kommandolinjen

`uv run radar performance` viser det samme som tabellen for hver af dine rigtige porteføljer:

```
uv run radar performance                      # dine rigtige porteføljer
uv run radar performance ASK "ASK test"       # bestemte porteføljer, også virtuelle
uv run radar performance --tag momentum-a --tag momentum-b
uv run radar performance --start 2026-01-01 --json
```

Kolonnerne er værdi, TWR, TWR p.a., MWR p.a., ACWI, forskellen til ACWI og største fald, efterfulgt af noterne. Virtuelle porteføljer og tags kommer kun med, når du nævner dem.

`uv run radar attribution` viser fanen *Attribution* for dine rigtige porteføljer samlet (`--start` og `--end` for en periode, `--json` for det hele). Se [Kommandolinjen](brugervejledning/kommandolinjen).

## Værd at vide

- Afkastet er i DKK. Valutakursbevægelser er en del af afkastet, også for ACWI.
- Et kort tidsrum siger lidt. Afkast over få uger er mest støj, og et års MWR kræver netop et års data.
- Afkastet viser, hvad der skete; [X-ray](/xray) viser, hvad porteføljen er eksponeret mod i dag, og hvor risikoen sidder. Dens realiserede volatilitet og drawdown er regnet på samme tidsvægtede indeks som her. Se [Røntgen af porteføljen](brugervejledning/xray).
- `/market-brief` læser dine rigtige porteføljers afkast (1 måned, 3 måneder, år til dato, 1 år og siden start) fra `summary.json`. Se [Claude Code-skills](brugervejledning/claude-code).
- Siden er analyse, ikke rådgivning.
