# Estimatrevisioner

## Intuition

En P/E fortæller, hvad du betaler for den forventede indtjening. En estimatrevision fortæller, hvilken vej forventningen bevæger sig. Det er ofte det mere interessante tal: aktiekurser reagerer på *ændringer* i forventninger, ikke på niveauet.

Når analytikerne løfter deres skøn for næste års indtjening, sker det typisk, fordi selskabet har leveret bedre end ventet, fordi ledelsen har hævet sin guidance, eller fordi branchens efterspørgsel er bedre end antaget. Den slags nyheder fordøjes sjældent på én dag. Analytikere justerer i små skridt, og investorer reagerer gradvist. Resultatet er, at revisioner har en tendens til at fortsætte i samme retning, og at aktiekurser har en tendens til at følge dem. Det er et af de mest robuste fundamentale signaler i den empiriske litteratur, og det passer godt til radarens horisont på 1–6 måneder.

Revisioner hænger tæt sammen med momentum: en del af kursmomentum kan forklares med, at markedet langsomt indregner indtjeningsnyheder. Når både kurs og skøn peger opad, støtter de hinanden. Når kursen stiger, mens skønnene falder, bør man spørge, hvad kursen ved, som analytikerne ikke ved, eller omvendt.

## Teori

### Analytikernes adfærd

Konsensusskøn er ikke uafhængige gæt. Tre mekanismer gør dem langsomme og flokkende:

- **Herding.** Det er karrieremæssigt farligt at tage fejl alene og mindre farligt at tage fejl sammen med alle andre. Hong, Kubik og Solomon (2000) fandt, at især unge analytikere holder sig tæt på konsensus, og at afvigelser straffes hårdere end fejl i flok.
- **Ankring.** Analytikere justerer fra deres forrige skøn i stedet for at regne forfra. Store nyheder giver derfor flere små revisioner over uger og måneder frem for én stor.
- **Selskabernes forventningsstyring.** Ledelser guider ofte forsigtigt for at kunne "slå forventningerne". Det giver et mønster, hvor skønnene for indeværende kvartal typisk falder op til regnskabet, og hvor de fleste selskaber derefter leverer over konsensus.

Konsekvensen er, at revisioner er *autokorrelerede*: en opjustering følges oftere af endnu en opjustering end af en nedjustering.

### Post-earnings announcement drift

Ball og Brown (1968) viste, at aktiekurser bevæger sig i retning af regnskabsoverraskelsen allerede før offentliggørelsen. Bernard og Thomas (1989) dokumenterede, at bevægelsen fortsætter i op til 60 handelsdage *efter* regnskabet: aktier med positive overraskelser fortsætter med at klare sig bedre, aktier med negative med at klare sig dårligere. Det kaldes post-earnings announcement drift (PEAD) og er en af de ældste og mest undersøgte anomalier.

### Revisionsmomentum

Givoly og Lakonishok (1979) fandt, at aktier med opjusterede skøn gav merafkast i månederne efter revisionen. Chan, Jegadeesh og Lakonishok (1996) viste, at både kursmomentum og indtjeningsmomentum (målt som overraskelser og revisioner) forudsiger afkast over de følgende 6–12 måneder, og at de to delvist er forskellige signaler. Effekten er størst for mindre, mindre dækkede aktier, hvor information spredes langsommere.

En simpel måling af revisionen for aktie $i$ over $h$ uger er den relative ændring i konsensus:

$$
\text{rev}_i(h) = \frac{\text{EPS}_{i,t}^{\text{FY1}} - \text{EPS}_{i,t-h}^{\text{FY1}}}{\left|\text{EPS}_{i,t-h}^{\text{FY1}}\right|}
$$

Absolutværdien i nævneren sikrer, at en forbedring fra $-1$ til $-0.5$ tæller som positiv.

### Revisionsbredde

For et marked eller en sektor er et samlet mål nyttigt. Revisionsbredden er andelen af selskaber med opjusteringer minus andelen med nedjusteringer:

$$
\text{bredde} = \frac{n_{\text{op}}}{n} - \frac{n_{\text{ned}}}{n}
$$

