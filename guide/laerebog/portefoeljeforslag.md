# Porteføljeforslag: forventet afkast, drawdown og nulhypotesen

## Intuition

Når du har et beløb, du vil investere, er spørgsmålet ikke kun "hvilke aktier ser bedst ud?". Det er "er der en grund til at vælge aktier i stedet for at købe verdensindekset?". Verdensindekset (ACWI) er **nulhypotesen**: det alternativ, du får uden at vælge noget. Et forslag skal slå det, efter omkostninger og med en risiko, du kan leve med, ellers er indekset det bedre valg.

Tre fejl er lette at begå, når man sammensætter en kurv:

- **At forvente, at vinderne fortsætter som før.** Aktier valgt for et højt afkast det seneste år har pr. konstruktion et højt historisk afkast. Det siger ikke, hvad de giver fremover. Det ærlige mål er, hvad *selve udvælgelsesreglen* har givet, når den blev brugt på tidligere datoer.
- **At undervurdere risikoen.** En kurv med otte "forskellige" aktier kan være ét væddemål på dollaren, på renter eller på momentum. Og et faldt, der aldrig har været i de seneste tre år, kan stadig komme.
- **At lade vurderingen glide.** Hvis du justerer kurven, til modellens tal ser pæne ud, har du tilpasset dig din egen model.

## Teori

### Forventet merafkast fra en regeltest

Lad $R_{p,t}$ være afkastet over horisonten $H$ af den kurv, reglen valgte på dato $t$, og $R_{m,t}$ ACWI's afkast i samme periode. Merafkastet er $e_t = R_{p,t} - R_{m,t}$. Gennemsnittet over datoerne, $\bar e$, er reglens historiske merafkast. Med månedlige datoer og en horisont på flere måneder overlapper perioderne, så nabodatoerne deler det meste af deres afkast. Antallet af nogenlunde uafhængige perioder er derfor omtrent

$$
N_{\text{eff}} \approx \frac{\text{antal datoer}}{H \text{ i måneder}}
$$

og t-værdien beregnes med Newey-West-standardfejl, der tager højde for overlappet (se [Statistik for investorer](laerebog/statistik)). En regel, der kun virker i perioden, den blev udviklet på, men ikke i en senere holdout-periode, er sandsynligvis tilfældig.

### Overlevelsesbias

Universet er dagens: aktier, der er røget ud af indekset, mangler, og aktier, der kom ind efter en stærk periode, er med. Det får momentum til at se bedre ud tilbage i tiden, end det var. Et forsigtigt skøn er derfor at trække en andel fra et positivt merafkast.

### Risiko: kovarians med shrinkage

Porteføljens volatilitet er $\sigma_p = \sqrt{w^\top \Sigma w}$, hvor $\Sigma$ er kovariansmatricen af afkastene (se [Diversifikation og korrelation](laerebog/diversifikation)). Med få års data er den estimerede $\Sigma$ støjfyldt. Shrinkage trækker den mod en enklere matrix $F$ med samme volatiliteter og én fælles korrelation $\bar\rho$:

$$
\hat\Sigma = \delta F + (1-\delta) S
$$

Tracking error mod ACWI er standardafvigelsen af merafkastet, og diversifikationsgraden er $\sum_i w_i \sigma_i / \sigma_p$: jo højere over 1, jo mere udligner aktierne hinanden.

### Drawdown på tre måder

Maks. drawdown er det største fald fra en top (se [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown)). Den kan ikke forudsiges præcist, så det giver mening at se den fra flere sider:

1. **Regeltesten**: fordelingen af de realiserede drawdowns for kurvene, reglen valgte tidligere.
2. **Block bootstrap**: man trækker tilfældige blokke af sammenhængende uger fra historikken, for kurven og ACWI samtidig, så korrelationen bevares. Afkastene centreres om et antaget afkast, og udsvingene skaleres til dagens volatilitet (et eksponentielt vægtet gennemsnit), så en rolig eller urolig periode lige nu tæller med.
3. **Stressperioder**: dagens vægte lagt på kendte faldperioder.

## Sådan gør radaren

`uv run radar propose` og skill'en `/propose-portfolio` (se [Claude Code](brugervejledning/claude-code#propose-portfolio)) gør det, der står ovenfor:

