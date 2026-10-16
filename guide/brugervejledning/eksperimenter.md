# Eksperimenter: virtuelle porteføljer

Siden [Experiments](/experiments) samler dine virtuelle porteføljer: A/B-testen, simuleringer, forks af dine konti og testporteføljer, du selv fører. De tæller aldrig som dine (beholdninger, briefs, Claude-skills) og vises derfor ikke på siden [Portfolio](/portfolio), som kun har dine konti. Forskellen er beskrevet i [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

## Listen

Kører [A/B-testen](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum), står den øverst i sit eget kort med de tre kurve, deres afkast og afkastet mod ACWI, datoen for næste ombalancering og et link til at sammenligne dem på siden *Returns*.

Derunder står alle virtuelle porteføljer i én tabel:

| Kolonne | Viser |
|---|---|
| *Experiment* | Navnet (klik for at åbne den) og dens tags |
| *Kind* | *A/B test*, *Simulation*, *Fork* eller *Your own* (se nedenfor) |
| *From* | Datoen for den første række |
| *Value (DKK)* | Værdien i dag |
| *Return*, *ACWI*, *vs ACWI* | Det tidsvægtede afkast fra første række, ACWI's afkast i samme periode og forskellen |
| *Rows* | Antal rækker |

Et afkast, der ikke kan regnes (manglende kurs eller valutakurs), står som –, aldrig som 0. Arkiverede eksperimenter vises med *show N archived*. Nederst opretter du en ny virtuel portefølje: skriv et navn, vælg hvilken skattetype den skal efterligne, og klik *Add*.

### De fire slags

| *Kind* | Hvor den kommer fra | Rækkerne |
|---|---|---|
| *A/B test* | *Start the A/B test* på siden [Quality & value](/quality#ab), eller `radar abtest start` | Skrives af testen hver måned; kan ikke rettes |
| *Simulation* | `radar sim picks`, `/hindsight`, `radar sim exits` | Skrives af en kørsel; en ny kørsel erstatter dem |
| *Fork* | *fork into an experiment* under *Accounts* på siden *Portfolio* | Dine egne: ret og tilføj som på en konto |
| *Your own* | Oprettet nederst på denne side | Dine egne |

## En enkelt portefølje

Klikker du på et navn, åbner porteføljen (`?pf=<id>` i adressen). Øverst står, hvad den er: strategien, hvilken konto en fork er kopieret fra og hvornår, perioden, den seneste kørsel for en simulering, og linjen med værdi, afkast og afkast mod ACWI. Her kan du også tagge, omdøbe, arkivere og slette den.

Derunder er der faner:

- ***Holdings***: hvad porteføljen ejer nu, med antal, gennemsnitskurs, seneste kurs, værdi og urealiseret afkast, og kontantbeholdningen.
- ***Trades***: alle rækker. I en fork og din egen portefølje kan du tilføje, rette og slette rækker som på en konto. I en simulering og A/B-testen kan de ikke rettes, fordi næste kørsel ville erstatte dem.
- ***Rebalances*** (kun A/B-testen): hver måneds kurv med vægte og hvor stor en del, der blev handlet om.
- ***Returns***: værdien over tid mod ACWI og et link til siden *Returns*, hvor du kan sammenligne med dine konti eller andre eksperimenter.

*Experiments* øverst fører tilbage til listen.

> **Bemærk:** Et eksperiment er analyse, ikke rådgivning. Et par måneders forspring til en strategi siger næsten intet; se [Scoretesten](brugervejledning/scoretest).