Den ligger mellem $-1$ (alle skåret ned) og $+1$ (alle løftet). Ligesom [markedsbredde](laerebog/markedsbredde) for kurser fortæller den, om en bevægelse er bred eller drives af få store navne. Et indeks' samlede EPS-skøn kan stige, fordi tre megaselskaber løftes, mens flertallet skæres; bredden afslører det.

### Kursmål

Analytikere publicerer også kursmål: den kurs, de forventer om typisk 12 måneder. Brav og Lehavy (2003) fandt, at ændringer i kursmål har informationsværdi på kort sigt, også ud over anbefalingsændringer og indtjeningsrevisioner. Selve niveauet er derimod systematisk for optimistisk: det gennemsnitlige kursmål ligger normalt et godt stykke over kursen, og kun en del af målene nås inden for horisonten. Ændringen er derfor mere informativ end afstanden.

## Sådan gør radaren

Radaren har fire kilder til revisioner, hver med sit formål.

### EPS-revisioner pr. aktie

Fra de ugentlige snapshots af Yahoos konsensus (se [P/E og indtjening pr. aktie](laerebog/pe-og-eps)) beregner radaren ændringen i næste regnskabsårs EPS (`eps_fy1`) over 4 og 12 uger (`signals/valuation.py`):

- Det seneste snapshot sammenlignes med det snapshot, der ligger tættest på præcis 4 (eller 12) uger tidligere, inden for en tolerance på ±4 dage. Findes intet snapshot i det vindue, er feltet tomt. Vinduerne og tolerancen står fast i koden.
- Revisionen er $(\text{ny} - \text{gammel}) / |\text{gammel}|$, som formlen ovenfor. Er det gamle skøn nul eller mangler, er der ingen revision.
- **Regnskabsåret ruller.** Er "indeværende år"-skønnet ændret med mere end 15 % siden det gamle snapshot, og ligger det nye "indeværende år" tættere på det gamle "næste år" end på det gamle "indeværende år", tolker radaren det som et skift af regnskabsår. Så sammenlignes det nye "indeværende år" med det gamle "næste år", altså det samme regnskabsår. Grænsen på 15 % står i koden.
- **Navne med to valutaer udelades** (`cross_ccy`: selskabet rapporterer i en anden valuta, end det handles i). Yahoo omregner deres næste års EPS til handelsvalutaen med dagens kurs, så en valutabevægelse ville ligne en revision.

Felterne vises i kolonnerne *EPS rev 4w* og *EPS rev 12w* (slås til i aktietabellerne) og i [tickerprofilen](brugervejledning/tickerprofil). 4-ugersrevisionen farves efter måleren `gauges.eps_rev` fra *cut* over *unchanged* til *raised*.

### Revisionsbredde pr. region

For hver af radarens regioner og hvert Discover-marked tæller radaren de navne, der har en revision:

- *Raised*: andelen med en revision over +{{settings:valuation.revision_band|pct}}.
- *Cut*: andelen under −{{settings:valuation.revision_band|pct}}.
- *Net*: *Raised* minus *Cut*, farvet efter `gauges.revision_breadth`.
- *Median change*: medianrevisionen.

Ændringer inden for ±{{settings:valuation.revision_band|pct}} (`valuation.revision_band`) tæller som uændrede. En gruppe skal have mindst 10 navne med en revision for at blive vist (fast i koden). Tabellen står under *Earnings revisions by region (Yahoo consensus)* på [Positioning & cycle](/positioning), én for 4 uger og én for 12 uger. Uden for S&P 500 er det radarens eneste revisionsmåling.

### FactSet: kvartalets vækstskøn

For S&P 500 læser radaren FactSets ugentlige *Earnings Insight*: det forventede indtjeningsvækst for indeværende kvartal nu og ved kvartalets start. Forskellen i procentpoint er en revisionsmåling for hele indekset og stemmer i [regimeafstemningen](laerebog/afstemningsmodellen): over +{{settings:regime.revisions_band}} procentpoint er risk-on, under −{{settings:regime.revisions_band}} risk-off. Rapporten giver også antal selskaber med positiv og negativ guidance og FactSets forward P/E. Detaljerne og hvorfor revisioner er en ledende indikator, står i [Ledende indikatorer og indtjeningsrevisioner](laerebog/ledende-indikatorer).