- **Forslagsscoren** er et vægtet gennemsnit af percentilerne af momentumscoren og K+V i puljen. Vægtene for hver hældning ligger fast i `settings.yaml` (`propose.tilts`). Fra scoren trækkes point: op til {{settings:propose.penalties.vol}} for volatilitet, {{settings:propose.penalties.stretch}}, hvis den seneste måneds stigning er blandt puljens højeste 10 %, og op til {{settings:propose.penalties.corr}} gange korrelationen med porteføljen. Kan korrelationen ikke regnes (for få fælles uger), trækkes medianen af puljens fradrag. En ukendt korrelation regnes ikke som 0.
- **Kurven** bygges af reglen, før Claude ser den (tærsklerne står i [Claude Code](brugervejledning/claude-code#propose-portfolio)):
  - **Puljen.** En aktie er ude, og står på listen over fravalgte med grunden, når den mangler en score, hældningen bruger, en DKK-kurs, en frisk kurs, historik eller omsætning, når én aktie koster mere end beløbet pr. navn, eller (når momentum vejer mindst {{settings:propose.require_trend_from|pct}}) når den ikke er i optrend.
  - **Lofterne** gælder porteføljen efter købet og vælges grådigt efter forslagsscoren: den bedste aktie, der ikke bryder et loft, kommer med, så den næste. Den første aktie i en sektor, region eller valuta, du ikke har i forvejen, er altid tilladt: én post er ikke en ophobning. Uden iShares' beholdningsfil for ACWI kendes ACWI's vægte ikke; så springes lofterne mod ACWI over, og de aktive vægte vises som ukendte. Loftet for den største position måles mod alle dine rigtige porteføljer.
  - **Beløbet pr. aktie** er lige stort eller omvendt proportionalt med volatiliteten (dog mindst {{settings:propose.min_ticket_dkk}} kr.), i hele aktier med porteføljens kurtage, valutatillæg og et skønnet halvt spread efter omsætningen. Resten går til en ACWI-ETF eller bliver stående som kontanter.
- **Regeltesten** (`uv run radar study propose`) bruger reglen på hver tidligere månedsultimo, med kun de data, der fandtes dengang. Den gør det for kurvestørrelserne {{settings:propose.study_ns}} og horisonterne {{settings:propose.horizons}} måneder, holdt hele perioden og med forslagets exits, og med {{settings:propose.study_cost_bps}} basispunkter i omkostning hver vej. Reglen vælger kurven, som den ville vælge reglens egen kurv i et forslag, men til en tom portefølje, med lige vægte og købt på næste handelsdag (`backtest.fill`). Rammer en aktie et exit, står pengene i ACWI resten af perioden. Rapporten viser for hver hældning og kurvestørrelse gennemsnit, median, 10 %- og 90 %-fraktiler, Newey-West-t, hitrate og $N_{	ext{eff}}$, delt på holdout-perioden og på regimet på datoen, og desuden scorens IC med de næste 6 måneder og kurvens månedlige udskiftning. Værdi- og blandingshældningen kan kun testes på amerikanske aktier, fordi kun SEC EDGAR har datoen for, hvornår et regnskab blev offentliggjort. Rapporten gemmes med et fingeraftryk af reglens indstillinger. Ændrer du en af dem, er testen forældet, og forslaget viser ikke noget forventet merafkast, før den er kørt igen.
- **Det forventede merafkast** regnes i tre trin:
  1. **Testens gennemsnit** for samme hældning, den nærmeste kurvestørrelse og horisonten. Har det aktuelle regime mindst {{settings:propose.min_regime_dates}} datoer, bruges regimets eget gennemsnit.
  2. **Fradrag for overlevelsesbias.** Et positivt tal reduceres med {{settings:propose.survivorship_haircut|pct}}, eller mere, hvis `radar study longrun`s måling af overlevelsesbias peger på et større fradrag (aldrig mindre).
  3. **Træk mod den lange historik.** Testen har få uafhængige perioder og dagens aktier. Derfor trækkes tallet mod en *prior*: hvad de samme egenskaber (12-1- og 6-1-måneders afkast, FCF yield, EBITDA/EV, nettoudlodning og kvalitet) har givet i JKP's porteføljer af alle aktier i udviklede markeder siden {{settings:propose.prior.since}}: den bedste tredjedel mod gennemsnittet af de tre, uden overlevelsesbias. Har dagens trend (ACWI over eller under sit {{settings:propose.prior.trend_months}}-måneders gennemsnit) mindst {{settings:propose.prior.min_trend_eff_n}} uafhængige perioder, bruges trendens eget tal. Vægtene følger usikkerheden (en bayesiansk opdatering): $w = \frac{1/se_s^2}{1/se_s^2 + 1/(se_p^2 + \tau^2)}$, hvor $se_s$ er testens standardfejl, $se_p$ priorens og $\tau$ = {{settings:propose.prior.tau_annual|pct}} om året en ekstra usikkerhed, fordi få af dagens aktier ikke er en tredjedel af tusinder. Jo mere støj i testen, jo nærmere prioren. Har prioren ingen standardfejl (dens t-værdi er 0), er dens sikkerhed ukendt, ikke perfekt. Så bruges testen alene, og det noteres.

  Til sidst trækkes forslagets egne omkostninger fra (kurtage begge veje, valutatillæg, skønnet spread). Kan en omkostning ikke beregnes (en kurs eller valutakurs mangler), er merafkastet efter omkostninger ukendt, ikke det samme som før omkostninger; det gælder også alternativerne. Ved værdi og blanding markeres aktier uden for USA som *ikke testet*: regeltesten kender kun amerikanske regnskaber, så for dem er det kun prioren for udviklede markeder uden for USA, der taler.
- **Risikoen** regnes på ugentlige afkast i kroner over {{settings:risk.covariance.history_weeks}} uger, med shrinkage $\delta$ = {{settings:risk.covariance.shrink}}. Bootstrappen bruger blokke på {{settings:propose.bootstrap.block_weeks}} uger og ACWI-afkastet {{settings:propose.acwi_drift_annual|pct}} om året som antagelse (ikke en prognose). Stressperioderne bruges kun, hvor kurshistorikken dækker mindst halvdelen af kurvens værdi.
- **Forventet maks. drawdown** er medianen af testens og bootstrappens median. **Det dårlige scenarie** er det værste af deres 10 %-fraktiler og den værste stressperiode.
- **Beslutningsreglen**: aktier foreslås kun, hvis det forventede merafkast efter omkostninger er over {{settings:propose.min_edge|pct}}, holdout-perioden har samme fortegn, og det dårlige scenarie ligger inden for din tolerance. Ellers er konklusionen ACWI.
- **Exitkriterierne** er de samme, som testen bruger: en lukkekurs under {{settings:stops.trend_sma}}-dages gennemsnittet og et signal-exit ved månedsultimo. Ved momentum er det en momentumscore under {{settings:propose.exit.min_score}}, ved værdi en K+V under {{settings:propose.exit.min_qv}}. `uv run radar propose check` viser, hvor tæt hvert kriterium er på at blive udløst.

## Regneeksempel

Et forslag på 50.000 kr. i 5 aktier med blandingshældningen og en horisont på 6 måneder (tænkte tal):

- Regeltesten for blandingen med 5 aktier: brutto 4,0 % merafkast pr. 6 måneder over 54 datoer, altså $N_{\text{eff}} \approx 54 / 6 = 9$. Holdout-perioden er positiv.
- Fradrag for overlevelsesbias: $4{,}0\ \% \times (1 - 0{,}3) = 2{,}8\ \%$.
- Omkostninger: kurtage og spread begge veje ca. 0,5 % af beløbet. Forventet merafkast efter omkostninger: $2{,}8 - 0{,}5 = 2{,}3\ \%$, over grænsen på 1 %.
- Drawdown: testens median −12 % og 10 %-fraktil −24 %; bootstrappens median −10 % og 10 %-fraktil −20 %; den værste stressperiode −18 %. Forventet: medianen af −12 % og −10 % = −11 %. Dårligt scenarie: −24 %.
- Med en tolerance på 25 % består forslaget. Med en tolerance på 20 % bliver konklusionen ACWI, selv om merafkastet ser pænt ud.

## Faldgruber og begrænsninger

- **Få uafhængige perioder.** Med fem års månedsdata og en horisont på 6 måneder er der omkring 10 uafhængige perioder. Et gennemsnit på 10 observationer er usikkert, også med en pæn t-værdi.
- **Overlevelsesbias** er kun skønnet; den reelle størrelse kendes ikke.
- **Dagens sektorer og dagens ACWI-vægte** bruges også bagud i tiden.
- **Bootstrappen gentager fortiden.** Et fald, der er større end noget i historikken, kan ikke komme med. Derfor stressperioderne, og derfor det dårlige scenarie.
- **Ugentlige skridt** ser ikke et fald inden for en uge, så drawdowns læses lidt for pæne.
- **Før skat.** På en aktiesparekonto koster mange handler ikke ekstra skat; i frie midler beskattes en realiseret gevinst (se [Dansk skat for investorer](laerebog/skat)).
- **Vurderingen kan ikke testes bagud.** Om Claudes udskiftninger hjælper, viser kun skyggeporteføljerne over tid, og det kræver mange forslag.

## Videre læsning

- Bailey, D., Borwein, J., López de Prado, M. og Zhu, Q. (2014): *Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance*.
- Ledoit, O. og Wolf, M. (2004): *Honey, I Shrunk the Sample Covariance Matrix*.
- Politis, D. og Romano, J. (1994): *The Stationary Bootstrap*.
- Harvey, C., Liu, Y. og Zhu, H. (2016): *… and the Cross-Section of Expected Returns*.
