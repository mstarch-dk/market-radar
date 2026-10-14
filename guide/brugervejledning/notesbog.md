# Notesbogen: briefs, research og journal

Siden [Notebook](/notebook) i gruppen *Mine* samler det, som Claude-skills har skrevet til dig: markedsbriefs, research-notater, sammenligninger og din beslutningsjournal. Du læser dem her; du skriver dem med skills i Claude Code (se [Claude Code-skills](brugervejledning/claude-code)).

Filerne ligger i mapperne `briefs/`, `research/` og `journal/` på din computer. De er personlige, kommer aldrig med i git og deles ikke.

## Briefs

Fanen *Briefs* viser den nyeste markedsbrief i fuld længde og en liste over de tidligere. En brief skrives af `/market-brief` og af den planlagte månedsbrief den første i hver måned (se [Månedsbriefen](brugervejledning/maanedsbrief)).

## Research

Fanen *Research* har to lister:

- **Research memos**: ét notat pr. ticker fra `/research <ticker>`, med link til tickerprofilen.
- **Comparisons**: sammenligninger fra `/compare <t1> <t2> …`, nyeste først.

## Journal

Fanen *Journal* viser dine beslutninger i en tabel med dato, ticker, handling (*buy*, *add*, *trim*, *sell*, *pass*), konto, horisont, status og hvornår beslutningen skal gennemgås. Tabellen kan sorteres og filtreres som de andre tabeller i appen (se [Sådan finder du rundt](brugervejledning/navigation#tabellerne)).

- **review due** betyder, at en åben beslutning har passeret sin gennemgangsdato. Antallet står også på fanen.
- Under tabellen ligger de månedlige gennemgange fra `/journal review`.

En beslutning skriver du med fx `/journal buy RHM.DE …` i Claude Code. Claude spørger efter din tese, konto, horisont og exit-regel og gemmer radarens tal fra beslutningsøjeblikket. Status ændres kun, når du selv beder om det.

> **Bemærk:** Mangler en journalfil sine felter øverst (front matter), vises den stadig, men med en note om, hvad der mangler. Status og gennemgangsdato kan så ikke læses.

## At læse et dokument

Klik på en titel for at åbne dokumentet. Tabeller, links og formler vises som i guiden. Journalindlæg har en lille boks øverst med ticker, handling, konto, horisont, status og gennemgangsdato. *← Notebook* fører dig tilbage til den fane, du kom fra.

## På tickerprofilen

Har du notater, sammenligninger eller beslutninger om en ticker, står de øverst på dens [tickerprofil](brugervejledning/tickerprofil) under *In your notebook*, med *review due*, hvis en beslutning skal gennemgås.
