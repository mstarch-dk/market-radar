# Skat: radarens skatteestimat

Fanen *Tax* på siden [Portfolio](/portfolio) viser et skøn over den danske skat, som dine egne handler i radaren giver for et indkomstår: pr. konto og pr. person. Den bygger på reglerne i [Dansk skat for investorer](laerebog/skat), og metoden er beskrevet i kapitlets afsnit [Sådan gør radaren](laerebog/skat#sådan-gør-radaren).

> **Bemærk:** Det er et estimat ud fra radarens egne tal, ikke skatterådgivning. Din årsopgørelse og din mæglers indberetning er det, der gælder. Brug fanen til at forstå, hvor skatten kommer fra, og til at tjekke, at intet er glemt.

## Hvad fanen viser

Øverst vælger du indkomståret (*Income year*). Derunder står en gul boks med forbeholdet, den dato satserne for året sidst er tjekket mod skat.dk, og links til kilderne. Er året ikke slut, står der også, hvilken dag værdierne er fra: estimatet flytter sig indtil 31. december.

Derefter kommer et kort for hver person og for hver konto:

- **Personens kort** (*Me: frie midler*) samler alle personens konti med frie midler, fordi gennemsnitsmetoden og aktieindkomsten opgøres pr. person, ikke pr. depot. Bjælken viser aktieindkomsten mod progressionsgrænsen ({{tax:2026.share_income.progression_limit}} kr. i 2026). Under den står aktieindkomsten efter tab, skatten med den lave og den høje sats, realiserede gevinster og tab, udbytte, lagergevinst på fonde på positivlisten, tab der fremføres, og kapitalindkomst fra fonde uden for listen.
- **En aktiesparekonto eller en pensionskonto** er ét regnskab: værdi ved årets start og slut, ind- og udbetalinger, afkastet og skatten ({{tax:2026.ask.rate|pct}} på aktiesparekontoen, {{tax:2026.pension.pal_rate|pct}} PAL-skat på pension). Et år med tab giver negativ skat, som fremføres og står som *Negative tax carried out*.
- **En konto med frie midler** viser salgene i året (antal, provenu, anskaffelsessum efter gennemsnitsmetoden og gevinst), lagerbeskattede fonde (værdi ved start og slut, køb, salg og gevinst) og udbytte.

Under kortene står *Not in the estimate*: beholdninger, radaren ikke kan afgøre beskatningen af. De er nævnt med værdi og årsag og regnes ikke med; de bliver aldrig gættet. Nederst åbner *Who owns what, rates and losses carried in* indstillingerne (se nedenfor).

Et beløb, der ikke kan regnes (en manglende kurs eller valutakurs), står som –, aldrig som 0, og kortet er mærket *incomplete* eller *no estimate*. Det gælder også udbyttet, når kurserne viser et udbytte, du ikke har bogført, og kapitalindkomsten, så længe en beholdning mangler sin beskatning: en af dem kan være en fond uden for positivlisten.

## Sådan regner radaren

- **Beløb i kroner.** Hver handel omregnes med sin egen valutakurs (feltet *DKK per …*), ellers med Yahoos kurs den dag, som på [Afkast over tid](brugervejledning/afkast). Værdierne ved årets start og slut er lukkekursen den sidste handelsdag, ikke de udbyttejusterede kurser: udbytte er indkomst for sig.
- **Gennemsnitsmetoden** regnes i kroner på tværs af en persons konti med frie midler. Kurtage ved køb lægges til anskaffelsessummen, kurtage ved salg trækkes fra provenuet. Køb på aktiesparekontoen påvirker ikke gennemsnittet.
- **Lager** for en fond: værdien ved årets slut plus det, salg har indbragt, minus værdien ved årets start og det, køb har kostet.
- **Aktiesparekonto og pension**: afkastet er værdien ved årets slut minus værdien ved årets start, minus indbetalinger, plus udbetalinger. Udbytte er med i værdien.
- **Klassificering pr. år.** En aktie er realisationsbeskattet aktieindkomst. En fond, hvis ISIN står på det års positivliste, er lagerbeskattet aktieindkomst; en udenlandsk fond, der ikke gør, er lagerbeskattet kapitalindkomst. Forlader en ETF listen, skifter den derfor beskatning i det år, den forsvinder, og på en aktiesparekonto får du en advarsel.
- **Fremførsel** regnes fra kontoens første år: negativ skat på aktiesparekonto og pension, tab på børsnoterede aktier og negativ aktieindkomst pr. person. Har et tidligere år ingen satser, kendes det fremførte ikke, og året viser grundlaget uden skat, indtil du skriver beløbene fra din årsopgørelse ind under *Losses carried in* (se nedenfor). De erstatter radarens egen optælling fra det år.
- **Udbytte** tæller med det beløb, du har bogført som udbytte. Radaren kan se på kurserne, hvornår en aktie er gået ex-udbytte. Ejede du den dagen før, og er der ikke bogført et udbytte fra en uge før til 45 dage efter, står udbyttet som ukendt, og noten nævner aktien og datoen. En ex-dag, der er yngre end 45 dage, er måske ikke udbetalt endnu og tælles ikke med.
- **Negativ kapitalindkomst** giver ingen skat her. Den sænker skatten af din øvrige indkomst med et beløb, der afhænger af den indkomst, så den regnes ikke med.

Satserne står i `config/tax_dk.yaml`, ét afsnit pr. år, hvert tal med kilde og den dato, det er tjekket. Et år uden tjekkede satser viser beløbene, men ingen skat: radaren låner aldrig et andet års tal.

## Det, du selv skal angive

Åbn *Who owns what, rates and losses carried in* nederst på fanen:

- **Accounts**: hvilken person hver konto tilhører. Alle rigtige konti tilhører *Me*, indtil du ændrer det. Har du og en partner hver jeres frie midler, så opret en person mere med `radar tax person add Navn` og flyt kontoen.
- **Rate on capital income**: din marginale skat på kapitalindkomst i procent. Den afhænger af resten af din indkomst, så radaren gætter den ikke; uden den vises kapitalindkomsten uden skat.
- **Losses carried in**: det, din årsopgørelse for året før fører ind i et år. Vælg året, beløbet føres ind i, puljen (*ASK: negative tax*, *Pension: negative tax*, *Listed-share loss* eller *Negative share income*), kontoen eller personen og beløbet i kroner. Beløbet erstatter radarens egen optælling fra det år, så din seneste årsopgørelse er nok, også når dine handler i radaren går længere tilbage end satserne. Fremføres der intet, så skriv 0: det er også et svar. For en person gælder et beløb for begge puljer; den, du ikke skriver, fører 0 ind.

En beholdning under *Not in the estimate* retter du direkte i listen: skriv ISIN-koden (så positivlisten kan tjekkes), eller vælg beskatningen. En dansk fond uden for positivlisten skal du selv angive som *Danish distributing fund*, hvis den er udloddende. Det samme kan gøres med `radar tax isin SYMBOL ISIN` og `radar tax classify SYMBOL KLASSE`.

ISIN-koder hentes automatisk, første gang en beholdning ses: fra din import (den kode, din mægler brugte), fra `universe.yaml` og fra *Discover*-scannerens liste over fonde på positivlisten. En kode, du selv har skrevet, bliver aldrig overskrevet.

## Fra kommandolinjen

| Kommando | Hvad den gør |
|---|---|
| `uv run radar tax year 2026` | Estimatet for året; `--json` giver det samme som fanen, `--portfolio` og `--person` afgrænser |
| `uv run radar tax classify [--unknown]` | ISIN, kilde og klasse i året for det, dine rigtige konti har handlet (ikke simuleringer) |
| `uv run radar tax isin SYMBOL ISIN` | Sæt en ISIN-kode |
| `uv run radar tax classify SYMBOL stock\|pl_fund\|fund\|dk_distributing\|auto` | Sæt beskatningen (`auto`: ud fra ISIN og positivlisten igen) |
| `uv run radar tax person list\|add\|set` | Personer, deres sats på kapitalindkomst (`--capital-rate 0.37`) og konti (`--account`) |
| `uv run radar tax opening list\|add\|remove` | Fremførte tab fra din årsopgørelse (`--amount 0`: intet fremført) |

## Hvad radaren regner med, og hvad den ikke gør

**Med:**

- Gennemsnitsmetoden i kroner pr. person over konti med frie midler, med kurtage ved køb og salg
- Lagerbeskatning af fonde på og uden for positivlisten, år for år efter det års liste
- Aktiesparekontoen og pension som ét lagerbeskattet regnskab med fremført negativ skat
- Tab på børsnoterede aktier modregnet i gevinst, udbytte og lagergevinst på positivlistefonde, resten fremført
- Progressionsgrænsen for aktieindkomst
- Danske udloddende fonde, når du har angivet dem

**Ikke med:**

- Overførsel af uudnyttet progressionsgrænse eller tab mellem ægtefæller
- Unoterede aktier, obligationer og anden kapitalindkomst uden for radaren
- Udenlandsk kildeskat på udbytte: udbytte tæller med det beløb, du har bogført
- Skatteværdien af negativ aktieindkomst mod anden skat: den vises kun som fremført
- Betingelserne for at få fradrag for tab (rettidig indberetning til SKAT)
- Lukning af en aktiesparekonto og skat ved udbetaling af pension
- Alt fra før dine første handler i radaren, ud over de fremførte tab, du selv angiver

> **Tip:** Trækker din bank aktiesparekontoens skat fra kontoen i januar, så bogfør den som en udbetaling (*Withdrawal*), ikke som et gebyr. Et gebyr tæller som et tab i kontoens afkast. Fanen advarer, når en gebyrrække i januar ligner skatten.
