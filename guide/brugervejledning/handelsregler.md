# Mine handelsregler

En handelsregel er en regel, du selv vil handle efter: "ingen enkeltaktie over 10 %", "ingen genkøb inden for 30 dage efter et salg", "aldrig sælge mere end 15 % af porteføljen på en uge". På siden [Trading rules](/rules) skriver du dem ned, mens det er roligt. Bagefter kan du spørge reglerne om en konkret handling, før du gør den.

Reglerne er et spejl, aldrig en bom. Radaren blokerer intet, sender intet til din mægler og siger aldrig "gør det". Den viser regel for regel, om handlingen bryder reglen, kommer tæt på eller overholder den, med tallene bag, og hvad der ville få den til at overholde reglen. Teorien bag at binde sig på forhånd står i [Beslutninger, bias og falsifikation](laerebog/adfaerd).

## Skriv en regel

Du kan starte på to måder:

- *Start from a template*: generelle startpunkter, fx et loft pr. aktie, et loft over et tema, en kerne, en genkøbspause og en afkølingsperiode for salg. *Use this* åbner skabelonen i editoren. Skift tallene og begrundelsen til dine egne.
- *Write your own rule*: en tom editor.

Editoren har disse felter:

| Felt | Indhold |
|---|---|
| *The rule, in your words* | Reglen, som du selv vil sige den |
| *What the radar checks* | Reglens slags (se tabellen nedenfor) og dens tal |
| *How strict* | *Hard* (den bryder jeg ikke), *Soft* (kun med en begrundelse) eller *Reminder* (værd at tænke over) |
| *Which portfolios* | Dine rigtige porteføljer, alle (også virtuelle) eller udvalgte, evt. kun én kontotype, et tag eller en stil |
| *Why I have this rule* | Lektien bag reglen, med dine egne ord |

Strengheden er din egen etiket. Den bestemmer kun rækkefølge og farve, aldrig om noget blokeres.

### Slags regler

| Slags | Bryder, når … | Forslag til at overholde |
|---|---|---|
| *Max weight per name* | navnet efter et køb vejer mere end loftet | det største beløb, der kan være under loftet |
| *Max weight in a theme, sector or region* | de navne, der hører til temaet, vejer mere end loftet efter købet | det største beløb, der kan være under loftet |
| *Min weight in the core* | kernen (de fonde og aktier, du nævner) vejer mindre end gulvet efter handlen | det største beløb, der holder kernen på gulvet |
| *Min trade size* | handlen er mindre end minimum | handl mindst minimum, eller lad være |
| *Max number of names* | et køb af et nyt navn giver flere navne end maksimum | – |
| *No buying back soon after a sale* | du køber et navn, du har solgt inden for et antal dage | den første dag, det er tilladt |
| *Sell cooling-off* | salget og dine salg de seneste dage er mere end en andel af porteføljen | hvor meget du kan sælge nu, og hvornår vinduet er fri |
| *Max trades per month* | handlen er en for mange i måneden | den første dag i næste måned |
| *No averaging down* | du køber mere af en position, der ligger mere end en grænse under din gennemsnitspris | – |
| *Only buy above a moving average* | kursen er under 50- eller 200-dages gennemsnittet | den kurs, du kan vente på |
| *No chasing a run-up* | kursen er steget mere end en grænse på 3 måneder | – |
| *Min momentum score* | momentumscoren er under minimum | – |
| *Short-term trades in one account kind* | en kortsigtet handel (horisont op til et antal måneder) ligger i en anden kontotype | den kontotype, reglen nævner |
| *Exit rule first* | der ikke er en åben journalindførsel for navnet med et afsnit om exit-regler | skriv indførslen først med `/journal` |
| *Judgment* | aldrig: radaren kan ikke tjekke den | den vises som et spørgsmål til dig |

