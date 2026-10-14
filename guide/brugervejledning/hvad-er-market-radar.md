# Hvad er Market Radar?

Market Radar er et personligt analyseværktøj til dig, der investerer selv som dansk privatinvestor, i frie midler og på aktiesparekonto (ASK). Det kører på din egen computer, henter gratis, offentlige data og samler markedsregime, sektor- og temarotation, momentum og din egen portefølje ét sted.

Værktøjet er bygget til at være **proaktivt**: det skal hjælpe dig med at opdage skift tidligt, i stedet for at forklare dem bagefter. Horisonten er bevidst 1–6 måneder, hvor momentum og rotation historisk har haft mest at sige.

> **Bemærk:** Market Radar er analyse, ikke rådgivning. Data kommer for det meste fra Yahoo Finance og andre gratis kilder uden garanti for kvaliteten. Tjek altid det vigtige selv, før du handler.

> **Bemærk:** Data må kun bruges personligt og ikke-kommercielt. Du må ikke gøre radaren tilgængelig for andre som hjemmeside eller videregive de hentede data. Se [Datakilder og licenser](brugervejledning/datalicenser).

## Grundidéerne

### Ét benchmark: MSCI ACWI
Alt i radaren måles mod MSCI ACWI, verdensindekset med både udviklede markeder og vækstmarkeder. Det gælder sektorer, temaer og enkeltaktier, og det gælder din egen portefølje. Spørgsmålet er hele tiden det samme: er denne idé bedre end bare at eje verdensindekset? Hvis svaret ikke er tydeligt ja, er den passive løsning et ærligt alternativ. Baggrunden står i [Benchmark og relativt afkast](laerebog/benchmark).

### Vejret først, så strømmen, så navnene
Siderne er bygget til at blive læst i en bestemt rækkefølge:

1. **Regimet:** er markedet som helhed risk-on, risk-off eller blandet? Det er "vejret", som alle andre beslutninger træffes i.
2. **Rotationen:** hvilke sektorer, regioner, temaer og faktorer får mere af pengestrømmen, og hvilke mister den?
3. **Momentum:** hvilke konkrete aktier fører i hver region, og klumper de sig sammen i bestemte brancher?
4. **Dig:** hvordan passer dine beholdninger, din watchlist og dine markedssyn ind i billedet?

### Sandhed om data
Radaren siger hellere "ved ikke" end at gætte:

- Manglende data vises som manglende (en streg, *n/a* eller "no data"), aldrig som 0.
- Hver kilde har en alder og en grænse. Et input, der er ældre end sin grænse, markeres *stale* og tæller ikke med i regimeafstemningen.
- En kilde, der fejler under en opdatering, beholder sine seneste data, og fejlen står på siden [Data & coverage](/data).
- Siden *Data & coverage* har også en liste over det, radaren **ikke** kan se (blinde vinkler), fx fund flows og virksomhedernes regnskaber ud over Yahoos opsummering.

### Graderede aflæsninger
Mange tal er farvet efter, hvor tæt de er på en tærskel, på en skala i ni trin fra advarsel (orange til rød) over neutral (grå) til gunstig (grøn). Ordet står altid ved siden af farven, så farven aldrig er det eneste signal. Hold musen over for at se den nærmeste tærskel. Envejs-risikomål som VIX, volatilitet og beta bruger kun den grå-til-røde halvdel.

## Et kort over siderne

Fanerne øverst i appen følger rækkefølgen ovenfor. Her er hvad hver side gør, og hvor i vejledningen den er beskrevet:

