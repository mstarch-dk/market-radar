# Kalenderen

Siden [Calendar](/calendar) under *Mine* viser, hvad der sker for dine navne de næste uger: regnskaber og udbyttedage for de aktier, du ejer og følger, og dine egne datoer, dvs. gennemgangsdatoer i journalen og tidsstop i dine porteføljeforslag. For hvert punkt står, *hvorfor* det er fremhævet, efter faste regler. Kalenderen siger hvad og hvorfor, aldrig hvad du skal gøre. Det er analyse, ikke rådgivning.

Vinduet er {{settings:calendar.days}} dage (`calendar.days`), regnet fra seneste lukkekurs. Er det weekend, tæller dagene altså fra fredag, og et regnskab på tirsdag står som "in 4 d". Det står også i noterne nederst på siden. Fordi dagene regnes fra data og ikke fra uret, giver de samme data altid den samme kalender.

## Vælg portefølje

Vælgeren *Portfolio* virker som på [Mine beholdninger og watchlist](brugervejledning/beholdninger#vælg-portefølje): som standard dine rigtige porteføljer lagt sammen, ellers én portefølje, et tag eller alle virtuelle. Valget står i adressen som `?pf=`. Watchlisten er altid med (slås fra med `calendar.include.watchlist`).

## De næste dage

Øverst står *Next {{settings:calendar.soon_days}} days*: de punkter, der er fremhævet som *high* inden for {{settings:calendar.soon_days}} dage (`calendar.soon_days`), med det vigtigste først. Hvert kort viser navnet, datoen (eller Yahoos vindue), hvor datoen kommer fra og hvornår den er læst, og grundene som små mærker, fx *you hold it*, *6.2% of the portfolio* og *the quarter's EPS estimate cut 4.1% in 30 days*.

Er listen tom, står der *Nothing that needs attention in the next {{settings:calendar.soon_days}} days*. Tom betyder ikke "ingen data": har nogle aktier ingen kendt dato, står antallet ved siden af, og de er listet under [Ingen dato kendt](#ingen-dato-kendt).

## Agenda og måned

Under kortene vælger du mellem to faner:

- *Agenda*: alle punkter i vinduet, grupperet efter uge (ISO-uge, mandag til søndag) med én tabel pr. uge. Kolonnerne er *Date*, *Name*, *What* (regnskab, udbytte, gennemgang eller tidsstop, og om det er *held*, *watched* eller *yours*), *Level*, *Weight* (beholdningens andel af den investerede værdi), *EPS est.* (konsensus for kvartalet; hold musen over for laveste og højeste skøn) og *Why*.
- *Month*: de samme punkter i et månedsgitter. Hvert punkt er en lille mærkat på sin dag, farvet efter niveau. Et vindue (se nedenfor) løber hen over alle sine dage og er tegnet lysere og stiplet, så det aldrig ligner én dato. Dage uden for vinduet er nedtonede, og i dag har en blå ramme.

Over tabellen kan du filtrere: *Held & watched*, *Held* eller *Watched*, og hvilke slags punkter der vises (*Earnings*, *Ex-dividend*, *My reviews*, *Time stops*). Dine egne datoer hører med under *Held*. Filtrene og fanen står i adressen, så en visning kan gemmes som bogmærke.

## Hvor datoerne kommer fra

Datoerne er Yahoos: den dato eller det vindue, Yahoo *forventer*. De er ikke bekræftet af selskaberne, heller ikke når der kun står én dato. Radaren læser Yahoos kalender for dine beholdninger og din watchlist som et trin i opdateringen (se [Data og dækning](brugervejledning/data-og-daekning)): hver {{settings:calendar.refresh.max_age_days}}. dag, og dagligt når et regnskab er højst {{settings:calendar.refresh.near_days}} dage væk. Hver læsning gemmes i historikken, så kalenderen kan se, når en dato flytter sig.

Datoen vælges i denne rækkefølge:

1. **Yahoos kalender for aktien**, hvis den seneste læsning er højst {{settings:calendar.stale_days}} dage gammel (`calendar.stale_days`) og datoen ikke er passeret.
2. **Den ugentlige screener**, hvis den har en dato, der er i dag eller senere. Screeneren har kun én dag og kan stå på en dato, der lige er passeret, i op til en uge, så en passeret dato bruges aldrig.
3. **En ældre læsning**, hvis dens dato stadig ligger ude i fremtiden.
4. Ellers ingen dato: aktien står under [Ingen dato kendt](#ingen-dato-kendt).

Hvor sikker datoen er, står ved hvert regnskab: *expected window* (et vindue) eller *expected date*, kilden (*Yahoo calendar* eller *Yahoo screener*) og hvornår den er læst. Er datoen flyttet siden forrige læsning, står *moved from* og den gamle dato. Snævrer et vindue sig ind til en dag inden for det gamle vindue, er det ikke en flytning.

## Fremhævningsreglerne

Hvert punkt får sine grunde, og niveauet følger af dem. Der er ingen score og ingen regel, der siger køb eller sælg.

| Grund | Gælder | Regel |
|---|---|---|
| *you hold it* | regnskab, udbytte | Aktien er blandt beholdningerne i det valgte |
| *N% of the portfolio* | regnskab i en beholdning | Mindst {{settings:calendar.highlight.big_position|pct}} af den investerede værdi (`calendar.highlight.big_position`) |
| *price N% above/below its review level* | regnskab i en beholdning | Seneste lukkekurs højst {{settings:calendar.highlight.near_level|pct}} fra [gennemgangsniveauet](laerebog/stop-og-storrelse#gennemgangsniveauet), over eller under (`calendar.highlight.near_level`) |
| *losing momentum*, *below 200d* | regnskab i en beholdning | Flaget står på aktien under [Holdings & watchlist](brugervejledning/beholdninger#flagene) |
| *estimate cut* | regnskab | Kvartalets EPS-skøn ændret med {{settings:calendar.highlight.revision_cut|pct}} eller mere på 30 dage, eller flere nedjusteringer end opjusteringer (`calendar.highlight.revision_cut`) |
| *estimate raised* | regnskab | Spejlbilledet; vises, men hæver aldrig niveauet |
| *no set date: Yahoo expects …* | regnskab | Yahoo giver et vindue, ikke en dag |
| *date moved from …* | regnskab | Datoen er en anden end ved forrige læsning |
| *date from the weekly screener / an older read* | regnskab | Datoen kommer ikke fra en frisk læsning af aktiens kalender |
| *review your journal entry by …* | gennemgang | En åben journalpost har `review_by` i vinduet; en overskredet står som *review overdue since …* |
| *time stop of the … proposal*, *exit check: …* | tidsstop | Et forslags tidsstop falder i vinduet, med exit-tjekkets status (*Intact*, *Weakening*, *Triggered*) |

Niveauerne:

- ***high***: et regnskab i en beholdning inden for {{settings:calendar.soon_days}} dage med mindst én af disse grunde: stor position, tæt på gennemgangsniveauet, svagt momentum eller nedjusteret skøn. Også et tidsstop, hvor exit-tjekket siger *Triggered*.
- ***normal***: andre regnskaber i dine beholdninger og dine egne gennemgangsdatoer.
- ***info***: watchlist-navne og udbyttedage.

Inden for en dag står *high* først, derefter efter vægt. Teksterne er de samme på siden, i `radar calendar` og i månedsbriefen. Hvorfor netop størrelse og afstand til niveauet tæller, står i [Regnskaber og kursgab](laerebog/stop-og-storrelse#regnskaber-og-kursgab); om revisionerne i [Regnskaber i kalenderen](laerebog/estimatrevisioner#regnskaber-i-kalenderen).

> **Bemærk:** Et stop beskytter ikke mod et kursgab ved et regnskab. Fremhævningen viser, hvor et gab ville betyde mest; den er ikke en opfordring til at handle før regnskabet.

## Ingen dato kendt

En aktie, du ejer eller følger, uden en kendt regnskabsdato, bliver aldrig udeladt i stilhed. Den står under *No date known* med grunden:

- *not read yet*: Yahoos kalender er ikke læst for aktien endnu (fx lige efter, at du har købt den; den læses ved næste opdatering).
- *Yahoo gave no date*: Yahoo havde ingen dato ved seneste læsning.
- *the last known date has passed and no new one is known yet*: regnskabet er aflagt, og den næste dato er ikke kendt endnu.

Fonde aflægger ikke regnskab. De er talt med under *No date known* som *N fund(s) left out*, men ikke listet. Kan radaren ikke se, at et papir er en fond (fx en dansk investeringsforening, som Yahoo kalder en aktie), står det som en aktie uden dato.

## Dine egne datoer

- **Gennemgang i journalen**: åbne journalposter med en `review_by`-dato i vinduet, og overskredne. Linket fører til posten i [Notesbogen](brugervejledning/notesbog).
- **Tidsstop i porteføljeforslag**: et forslags valgte aktier, du stadig ejer, med det tidsstop, forslaget satte, og exit-tjekkets status. Se [/propose-portfolio](brugervejledning/claude-code#propose-portfolio).

Slås fra med `calendar.include.reviews`; udbyttedage med `calendar.include.ex_dividend`.

## Samme kalender andre steder

- **Forsiden**: *Soon* viser de samme *high*-punkter som *Next {{settings:calendar.soon_days}} days* for dine rigtige porteføljer. Er der ingen, vises båndet ikke.
- **Holdings & watchlist**: flaget *earnings in N d* (eller *earnings today*) på en aktie, der aflægger regnskab inden for {{settings:calendar.soon_days}} dage; se [Flagene](brugervejledning/beholdninger#flagene).
- **Månedsbriefen**: afsnittet *Kommende uger*; se [Månedsbriefen](brugervejledning/maanedsbrief).
- **Kommandolinjen**: `uv run radar calendar [NAVN…] [--tag T] [--days N] [--json]` skriver de næste dage, en tabel pr. uge og *no date known*. Med `--json` får du det samme som siden.

Alle fire bruger den samme beregning som siden, så de er aldrig uenige.

## Indstillinger

Tærsklerne står under `calendar:` i `config/settings.yaml`; se [Indstillinger](brugervejledning/indstillinger#calendar-regnskabsdatoer).
