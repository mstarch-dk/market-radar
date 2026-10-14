# Månedsbriefen

Den første i hver måned skriver Claude en markedsbrief på din egen computer: `briefs/YYYY-MM-DD.md`. Det er den samme brief, som du får med `/market-brief` (se [Claude Code-skills](brugervejledning/claude-code)), bare startet af en planlagt opgave i Claude-appen, så du ikke skal huske det.

Alt sker lokalt. Radaren henter selv data, læser dine porteføljer, markedssyn og noter, hvor de ligger, og briefen bliver liggende i mappen `briefs/`. Intet sendes til GitHub.

## Sådan kører den

En planlagt opgave i Claude-appen (*Scheduled tasks*) kører den første i hver måned om morgenen:

1. Den opdaterer radaren med `uv run radar run`, ligesom knappen *Update data*.
2. Den læser `reports/summary.json`, dine markedssyn (`uv run radar views --json`), den seneste Discover-scanning, hvis den er under 10 dage gammel, din investorprofil i `notes/investor.md` og dine læsenoter i `notes/`.
3. Den søger efter årsagerne til det vigtigste på nettet og skriver briefen i `briefs/`.

Den committer intet og opretter ingen pull request. Briefen er din, og den ligger kun på din computer.

> **Bemærk:** Planlagte opgaver kører, mens Claude-appen er åben. Er appen lukket den første i måneden, kører opgaven, næste gang du åbner den.

## Hvad briefen indeholder

Briefen har en fast opbygning: TL;DR, regime, positionering og cyklus, rotation, nye momentumledere, nyt fra Discover, dine markedssyn mod data, din portefølje i den sammenhæng og en kø af navne til `/research`. Den holder sig til 6–8 ting, der betyder noget, og hver påstand om nyheder har et kildelink. Manglende data skrives som manglende.

Fordi den kører, hvor dine data er, får briefen det hele med: dine rigtige porteføljer og deres afkast mod ACWI, watchlist, markedssyn, Discover og dine noter.

"Nye" momentumledere og "faldet ud" sammenlignes med radarens egne rangsnapshots i `data/snapshots/`, som bygges op, hver gang radaren opdateres. Har du kun opdateret få gange, er der mindre at sammenligne med i starten.

## Første gang

Den første kørsel beder om lov til de værktøjer, briefen bruger: at køre `uv run radar …` og at søge og læse på nettet. Godkend dem, og vælg at huske valget, så de næste måneder kører uden at vente på dig.

Vil du se resultatet med det samme, kan du starte opgaven med *Run now* i listen over planlagte opgaver, eller blot skrive `/market-brief` i Claude Code.

## Ændre, sætte på pause eller fjerne

Opgaven hedder *Månedsbrief (Market Radar)* og findes under planlagte opgaver i Claude-appen. Der kan du:

- ændre tidspunktet (fx en anden dag eller hver anden uge),
- slå den fra en periode,
- køre den nu,
- se tidligere kørsler og deres resultat.

Du kan også bede Claude om det direkte, fx "flyt månedsbriefen til den 15." eller "sæt månedsbriefen på pause".

## Når noget går galt

- **Ingen ny brief:** var appen lukket, kører opgaven, når du åbner den. Se ellers den seneste kørsel i listen over planlagte opgaver.
- **Briefen siger, at data er forældet:** en kilde fejlede under opdateringen; se [Data og dækning](brugervejledning/data-og-daekning) og [Drift](brugervejledning/drift).
- **Ingen Discover-afsnit:** Discover-scanningen er over 10 dage gammel. Kør den på [Discover](/discover) (*Scan again*) eller med `uv run radar discover`.
- **Ingen afsnit om dine syn:** du har ingen aktive markedssyn; se [Mine markedssyn](brugervejledning/markedssyn).

## Til en anden computer

Skifter du computer, kan du flytte dine porteføljer, watchlist, markedssyn og valg af regimeafstemning med ét bundt; se [Kommandolinjen](brugervejledning/kommandolinjen#flyt-dine-data-til-en-anden-computer). Opret derefter den planlagte opgave igen i Claude-appen på den nye computer.