### Analytikernes kursmål

For dine beholdninger og din watchlist henter radaren Yahoos konsensus for kursmål, højst hver {{settings:analyst.max_age_days}}. dag, og gemmer historikken (`sources/external.py`, `signals/levels.py`):

- **Enheder**: Yahoos kursmål er angivet mod Yahoos egen kurs, som kan være i en anden enhed end radarens (pence mod pund, ADR-forhold). Radaren omregner med forholdet mellem sin egen lukkekurs og Yahoos kurs på hentedagen.
- **Upside**: gennemsnitligt kursmål divideret med seneste kurs minus 1.
- **Ændring i kursmål**: det seneste gennemsnitlige kursmål divideret med det seneste kursmål, der er hentet mindst 30 dage tidligere, minus 1. De 30 dage står i koden.
- **Krav**: kursmålene bruges til take-profit (kursmål) og stop-justering kun med mindst {{settings:stops.min_analysts}} analytikere bag.
- **Forældelse**: er konsensus hentet mere end {{settings:coverage.max_age.analyst}} dage før seneste lukkekurs, vises den uden kursmål og markeres forældet, så den ikke kan sætte et kursmål.
- **Effekt**: falder det gennemsnitlige kursmål mere end {{settings:stops.target_cut|pct}} over 30 dage, strammes det regelbaserede stop med et halvt trin (*Targets being cut*); stiger det mere end {{settings:stops.target_cut|pct}}, noteres det (*Targets being raised*). Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

Tickerprofilen viser desuden Yahoos egen revisionstrend: konsensus-EPS i dag mod for 7, 30 og 90 dage siden pr. periode og antal op- og nedjusteringer de seneste 30 dage. Ændringen beregnes kun mellem to positive skøn.

### Regnskaber i kalenderen

[Kalenderen](brugervejledning/kalender) viser for hvert regnskab, du ejer eller følger, hvordan konsensus for *det kvartal, der skal aflægges*, har bevæget sig de seneste 30 dage (Yahoos revisionstrend, periode `0q`, fra samme læsning som datoen):

- **Nedjusteret** (*estimates_cut*): EPS-skønnet er ændret med {{settings:calendar.highlight.revision_cut|pct}} eller mere, eller flere analytikere har sænket end hævet skønnet.
- **Opjusteret** (*estimates_raised*): spejlbilledet.

En nedjustering af en beholdning få dage før regnskabet er en af grundene til, at kalenderen fremhæver regnskabet som *high*. En opjustering vises som grund, men hæver aldrig niveauet.

Hvorfor revisioner lige før et regnskab er værd at se: de er autokorrelerede (se ovenfor), så et skøn, der falder ind mod regnskabet, siger noget om, hvad analytikerne hører fra selskabet og branchen. Og PEAD viser, at kursen ofte fortsætter i retning af overraskelsen efter regnskabet. Men overraskelsen måles mod konsensus på dagen: når skønnet allerede er skåret, er barren lavere, og et regnskab "over forventning" kan komme efter en nedjustering. Kalenderen viser derfor revisionen som en grund til at kigge efter, aldrig som en stemme for eller imod aktien.

## Regneeksempel

> **Eksempel:** Tre situationer. Tallene er opfundne.

**1. En almindelig revision.** For fire uger siden var konsensus for næste år 5,00 kr. pr. aktie; i dag er den 5,20 kr. Regnskabsåret er ikke skiftet:

$$
\text{rev}(4\text{u}) = \frac{5.20 - 5.00}{|5.00|} = 0.040 = +4.0\ \%
$$

Det er over +{{settings:valuation.revision_band|pct}}, så aktien tæller som opjusteret i revisionsbredden.

**2. Regnskabsåret ruller.** Snapshottet i december viste "indeværende år" (2026) 4,20 og "næste år" (2027) 5,00. I februar har selskabet aflagt årsregnskab, og Yahoo har rykket basen: "indeværende år" er nu 2027 med 5,06, og "næste år" er 2028 med 5,60.

