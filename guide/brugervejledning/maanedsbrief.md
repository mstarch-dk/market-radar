# Månedsbriefen

Den første i hver måned skriver Claude en markedsbrief på din egen computer: `briefs/YYYY-MM-DD.md` i din datamappe. Det er den samme brief, som du får med `/market-brief` (se [Claude Code-skills](brugervejledning/claude-code)), bare startet af en planlagt opgave i Claude-appen, så du ikke skal huske det.

Alt sker lokalt. Radaren henter selv data, læser dine porteføljer, markedssyn og noter, hvor de ligger, og briefen bliver liggende i mappen `briefs/` i datamappen. Intet sendes til GitHub.

> **Bemærk:** Opgaven finder datamappen med `uv run radar paths --json`. Datamappen ligger uden for projektmappen, så Claude Code kan spørge om lov til at læse og skrive der. Svar ja, gerne med "altid", så opgaven ikke venter på dig næste måned.

## Sådan kører den

En planlagt opgave i Claude-appen (*Scheduled tasks*) kører den første i hver måned om morgenen:

1. Den opdaterer radaren med `uv run radar run`, ligesom knappen *Update data*. En gang om måneden opretter den også månedens kurv i scorens papirspor (tagget `picks-live`) og bringer de tidligere kurve up to date; se [Test momentumscoren på historikken](brugervejledning/scoretest#papirsporet).
2. Den læser `summary.json` (i cache-mappens `reports/`), dine markedssyn (`uv run radar views --json`), den seneste Discover-scanning, hvis den er under 10 dage gammel, din investorprofil i `notes/investor.md` og dine læsenoter i `notes/` i datamappen.
3. Den søger efter årsagerne til det vigtigste på nettet og skriver briefen i `briefs/` i datamappen.

Den committer intet og opretter ingen pull request. Briefen er din, og den ligger kun på din computer.

> **Bemærk:** Planlagte opgaver kører, mens Claude-appen er åben. Er appen lukket den første i måneden, kører opgaven, næste gang du åbner den.

## Hvad briefen indeholder

Briefen er skrevet på dansk og har en fast opbygning: TL;DR, regime, positionering og cyklus, rotation, nye momentumledere, nyt fra Discover, dine markedssyn mod data, din portefølje i den sammenhæng (med *Kommende uger*) og en kø af navne til `/research`. Den holder sig til 6–8 ting, der betyder noget, og hver påstand om nyheder har et kildelink. Manglende data skrives som manglende.

Fordi den kører, hvor dine data er, får briefen det hele med: dine rigtige porteføljer og deres afkast mod ACWI, watchlist, markedssyn, Discover og dine noter.

*Kommende uger* er de næste {{settings:calendar.days}} dage fra [Kalender](brugervejledning/kalender): regnskaber og udbyttedage for det, du ejer og følger, og dine egne gennemgangsdatoer. De fremhævede kommer først, med de samme grunde som på siden ("5,2 % af porteføljen", "ingen fast dato"), og for hver af dem skriver Claude kort, hvad markedet holder øje med i regnskabet. En aktie uden kendt dato står som "ingen dato kendt". Briefen anbefaler aldrig at handle før et regnskab.

"Nye" momentumledere og "faldet ud" sammenlignes med radarens egne rangsnapshots i `history/snapshots/` i datamappen, som bygges op, hver gang radaren opdateres. Har du kun opdateret få gange, er der mindre at sammenligne med i starten.

## Som podcast (NotebookLM)

Vil du hellere lytte til briefen, fx på vej på arbejde, kan Claude skrive en lytteversion, som du gør til en podcast i Googles NotebookLM (en *Audio Overview*, hvor to værter taler om stoffet).

Skriv `/market-brief podcast`. Ud over den almindelige brief får du så `briefs/lyt/YYYY-MM-DD.md`: den samme historie skrevet til at blive hørt, uden tabeller og links, med tallene rundet af og sagt i ord og forkortelserne forklaret. Lytteversionen vises ikke på [Notebook](/notebook); den er kun til NotebookLM.

Sådan laver du podcasten:

1. Åbn [notebooklm.google.com](https://notebooklm.google.com) eller NotebookLM-appen på telefonen, og opret en ny notesbog.
2. Tilføj lytteversionen som kilde: upload filen, eller indsæt teksten.
3. Vælg *Audio Overview* → *Customize*, vælg sproget Dansk, og indsæt prompten, der står øverst i filen.
4. Vælg *Generate*, og lyt i NotebookLM-appen, når lydfilen er klar.

Det gratis NotebookLM laver kun et begrænset antal lydoversigter om dagen (cirka 3 i skrivende stund).

> **Bemærk:** Teksten sendes til Google. Derfor er lytteversionen som standard kun om markedet: dine porteføljer, beholdninger, watchlist, solgte navne, markedssyn og noter er udeladt. Vil du have dem med, skriver du `/market-brief podcast personal`. Hold notesbogen og lydfilen private; se [Datakilder og licenser](brugervejledning/datalicenser).

Vil du have en lytteversion hver måned, kan du bede Claude om at tilføje `podcast` til den planlagte opgave. Upload til NotebookLM sker stadig i hånden, for NotebookLM har ingen officiel adgang for programmer.

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