| Fane | Hvad den viser | Kapitel |
|---|---|---|
| *Regime* | Risk-on/risk-off-afstemningen og hver indikators aflæsning | [Regime](brugervejledning/regime) |
| *Sector rotation* | Amerikanske og europæiske sektorer samt regioner på en rotationsgraf (RRG) | [Sektorrotation](brugervejledning/sektorrotation) |
| *Themes & factors* | Tema- og faktor-ETF'er med UCITS-alternativ og positivliste-status | [Temaer og faktorer](brugervejledning/temaer-og-faktorer) |
| *Momentum* | De stærkeste aktier pr. region, nye navne og klynger | [Momentum](brugervejledning/momentum) |
| *Discover* | Et bredere net: nordiske og europæiske aktier og UCITS-ETF'er i et heatmap og en screener | [Discover](brugervejledning/discover) |
| *Positioning & cycle* | Indtjeningsrevisioner, værdiansættelse, OECD-cyklus, renter, futurespositionering og sentiment | [Positionering og cyklus](brugervejledning/positionering) |
| *Holdings & watchlist* | Dine positioner i DKK mod ACWI, stop og kursmål | [Mine beholdninger og watchlist](brugervejledning/beholdninger) |
| *Market views* | Dine egne markedssyn, holdt op mod data | [Mine markedssyn](brugervejledning/markedssyn) |
| *Notebook* | Briefs, research-notater, sammenligninger og din beslutningsjournal | [Notesbogen](brugervejledning/notesbog) |
| *Portfolio* | Handler, kontanter, import og porteføljer | [Portefølje](brugervejledning/portefolje) |
| *Returns* | Afkast over tid mod ACWI (TWR og MWR) | [Afkast over tid](brugervejledning/afkast) |
| *Data & coverage* | Kilder, alder, status og blinde vinkler | [Data og dækning](brugervejledning/data-og-daekning) |
| *Operations* | Forespørgsler, fejl, jobs og pauser pr. kilde | [Drift](brugervejledning/drift) |

Derudover har hver aktie og ETF sin egen tickerprofil med graf, teknik, risiko, analytikere og værdiansættelse. Den åbner du ved at søge eller klikke på et tickersymbol; se [Tickerprofilen](brugervejledning/tickerprofil).

## Hvad radaren ikke er

- **Ikke en købsliste.** En høj momentumscore eller en sektor i kvadranten fører (*Leading*) er en grund til at undersøge nærmere, ikke et signal om at købe.
- **Ikke en prognose.** Regimet beskriver, hvad indikatorerne viser i dag. Det forudsiger ikke næste måned.
- **Ikke realtid.** Alle kurser er dagslukkekurser, og nogle kilder opdateres kun ugentligt eller månedligt.
- **Ikke skatterådgivning.** Positivliste-status og kontotyper er hjælp til at finde rundt; tjek de aktuelle regler på skat.dk.

## Dine data bliver hos dig

Market Radar kører på `127.0.0.1` og kan kun nås fra din egen computer. Der er intet login og ingen konto. Dine handler, din watchlist og dine noter ligger i lokale mapper og forlader aldrig maskinen. Hvordan mapperne er delt op, står i [Data og opdatering](brugervejledning/data-og-opdatering#hvor-dine-data-ligger).

## De to bøger

Guiden består af to bøger, som du skifter mellem i sidepanelet:

- **Brugervejledningen** (denne bog) forklarer appen side for side: hvad du ser, hvordan du læser det, og hvordan du bruger det i praksis.
- **Lærebogen** forklarer teorien bag: hvad momentum er, og hvorfor det virker, hvordan en rotationsgraf er bygget, hvad kreditspænd og VIX siger om risikoappetit, og hvordan man måler afkast rigtigt.

De to bøger henviser til hinanden. Står du på en side i appen og vil vide, hvorfor en tærskel er sat, hvor den er, så følg linket til lærebogen. Gode steder at begynde:

- [Momentumeffekten](laerebog/momentumeffekten) og [Radarens momentumscore](laerebog/momentumscore) til *Momentum* og *Discover*
- [Relativ styrke](laerebog/relativ-styrke) og [Rotationsgrafen (RRG)](laerebog/rrg) til *Sector rotation* og *Themes & factors*
- [Risk-on og risk-off](laerebog/risk-on-risk-off) og [Radarens afstemningsmodel](laerebog/afstemningsmodellen) til *Regime*
- [Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr) til *Returns*
- [Dansk skat for investorer](laerebog/skat) til positivlisten og kontotyperne

## Valgfrit: Claude Code

Bruger du Claude Code, kan radarens data bruges som udgangspunkt for skriftlige analyser: en dateret markedsbrief, et researchnotat om én aktie, en ærlig sammenligning af flere navne og en beslutningsdagbog. Det er beskrevet i [Claude Code-skills](brugervejledning/claude-code). Appen virker fuldt ud uden.

## Næste skridt

Gå videre til [Installation og første start](brugervejledning/installation), hvis du ikke har Market Radar kørende endnu, eller til [Sådan finder du rundt](brugervejledning/navigation) for en tur rundt i brugerfladen.