Radaren tester for skift:

$$
\left|\frac{5.06}{4.20} - 1\right| = 0.205 > 0.15
\quad\text{og}\quad
\left|\frac{5.06}{5.00} - 1\right| = 0.012 < 0.205
$$

Begge betingelser er opfyldt, så der sammenlignes år 2027 med år 2027:

$$
\text{rev} = \frac{5.06 - 5.00}{5.00} = +1.2\ \%
$$

Uden håndteringen ville radaren have sammenlignet 2028-skønnet med 2027-skønnet: $(5.60 - 5.00)/5.00 = +12\ \%$. En ren kalendereffekt ville se ud som en kraftig opjustering.

**3. Revisionsbredde.** I radarens nordiske region har 40 aktier en 4-ugersrevision: 18 er løftet mere end {{settings:valuation.revision_band|pct}}, 10 er skåret mere end {{settings:valuation.revision_band|pct}}, og 12 er uændrede:

$$
\text{Raised} = \frac{18}{40} = 45\ \%, \quad \text{Cut} = \frac{10}{40} = 25\ \%, \quad \text{Net} = 45\ \% - 25\ \% = +20\ \%
$$

Analytikerne løfter klart flere skøn, end de skærer.

**4. Kursmål.** Det gennemsnitlige kursmål er 120 kr., og kursen er 100 kr. For 35 dage siden var kursmålet 110 kr.:

$$
\text{upside} = \frac{120}{100} - 1 = 20\ \%, \qquad \text{ændring} = \frac{120}{110} - 1 = 9.1\ \%
$$

Ændringen er over {{settings:stops.target_cut|pct}}, så radaren noterer *Targets being raised*. Upside på 20 % siger mindre, fordi kursmål generelt er optimistiske.

## Faldgruber og begrænsninger

- **Historikken bygger sig op.** 4-ugersrevisionen findes først, når radaren har gemt snapshots i fire uger, og 12-ugersrevisionen efter tolv. Et tomt felt i starten er forventet.
- **Yahoos konsensus er uofficiel.** Antallet af analytikere bag skønnet kendes ikke i snapshottet; med få analytikere kan én ændring give en stor revision.
- **Regnskabsårsskiftet er en tommelfingerregel.** Grænsen på 15 % fanger de fleste skift, men et selskab med meget lav vækst mellem to år kan slippe igennem, og et kraftigt revideret skøn kan fejltolkes som et skift.
- **Selskaber med to valutaer mangler.** Shell, Vestas og lignende er udeladt af revisionerne og dermed af bredden.
- **Revisioner er langsomme nyheder.** Signalet handler om fortsættelse over uger og måneder. En enkelt uges ændring er mest støj.
- **Forudsigeligt dyk før regnskaber.** Kvartalsskøn falder typisk op til regnskabet som led i forventningsstyring. Radaren bruger helårsskøn, som er mindre påvirkede, men ikke immune.
- **Kursmål følger kursen.** Analytikere hæver ofte kursmål, *efter* kursen er steget. En stigning i kursmål efter en stigning i kursen er svagere information end en, der kommer først.

## Videre læsning

- Ray Ball og Philip Brown: "An Empirical Evaluation of Accounting Income Numbers", *Journal of Accounting Research* 6(2), 1968.
- Victor L. Bernard og Jacob K. Thomas: "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?", *Journal of Accounting Research* 27 (supplement), 1989.
- Dan Givoly og Josef Lakonishok: "The Information Content of Financial Analysts' Forecasts of Earnings", *Journal of Accounting and Economics* 1(3), 1979.
- Louis K. C. Chan, Narasimhan Jegadeesh og Josef Lakonishok: "Momentum Strategies", *Journal of Finance* 51(5), 1996.
- Harrison Hong, Jeffrey D. Kubik og Amit Solomon: "Security Analysts' Career Concerns and Herding of Earnings Forecasts", *RAND Journal of Economics* 31(1), 2000.
- Alon Brav og Reuven Lehavy: "An Empirical Analysis of Analysts' Target Prices: Short-term Informativeness and Long-term Dynamics", *Journal of Finance* 58(5), 2003.