Et tema bruger samme ordforråd som dine [markedssyn](brugervejledning/markedssyn): ETF (navnet selv og alle aktier, hvis afkast i forhold til ACWI følger ETF'en), sektor, branche, region og ticker. "AI-chips højst 25 %" kan fx være ETF'en SMH plus branchen Semiconductors.

Brede verdensfonde (listen `risk.world_funds` i indstillingerne) tæller ikke under *Max weight per name*: de er spredt over tusindvis af selskaber.

### Stil

En regel kan gælde én stil af positioner: momentum, value, core eller tactical. "Ingen tilkøb i en momentumposition under 200-dages gennemsnittet" er et eksempel. Radaren læser stilen fra den handling, du tester, og ellers fra feltet `style:` i navnets åbne journalindførsel. Har positionen ingen stil, er svaret *Unknown*, ikke "overholder".

## Hvad hver regel siger

Hver regel giver ét af disse svar:

| Svar | Betyder |
|---|---|
| *Breaks* | Handlingen bryder reglen |
| *Close to* | Inden for 10 % af grænsen (ved *Only buy above a moving average*: højst 2 % over gennemsnittet) |
| *Unknown* | Et input mangler, fx en kurs, en valutakurs, et gennemsnit eller en stil. Beskeden siger hvilket |
| *Ask yourself* | En *Judgment*-regel: et spørgsmål til dig |
| *Complies* | Handlingen overholder reglen |
| *Doesn't apply* | Forkert side (fx en regel om køb ved et salg), en anden portefølje end reglens, eller en anden stil |

*Unknown* betyder aldrig "overholder". Mangler data, siger radaren det.

Vægte er altid en andel af den investerede værdi i DKK i reglens porteføljer, og beskeden siger hvilke og hvor meget: "NVDA would be 22.6 % of your real portfolios (249.718 DKK invested, cash not counted)". Kontanter tælles ikke med, fordi ikke alle porteføljer har en kontantkonto. En position uden kurs eller valutakurs bliver udeladt og nævnt.

## Test en handling

*Test an action* øverst på siden: vælg køb eller salg, ticker, portefølje og et beløb i DKK, et antal aktier eller (ved salg) en andel af positionen (0,5 = halvdelen, 1 = det hele). Stil og horisont er valgfrie; uden dem bruges den åbne journalindførsel. *Check against my rules* viser én række pr. regel, brud først, med tallene og hvad der skal til for at overholde reglen. Intet gemmes.

Prisen er dagens lukkekurs, omregnet til DKK. Fra en tickerside åbner *Check against my rules* siden med tickeren udfyldt.

## Brud lige nu

*Breaks right now* viser, hvad dine beholdninger bryder eller er tæt på i dag, uden nogen handling: lofter pr. navn og tema, kernens gulv og antal navne. Det samme vises:

- som et flag på [Holdings & watchlist](/me): *breaks a rule* eller *near a rule* (se [Mine beholdninger og watchlist](brugervejledning/beholdninger)),
- i den månedlige brief under *Dine handelsregler* (se [Månedsbriefen](brugervejledning/maanedsbrief)).

## Når du registrerer en handel

Når du tilføjer et køb eller salg under [Portfolio](/portfolio), tjekkes det også mod dine regler. De regler, handlen bryder eller er tæt på, står som advarsler sammen med de andre, og du skal krydse af, før handlen gemmes, præcis som ved en usædvanlig kurs. Bryder handlen en regel, kan du skrive, hvorfor du gør det alligevel. Tjekket, din beslutning og begrundelsen gemmes sammen med handlen. Ændrer du en eksisterende handel, tjekkes reglerne ikke.

## Ville reglerne have hjulpet?

*Would my rules have helped?* nederst på siden kører dagens regler på dine egne tidligere køb og salg i dine rigtige porteføljer. Hver handel tjekkes, som den så ud den dag: beholdningen og handlerne før den, kurser til og med den dag. For hver regel og side ser du, hvor mange handler den ville have markeret, hvor mange den lod gå igennem, og hvad navnene gjorde bagefter i DKK i forhold til ACWI over de samme dage.

Det er beskrivende og et lille udsnit. Et markeret køb, der siden har klaret sig dårligere end ACWI, er en handel, reglen ville have sparet dig for. Det viser, hvad der skete, ikke at reglen virker. Radaren påstår ingen signifikans.

## Kommandolinjen og Claude

- `uv run radar rules [--json] [--archived]`: dine regler.
- `uv run radar rules check buy NOVO-B.CO 20000 --portfolio "frie midler" [--style momentum] [--horizon 6m] [--date D] [--json] [--log]`: test en handling. Beløbet er DKK, `50sh` er 50 aktier, og ved salg er `half`, `all` eller `0.25` en andel af positionen. `--log` gemmer tjekket.
- `uv run radar rules standing [--json]`, `rules replay [--json]`, `rules add --from-json FIL`, `rules decision ID went_ahead|changed|dropped [--reason …]`.

Claude-skillen `/rules` hjælper dig med at skrive reglerne, også ud fra en gennemgang af dine egne handler, og skriver kun en regel, når du har sagt ja til den. `/journal` tjekker en handling mod reglerne, før indførslen skrives, og `/propose-portfolio` respekterer dine lofter. Se [Claude Code-skills](brugervejledning/claude-code).
