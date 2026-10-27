# Claude Code-skills

Bruger du [Claude Code](https://claude.com/claude-code), kan du åbne programmappen (den mappe, hvor startscriptet ligger) i det og få en række kommandoer (skills), der bruger radarens data. Claude læser tallene fra radaren, søger på nettet efter forklaringerne og skriver et dokument til dig: en månedlig markedsbrief, et notat om én aktie, en sammenligning eller en beslutning i din journal.

Skills er valgfrie. Appen virker fuldt ud uden dem.

> **Bemærk:** Alt, hvad skills skriver, er analyse, ikke rådgivning. Claude skriver aldrig "køb" eller "sælg" som anbefaling, og en sammenligning kan sagtens ende med, at ingen af kandidaterne slår ACWI.

## Før du starter: din investorprofil

Skills tilpasser sig dig gennem filen `notes/investor.md` i din datamappe. Kopiér skabelonen `investor.example.md` fra programmappen til `notes/investor.md` i datamappen (`uv run radar paths` viser, hvor den ligger), og udfyld den:

- **Accounts**: hvad hver konto er til, fx aktiesparekonto (ASK) til momentumhandler og frie midler til langsigtede positioner. Brug de samme navne som dine rigtige porteføljer i appen (se `uv run radar portfolios list`), for `/journal` registrerer handler i porteføljen ved navn.
- **Horizon and style**: din typiske holdeperiode og stil.
- **Preferences and limits**: maksimal positionsstørrelse, sektorer du undgår, og andet Claude bør vide, fx at amerikanske ETF'er ikke sælges til private i EU.

Dine markedssyn skriver du ikke her, men på siden [Market views](/views); skills læser dem derfra. Se [Mine markedssyn](brugervejledning/markedssyn).

`notes/` bliver på din computer og bliver aldrig delt. Sundhedstjekket (`uv run radar doctor`) siger, om profilen findes.

## Hvor skills læser og skriver

Dine data ligger i datamappen, uden for programmappen (se [Dine data, backup og opdatering](brugervejledning/dine-data)). Skills læser og skriver dem gennem radarens værktøjer, som Claude Code starter fra programmappen: de ved selv, hvor tingene ligger, læser kun det, der skal bruges, og spørger, før noget gemmes. Se [Claude og radarens værktøjer](brugervejledning/claude-mcp). Stierne i dette kapitel, fx `briefs/` og `research/`, er mapper i datamappen.

Uden værktøjerne bruger skills kommandolinjen som før: de begynder med `uv run radar paths --json`, som siger, hvor mapperne ligger, og læser og skriver filerne der.

> **Bemærk:** Uden værktøjerne ligger datamappen uden for den mappe, du har åbnet i Claude Code, så Claude Code kan spørge om lov, før den læser eller skriver der. Giv lov til datamappen; det er der, dine noter, briefs, research og journal hører hjemme.

Er der endnu ikke valgt en datamappe, beder skillen dig om at starte appen eller køre `uv run radar setup` først.

## Oversigt

| Kommando | Skriver | Til |
|---|---|---|
| `/market-brief` | `briefs/ÅÅÅÅ-MM-DD.md` | Hvad der har ændret sig i markedet, hvorfor, og hvad det betyder for dig |
| `/research <ticker>` | `research/<TICKER>.md` | Et struktureret notat om én aktie eller ETF |
| `/compare <t1> <t2> …` | `research/compare/ÅÅÅÅ-MM-DD_<tickere>.md` | En ærlig sammenligning, med ACWI som alternativet |
| `/journal …` | `journal/ÅÅÅÅ-MM-DD-<TICKER>-<handling>.md` | En beslutning med tese og exitregler |
| `/journal review` | `journal/reviews/ÅÅÅÅ-MM.md` | Den månedlige gennemgang af åbne beslutninger |
| `/propose-portfolio <portefølje> <beløb>` | `research/proposals/ÅÅÅÅ-MM-DD_<portefølje>.md` | Et forslag til nye aktier for et beløb, testet mod ACWI og alternativerne |
| `/propose-portfolio review` | `research/proposals/reviews/ÅÅÅÅ-MM.md` | Hvordan tidligere forslag er gået, og om deres exitkriterier er udløst |
| `/hindsight [1M 3M 6M 1Y]` | `research/hindsight/ÅÅÅÅ-MM-DD_<navn>.md` | En kurv valgt på en dag i fortiden, simuleret frem til i dag |
| `/marketing` | `marketing/` | Den danske brochure (HTML og PDF) |

Alle mapperne ligger i din datamappe og er lokale og personlige; de kommer med i dine backupper, men aldrig i git. Undtagelsen er `marketing/`, som ligger i programmappen; se nedenfor.

Alt, hvad skills skriver, kan du læse i appen på siden [Notebook](/notebook) (gruppen *Mine*); se [Notesbogen](brugervejledning/notesbog).

## /market-brief

Markedsbriefen opdaterer først radaren (det samme som *Update data*) og læser derefter `summary.json`: regime og indikatorer, rotation, momentumledere og -klynger, positionering, ledende indikatorer, værdiansættelse, sentiment, dine beholdninger med flag og dine porteføljers afkast mod ACWI. Er Discover-scanningen frisk, læses de navne fra den, der står uden for radarens egne lister, og dine markedssyn hentes også.

Claude udvælger højst 6–8 ting, der betyder noget, søger efter årsagerne på nettet (med kildelink til hver påstand) og skriver en brief på under cirka 900 ord med disse afsnit: TL;DR, regime, positionering og cyklus, rotation, nye momentumledere, nyt fra Discover, dine syn mod data, din portefølje i den sammenhæng og en kø af navne til `/research`. Afsnittet *Kvalitet og værdi* nævner de bedste K+V-navne, deres overlap med momentumlederne og status for A/B-testen. Briefen skrives på dansk.

Med `/market-brief podcast` skriver Claude også en lytteversion i `briefs/lyt/`, som du kan gøre til en podcast i NotebookLM; se [Månedsbriefen](brugervejledning/maanedsbrief#som-podcast-notebooklm).

Har du egne læsenoter i `notes/` (fx `notes/bloomberg.md`), bruges de som spor, der skal efterprøves, ikke som kilder.

Briefen kører også af sig selv den første i hver måned som en planlagt opgave i Claude-appen. Se [Månedsbriefen](brugervejledning/maanedsbrief).

## /research

`/research NOVO-B.CO` skriver et notat i `research/NOVO-B.CO.md`. Claude henter hele profilen (det samme som `uv run radar info <TICKER>`: momentum, risiko, stop, analytikere, værdiansættelse, fondsgennemlysning, peers og dine markedssyn), læser rotationen fra `summary.json`, ser efter dine tidligere beslutninger og notater og søger på nettet efter forretning, seneste regnskaber, værdiansættelse mod historik og peers og kommende begivenheder. Kvalitets- og værdiscoren, FCF yield, ROIC og EV/EBIT tager Claude fra radarens egne regnskabstal (afsnittet *Quality & value* i notatet).

Notatet har en fast skabelon: tese (bull case), momentum og rotation, nøgletal og værdiansættelse, sammenhæng med dine markedssyn, katalysatorer de næste 1–6 måneder, risici (bear case), hvad der ville ugyldiggøre tesen, implementering (aktien selv eller en UCITS-ETF, og hvilken konto) og kilder. Manglende data skrives som "n/a", aldrig som et gæt.

Findes notatet allerede, beholdes det gamle indhold, og Claude tilføjer et dateret afsnit `## Update ÅÅÅÅ-MM-DD` øverst om, hvad der har ændret sig.

## /compare

`/compare NVDA AMD MU` sammenligner to eller flere navne side om side og altid med ACWI som det at gøre ingenting. Claude henter data for alle navnene på én gang (det samme som `uv run radar info NVDA AMD MU`) og går frem i fast rækkefølge:

1. **Rubrik** fra radarens data alene, før nyhederne: momentum, indtjeningsmomentum, værdiansættelse mod vækst (med værdiscoren, FCF yield og EV/EBIT), kvalitet (med kvalitetsscoren og dens søjler), risiko, rotationsmedvind, overstrækning, praktiske forhold.
2. **Fakta fra nettet** med kilder.
3. **Bull og bear** pr. navn, hver bundet til data eller en kilde.
4. **Red team**: en separat agent angriber hver bull case og skriver en pre-mortem.
5. **Relativ vurdering**, risiko, korrelation og positionsstørrelse, og en beslutningsregistrering.

Horisonten er 3 måneder, medmindre din profil eller du siger andet. Dine personlige data (positioner, journal, markedssyn) bruges kun med `--personal`. Notatet gemmes i `research/compare/ÅÅÅÅ-MM-DD_<tickere>.md`.

## /journal

Journalen gør beslutninger bevidste og mulige at efterprøve. Hver post siger, hvorfor du traf beslutningen, og hvad der ville vise, at den var forkert.

**Registrér en beslutning**, fx `/journal buy RHM.DE …`. Claude spørger én gang efter det, der mangler: handling (buy, add, trim, sell, pass), konto, tesen med dine egne ord, horisont og exitregel. Derefter tager Claude et øjebliksbillede af radarens tal, nævner markedssyn, navnet passer med, og skriver `journal/ÅÅÅÅ-MM-DD-<TICKER>-<handling>.md` med tese, radarens tal, exitregler og en pre-mortem. Er det en gennemført handel med antal og kurs, tilbyder Claude at registrere den i porteføljen. Handlen tjekkes som i appen, Claude viser dig tjekket og din position før og efter, og den gemmes først, når du siger ja.

**Månedlig gennemgang** med `/journal review`. Claude opdaterer radaren, læser alle åbne poster, henter de aktuelle tal for alle deres aktier på én gang og sammenligner exitreglerne med dem. Hver post klassificeres som *Intact*, *Weakening* eller *Invalidated*. Lukkede handler fra de seneste 3 måneder gennemgås også: hvad skete der efter exit? Resultatet skrives i `journal/reviews/ÅÅÅÅ-MM.md` med 2–3 mønstre på tværs af beslutningerne, fx at sælge vindere for tidligt. Claude ændrer ikke status på en post uden at spørge dig.

## /propose-portfolio

`/propose-portfolio ASK 50000` foreslår en spredt kurv af nye aktier til et beløb i en af dine porteføljer. Beløbet kan skrives `50000`, `50.000` eller `50k`. Claude spørger én gang efter det, der mangler:

- **Hældning**: momentum, værdi (K+V) eller en blanding. Ved hvert valg står, hvad radarens test af reglen har vist for den hældning, også i det aktuelle regime. Claude anbefaler ikke den hældning, der klarede sig bedst i testen; det ville være at tilpasse sig historikken.
- **Tilgang**: de højeste scorer (*conviction*) eller sektorer, hvor porteføljen er undervægtet mod ACWI (*fill-gaps*).
- **Horisont** (3 eller 6 måneder), **antal aktier** og om et overskydende beløb skal i en ACWI-ETF.

**Sådan vælges aktierne.** Hver aktie skal mindst have {{settings:propose.min_ticket_dkk}} kr. (indstillingen `propose.min_ticket_dkk`), fordi kurtagens minimum gør små handler dyre; der bliver højst {{settings:propose.max_names}} nye navne. En aktie er med i puljen, når den har de data, hældningen kræver, en kurs fra den seneste uge, mindst {{settings:propose.gates.min_history_weeks}} ugers historik og en gennemsnitlig daglig omsætning på mindst {{settings:propose.gates.min_adv_dkk}} kr. Ved momentum skal den også være i optrend. Radarens forslagsscore vægter percentilen af momentumscoren og K+V efter hældningen og trækker point fra for høj volatilitet, en stor stigning den seneste måned og høj korrelation med det, du allerede ejer. Kurven bygges derefter under lofter, som gælder **porteføljen efter købet**:

- højst {{settings:propose.max_per_sector}} nye navne pr. sektor;
- ingen sektor, region eller valuta mere end hhv. {{settings:propose.caps.sector|pct}}, {{settings:propose.caps.region|pct}} og {{settings:propose.caps.currency|pct}} over ACWI's vægt. ACWI's vægte kommer fra iShares' beholdningsfil for MSCI ACWI UCITS;
- ingen korrelation over {{settings:propose.max_corr}} med en anden ny aktie eller en beholdning (så er det samme væddemål);
- valgfrit en største position i forhold til alle dine rigtige porteføljer.

Antal stk. regnes i hele aktier med porteføljens kurtage, valutatillæg og et skønnet spread. På en aktiesparekonto bruges en ETF til restbeløbet kun, hvis den står på positivlisten.

**Claudes vurdering har grænser.** Claude tager udgangspunkt i reglens egen kurv og må højst bytte {{settings:propose.max_swaps}} aktier ud, hver med en skrevet grund: et regnskab inden for to uger, en konflikt med et af dine markedssyn med høj overbevisning, en sektor du undgår. Valget låses (`propose freeze`), **før** modellens tal ses. Derefter regnes det hele igennem (`propose evaluate`).

**Hvad notatet viser.**
- **Det forventede merafkast over ACWI** kommer fra testen af reglen (`uv run radar study propose`: samme regel på hver tidligere månedsultimo), med fradrag for overlevelsesbias (mindst {{settings:propose.survivorship_haircut|pct}} af et positivt merafkast) og trukket mod den lange historik: hvad de samme egenskaber har givet i alle aktier i udviklede markeder siden {{settings:propose.prior.since}}. Derefter trækkes forslagets egne handelsomkostninger fra. Aktiernes egne historiske afkast bruges ikke: de er valgt, fordi de har været høje. Se [Porteføljeforslag](laerebog/portefoeljeforslag#sådan-gør-radaren).
- **Forventet maks. drawdown** set på tre måder: testens realiserede drawdowns, en bootstrap af ugentlige afkast skaleret til dagens volatilitet, og historiske stressperioder lagt på dagens vægte. Notatet viser et forventet tal og et dårligt scenarie.
- **Alternativerne på samme mål**: ACWI for hele beløbet (A0), reglens kurv uden Claudes vurdering (A1), de to andre hældninger (A2), færre eller flere aktier (A3), at købe mere af det, du har (A4), sektor-ETF'er med samme sektorfordeling (A5) og tilfældige kurve under samme lofter (A6).
- **Konklusionen** følger en regel, der er fastlagt på forhånd: aktier foreslås kun, hvis det forventede merafkast efter omkostninger er over {{settings:propose.min_edge|pct}}, testens holdout-periode peger samme vej, og det dårlige scenarie ligger inden for din tolerance. Ellers er svaret ACWI, og det siger notatet ligeud.
- **Exitkriterier for hver aktie**: lukkekurs under {{settings:stops.trend_sma}}-dages gennemsnittet (et signal til at se på positionen igen), et signal-exit (momentumscore under {{settings:propose.exit.min_score}} eller K+V under {{settings:propose.exit.min_qv}}), 1–2 punkter fra tesen og en dato for genvurdering.

**Bagefter.** Claude tilbyder to ting. `uv run radar propose shadow` laver virtuelle kopier af porteføljen med forslaget, med ACWI og med reglens kurv, så siden [Returns](/returns) følger alle tre. `/journal` registrerer rigtige køb med exitkriterierne som exitregler. `uv run radar propose check` viser for hvert åbent forslag, om kriterierne er *Intact*, *Weakening* eller *Triggered*; `/journal review` og `/market-brief` bruger det. `/propose-portfolio review` gør status: afkast mod ACWI og mod reglens kurv, og om drawdown holdt sig inden for det forventede. Med færre end {{settings:propose.review_min}} forslag er det for tidligt at sige noget om metoden, og det står der.

Metoden er beskrevet i [Porteføljeforslag: forventet afkast, drawdown og nulhypotesen](laerebog/portefoeljeforslag).

## /hindsight

`/hindsight 3M 6M` bygger en kurv af aktier, som den kunne have været valgt for 3 og 6 måneder siden ud fra det, radaren vidste dengang, og simulerer den frem til i dag. Claude spørger én gang:

- **Hvor langt tilbage**: 1, 3, 6 eller 12 måneder.
- **Grundlaget**: scoren alene (mekanisk, den rene test), scoren og dine markedssyn (kun dem, der var oprettet senest på dagen), scoren og Claudes vurdering, eller K+V (de bedste efter kvalitet og værdi, som de så ud på dagen; kun amerikanske aktier).
- **Antal aktier** og **spredning**: fx højst 3 pr. sektor, lige vægte eller vægtet efter score.

Claude henter universet, som det så ud på dagen (`radar sim picks-candidates`), lægger sig fast på valget, før noget resultat er kendt, og kører simuleringen (`radar sim picks`). Notatet viser kurven beholdt og med stopreglen fulgt mod ACWI, mod scorens egne bedste aktier og mod gennemsnitsaktien, kurvens placering blandt tilfældige kurve og scorens test over alle måneder (`uv run radar study score`). Én kurv over én periode er et eksempel, ikke et bevis, og det står i notatet.

Claude kender markedet frem til sin vidensgrænse. Til en dag før den vælger Claude blindt, med aktierne skjult bag C001, C002 …. Se [Test momentumscoren på historikken](brugervejledning/scoretest).

## /marketing

`/marketing` bygger eller opdaterer den danske brochure i `marketing/` (`site/index.html` og `market-radar.pdf`) med nye skærmbilleder. Skærmbillederne tages fra en demokopi af appen (`.demo/`, port 8790) med en opdigtet investor, så dine egne data aldrig kommer med. Claude finder de funktioner, der er kommet til siden sidste udgave, og tilføjer afsnit og billeder til dem. PDF'en og kilderne bliver lagt i git; skærmbillederne gør ikke.

## Hvor kommer tallene fra?

Skills bruger de samme tal som appen, gennem radarens værktøjer eller kommandolinjen:

- `summary.json` fra seneste opdatering: hele markedsbilledet, dine beholdninger og porteføljernes afkast. Kun dine rigtige porteføljer; virtuelle kommer aldrig med.
- Tickerprofilen for enkelte navne (`uv run radar info`).
- Dine markedssyn (`uv run radar views --json`) og dine konti (`uv run radar portfolios list --json`).

Manglende data er `null` i radarens output og skal skrives som "n/a". Se [Claude og radarens værktøjer](brugervejledning/claude-mcp) og [Kommandolinjen](brugervejledning/kommandolinjen).

> **Tip:** Kør `/market-brief` en gang om måneden og `/journal review` lige efter. Briefen giver billedet, gennemgangen holder dine egne beslutninger op mod det.
