# Claude Code-skills

Bruger du [Claude Code](https://claude.com/claude-code), kan du åbne programmappen (den mappe, hvor startscriptet ligger) i det og få en række kommandoer (skills), der bruger radarens data. Claude læser tallene fra radaren, søger på nettet efter forklaringerne og skriver et dokument til dig: en månedlig markedsbrief, et notat om én aktie, en sammenligning eller en beslutning i din journal.

Skills er valgfrie. Appen virker fuldt ud uden dem.

> **Bemærk:** Alt, hvad skills skriver, er analyse, ikke rådgivning. Claude skriver aldrig "køb" eller "sælg" som anbefaling, og en sammenligning kan sagtens ende med, at ingen af kandidaterne slår ACWI.

## Før du starter: din investorprofil

Skills tilpasser sig dig gennem filen `notes/investor.md` i din datamappe. Kopiér skabelonen `investor.example.md` fra programmappen til `notes/investor.md` i datamappen (`uv run radar paths` viser, hvor den ligger), og udfyld den:

- **Accounts**: hvad hver konto er til, fx aktiesparekonto (ASK) til momentumhandler og frie midler til langsigtede positioner. Brug de samme navne som dine rigtige porteføljer i appen (se `uv run radar portfolios list`), for `/journal` registrerer handler i porteføljen ved navn.
- **Horizon and style**: din typiske holdeperiode og stil.
- **Preferences and limits**: maksimal positionsstørrelse, sektorer du undgår, og andet Claude bør vide, fx at amerikanske ETF'er ikke sælges til private i EU.

Dine markedssyn skriver du ikke her, men på siden [Market views](/views); skills læser dem med `uv run radar views --json`. Se [Mine markedssyn](brugervejledning/markedssyn).

`notes/` bliver på din computer og bliver aldrig delt. Sundhedstjekket (`uv run radar doctor`) siger, om profilen findes.

## Hvor skills læser og skriver

Dine data ligger i datamappen, uden for programmappen (se [Dine data, backup og opdatering](brugervejledning/dine-data)). Hver skill begynder derfor med `uv run radar paths --json`, som siger, hvor datamappen, `summary.json` og de andre mapper ligger. Stierne i dette kapitel, fx `briefs/` og `research/`, er mapper i datamappen, og `summary.json` ligger i cache-mappens `reports/`.

> **Bemærk:** Fordi datamappen ligger uden for den mappe, du har åbnet i Claude Code, kan Claude Code spørge om lov, før den læser eller skriver der. Giv lov til datamappen; det er der, dine noter, briefs, research og journal hører hjemme.

Er der endnu ikke valgt en datamappe, beder skillen dig om at starte appen eller køre `uv run radar setup` først.

## Oversigt

| Kommando | Skriver | Til |
|---|---|---|
| `/market-brief` | `briefs/ÅÅÅÅ-MM-DD.md` | Hvad der har ændret sig i markedet, hvorfor, og hvad det betyder for dig |
| `/research <ticker>` | `research/<TICKER>.md` | Et struktureret notat om én aktie eller ETF |
| `/compare <t1> <t2> …` | `research/compare/ÅÅÅÅ-MM-DD_<tickere>.md` | En ærlig sammenligning, med ACWI som alternativet |
| `/journal …` | `journal/ÅÅÅÅ-MM-DD-<TICKER>-<handling>.md` | En beslutning med tese og exitregler |
| `/journal review` | `journal/reviews/ÅÅÅÅ-MM.md` | Den månedlige gennemgang af åbne beslutninger |
| `/hindsight [1M 3M 6M 1Y]` | `research/hindsight/ÅÅÅÅ-MM-DD_<navn>.md` | En kurv valgt på en dag i fortiden, simuleret frem til i dag |
| `/marketing` | `marketing/` | Den danske brochure (HTML og PDF) |

Alle mapperne ligger i din datamappe og er lokale og personlige; de kommer med i dine backupper, men aldrig i git. Undtagelsen er `marketing/`, som ligger i programmappen; se nedenfor.

Alt, hvad skills skriver, kan du læse i appen på siden [Notebook](/notebook) (gruppen *Mine*); se [Notesbogen](brugervejledning/notesbog).

## /market-brief

Markedsbriefen opdaterer først radaren (`uv run radar run`) og læser derefter `summary.json`: regime og indikatorer, rotation, momentumledere og -klynger, positionering, ledende indikatorer, værdiansættelse, sentiment, dine beholdninger med flag og dine porteføljers afkast mod ACWI. Er Discover-scanningen under 10 dage gammel, læses den også, og dine markedssyn hentes med `radar views --json`.

Claude udvælger højst 6–8 ting, der betyder noget, søger efter årsagerne på nettet (med kildelink til hver påstand) og skriver en brief på under cirka 900 ord med disse afsnit: TL;DR, regime, positionering og cyklus, rotation, nye momentumledere, nyt fra Discover, dine syn mod data, din portefølje i den sammenhæng og en kø af navne til `/research`. Briefen skrives på dansk.

Med `/market-brief podcast` skriver Claude også en lytteversion i `briefs/lyt/`, som du kan gøre til en podcast i NotebookLM; se [Månedsbriefen](brugervejledning/maanedsbrief#som-podcast-notebooklm).

Har du egne læsenoter i `notes/` (fx `notes/bloomberg.md`), bruges de som spor, der skal efterprøves, ikke som kilder.

Briefen kører også af sig selv den første i hver måned som en planlagt opgave i Claude-appen. Se [Månedsbriefen](brugervejledning/maanedsbrief).

## /research

`/research NOVO-B.CO` skriver et notat i `research/NOVO-B.CO.md`. Claude henter hele profilen med `uv run radar info <TICKER>` (momentum, risiko, stop, analytikere, værdiansættelse, fondsgennemlysning, peers og dine markedssyn), læser rotationen fra `summary.json`, ser efter dine tidligere beslutninger i `journal/` og søger på nettet efter forretning, seneste regnskaber, værdiansættelse mod historik og peers og kommende begivenheder.

Notatet har en fast skabelon: tese (bull case), momentum og rotation, nøgletal og værdiansættelse, sammenhæng med dine markedssyn, katalysatorer de næste 1–6 måneder, risici (bear case), hvad der ville ugyldiggøre tesen, implementering (aktien selv eller en UCITS-ETF, og hvilken konto) og kilder. Manglende data skrives som "n/a", aldrig som et gæt.

Findes notatet allerede, beholdes det gamle indhold, og Claude tilføjer et dateret afsnit `## Update ÅÅÅÅ-MM-DD` øverst om, hvad der har ændret sig.

## /compare

`/compare NVDA AMD MU` sammenligner to eller flere navne side om side og altid med ACWI som det at gøre ingenting. Claude henter data med `uv run radar info NVDA AMD MU --out …` (en fil i `exports/` i datamappen) og går frem i fast rækkefølge:

1. **Rubrik** fra radarens data alene, før nyhederne: momentum, indtjeningsmomentum, værdiansættelse mod vækst, kvalitet, risiko, rotationsmedvind, overstrækning, praktiske forhold.
2. **Fakta fra nettet** med kilder.
3. **Bull og bear** pr. navn, hver bundet til data eller en kilde.
4. **Red team**: en separat agent angriber hver bull case og skriver en pre-mortem.
5. **Relativ vurdering**, risiko, korrelation og positionsstørrelse, og en beslutningsregistrering.

Horisonten er 3 måneder, medmindre din profil eller du siger andet. Dine personlige data (positioner, journal, markedssyn) bruges kun med `--personal`. Notatet gemmes i `research/compare/ÅÅÅÅ-MM-DD_<tickere>.md`.

## /journal

Journalen gør beslutninger bevidste og mulige at efterprøve. Hver post siger, hvorfor du traf beslutningen, og hvad der ville vise, at den var forkert.

**Registrér en beslutning**, fx `/journal buy RHM.DE …`. Claude spørger én gang efter det, der mangler: handling (buy, add, trim, sell, pass), konto, tesen med dine egne ord, horisont og exitregel. Derefter tager Claude et øjebliksbillede af radarens tal, nævner markedssyn, navnet passer med, og skriver `journal/ÅÅÅÅ-MM-DD-<TICKER>-<handling>.md` med tese, radarens tal, exitregler og en pre-mortem. Er det en gennemført handel med antal og kurs, tilbyder Claude at registrere den i porteføljen med `uv run radar portfolio add`, som tjekker den som i appen.

**Månedlig gennemgang** med `/journal review`. Claude opdaterer radaren, læser alle åbne poster og sammenligner exitreglerne med de aktuelle tal. Hver post klassificeres som *Intact*, *Weakening* eller *Invalidated*. Lukkede handler fra de seneste 3 måneder gennemgås også: hvad skete der efter exit? Resultatet skrives i `journal/reviews/ÅÅÅÅ-MM.md` med 2–3 mønstre på tværs af beslutningerne, fx at sælge vindere for tidligt. Claude ændrer ikke status på en post uden at spørge dig.

## /hindsight

`/hindsight 3M 6M` bygger en kurv af aktier, som den kunne have været valgt for 3 og 6 måneder siden ud fra det, radaren vidste dengang, og simulerer den frem til i dag. Claude spørger én gang:

- **Hvor langt tilbage**: 1, 3, 6 eller 12 måneder.
- **Grundlaget**: scoren alene (mekanisk, den rene test), scoren og dine markedssyn (kun dem, der var oprettet senest på dagen) eller scoren og Claudes vurdering.
- **Antal aktier** og **spredning**: fx højst 3 pr. sektor, lige vægte eller vægtet efter score.

Claude henter universet med `uv run radar sim picks-candidates`, låser valget i en fil, før noget resultat er kendt, og kører `uv run radar sim picks`. Notatet viser kurven beholdt og med stopreglen fulgt mod ACWI, mod scorens egne bedste aktier og mod gennemsnitsaktien, kurvens placering blandt tilfældige kurve og scorens test over alle måneder (`uv run radar study score`). Én kurv over én periode er et eksempel, ikke et bevis, og det står i notatet.

Claude kender markedet frem til sin vidensgrænse. Til en dag før den vælger Claude blindt, med aktierne skjult bag C001, C002 …. Se [Test momentumscoren på historikken](brugervejledning/scoretest).

## /marketing

`/marketing` bygger eller opdaterer den danske brochure i `marketing/` (`site/index.html` og `market-radar.pdf`) med nye skærmbilleder. Skærmbillederne tages fra en demokopi af appen (`.demo/`, port 8790) med en opdigtet investor, så dine egne data aldrig kommer med. Claude finder de funktioner, der er kommet til siden sidste udgave, og tilføjer afsnit og billeder til dem. PDF'en og kilderne bliver lagt i git; skærmbillederne gør ikke.

## Hvor kommer tallene fra?

Skills bruger de samme tal som appen:

- `summary.json` fra seneste `radar run` (i cache-mappens `reports/`): hele markedsbilledet, dine beholdninger og porteføljernes afkast. Kun dine rigtige porteføljer; virtuelle kommer aldrig med.
- `uv run radar info` for enkelte navne.
- `uv run radar views --json` for dine markedssyn.
- `uv run radar portfolios list --json` for dine konti.

Manglende data er `null` i radarens output og skal skrives som "n/a". Se [Kommandolinjen](brugervejledning/kommandolinjen).

> **Tip:** Kør `/market-brief` en gang om måneden og `/journal review` lige efter. Briefen giver billedet, gennemgangen holder dine egne beslutninger op mod det.
