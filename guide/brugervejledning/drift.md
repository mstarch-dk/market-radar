# Drift: forespørgsler, fejl og pauser

Siden [Operations](/ops) handler om maskinrummet, ikke om markederne. Den viser hver forespørgsel, radaren sender til en ekstern kilde (Yahoo, FRED, CFTC og de andre), opdateringer der fejlede, svar der ikke kunne læses, fejl i selve appen, og opdaterings- og scanningsjob med deres log. Intet herfra indgår i en markedsaflæsning.

Du har brug for siden, når en opdatering er gået galt, når en kilde bliver ved med at være forældet, eller når du vil vide, om radaren er blevet bremset af et websted.

## Overblik øverst

Fire felter giver status med det samme:

| Felt | Viser |
|---|---|
| *Last update* | Status for den seneste dataopdatering (fra appen eller `radar run`/`radar update`), hvornår den startede og hvor længe den tog |
| *Requests, last 24 h* | Antal forespørgsler det seneste døgn, og hvor mange der fejlede |
| *Error events, last 24 h* | Fejlhændelser det seneste døgn: kilder der fejlede, svar der ikke kunne læses, serverfejl |
| *Paused sites* | Antal websteder på pause lige nu, og om nogen er over dagens budget |

Er et websted på pause, står der en gul boks under felterne med webstedet, hvornår pausen slutter, og hvorfor. Knappen *Resume now* ophæver pausen med det samme (se [Pauser efter for mange forespørgsler](#pauser-efter-for-mange-forespørgsler)).

Siden opdaterer sig selv hvert halve minut.

## Websteder og kilder

Tabellen under *Sites and sources* har én række pr. kombination af websted (*Host*) og datakilde (*Source*). Knapperne *24 h*, *7 days* og *30 days* vælger vinduet; valget står i adressen som `?days=`.

| Kolonne | Betyder |
|---|---|
| *Host* | Webstedet, fx `query1.finance.yahoo.com` |
| *Source* | Den kilde eller det job, forespørgslen hørte til, fx en opdateringsstep eller `app:…` for appens egne opslag |
| *Requests* | Antal forespørgsler i vinduet |
| *Errors* | Fejlede forespørgsler og andel i procent |
| *429s* | Antal svar med HTTP 429 ("for mange forespørgsler") |
| *p50* / *p95* | Svartid: halvdelen var hurtigere end p50, 95 % hurtigere end p95 |
| *Today / budget* | Forespørgsler i dag mod webstedets bløde dagsbudget (rødt, når det er overskredet) |
| *Per day* | Små søjler med antal pr. dag |
| *Last request* | Hvornår den seneste blev sendt |
| *Last error* | Den seneste fejl og hvornår |

En fejl er en forespørgsel uden svar (timeout, afvist forbindelse) eller med en HTTP-fejlkode. Svar, en kilde forventes at give, tæller ikke: fx når FactSet ikke har udgivet en rapport den dag, eller CBOE holder lukket. Svartiden måler tiden på linjen, ikke ventetiden mellem forsøg. Er intet blevet målt, står der –, ikke 0.

## Hændelser

Tabellen *Events* viser hændelser, nyeste først. Hver har et niveau og en type:

- **Niveau**: *info*, *warn* eller *error*.
- **Type**:
  - *source*: en datakilde blev opdateret eller fejlede.
  - *parse*: kilden svarede, men ikke i den forventede form (ofte et ændret layout hos kilden).
  - *api*: en fejl i selve appen.
  - *job*: en opdatering eller scanning stoppede.
  - *throttle*: et websted blev sat på pause, genoptaget eller gik over budget.
  - *doctor*: et sundhedstjek.

Kolonnerne kan filtreres, så du fx kun ser fejl af typen *parse*. Har en fejl et teknisk spor, kan du folde *Traceback* ud under beskeden. Det er nyttigt, hvis du vil rapportere en fejl. Kolonnen *Job* fortæller, hvilket job hændelsen hørte til.

## Job og logs

Under *Jobs* står de seneste kørsler: dataopdateringer fra appen (`update`), Discover-scanninger (`discover`) og kørsler fra kommandolinjen (`cli_run`, `cli_update`, `cli_discover`). Hver har status (*done*, *failed*, *running* eller *interrupted*), starttid, varighed og eventuel fejl. *Log* folder jobbets log ud med antal forespørgsler og fejl.

*interrupted* betyder, at appen blev lukket, mens jobbet kørte. Det markeres næste gang appen starter.

## Seneste forespørgsler

*Recent requests* er foldet sammen fra start. Folder du det ud, ser du de seneste 300 forespørgsler én for én: tidspunkt, websted, sti, kilde, statuskode, tid og forsøgsnummer (*Try*).

> **Bemærk:** Radaren gemmer kun stien, aldrig forespørgselsstrengen (delen efter `?`). Nøgler og lignende i selve stien (`key=`, `token=`, `crumb=` m.fl.) bliver maskeret. Loggen indeholder derfor ingen adgangsnøgler.

## Sundhedstjek

Under *Health checks* kører du de samme tjek som `uv run radar doctor`:

- *Check the setup* tjekker Python, den byggede webapp, markedsdata, rapporten, positivlisten, din portefølje og investorprofilen til Claude.
- *Check + contact every source* kontakter desuden hver datakilde én gang. Det tager nogle sekunder.

Hvert tjek får *ok*, *warn*, *fail* eller *info* og, ved problemer, en linje med hvad du kan gøre. Se [Fejlfinding og spørgsmål](brugervejledning/fejlfinding).

## Sådan holder radaren tempoet

Gratis datakilder bryder sig ikke om at blive bombarderet. Sender et program for mange forespørgsler for hurtigt, kan webstedet blokere det i en periode. Radaren sender derfor alle forespørgsler gennem ét lag, der holder et roligt tempo pr. websted, og som bakker af, når et websted beder om det. Grænserne står i `config/settings.yaml` under `network:`.

### Tempo pr. websted

Hvert websted har sit eget tempo: et antal forespørgsler i sekundet, et lille antal, der må gå på én gang efter en stille periode, og et loft over hvor mange der kører samtidig. Websteder uden egen indstilling får standarden: {{settings:network.default.rate}} forespørgsler i sekundet, op til {{settings:network.default.burst}} på én gang og højst {{settings:network.default.concurrency}} samtidig. Langsomme eller sårbare kilder som multpl.com og AAII har et meget lavere tempo, og alle Yahoos websteder deler ét fælles tempo. Venter radaren på sin tur, bliver opdateringen bare lidt langsommere.

### Nye forsøg

Svarer et websted ikke, eller svarer det med en midlertidig fejl (HTTP 429 eller 5xx), prøver radaren igen op til {{settings:network.default.retries}} gange med stigende ventetid, først {{settings:network.default.backoff}} sekunder og derefter dobbelt så længe. Beder webstedet selv om en bestemt ventetid (`Retry-After`), respekteres den, medmindre den er længere end {{settings:network.default.max_wait}} sekunder; så opgives forsøget. Andre fejl, fx at en side ikke findes, prøves ikke igen. Yahoo-opslag går gennem biblioteket yfinance, som selv står for sine nye forsøg; radaren holder tempoet og tæller med.

### Pauser efter for mange forespørgsler

HTTP 429 betyder "for mange forespørgsler": webstedet beder radaren sætte farten ned. Får radaren {{settings:network.cooldown.trip}} sådanne svar fra samme websted inden for {{settings:network.cooldown.window_min}} minutter, sættes webstedet på pause i {{settings:network.cooldown.cooldown_min}} minutter. Sker det igen samme dag, fordobles pausen hver gang, dog højst til {{settings:network.cooldown.max_cooldown_min}} minutter.

Under en pause sendes intet til webstedet. De trin i opdateringen, der skal bruge det, fejler med det samme og beholder deres seneste data, ligesom ved enhver anden fejl. Pausen gemmes i `data/ops.db`, så appen og kommandolinjen respekterer den samme pause.

Pausen ophører af sig selv. Vil du ikke vente, kan du klikke *Resume now*. Gør det kun, hvis du har en grund til at tro, at webstedet er klar igen: kommer der straks nye 429-svar, bliver næste pause længere.

### Blødt dagsbudget

Et websted kan have et dagsbudget, fx Yahoo. Går radaren over budgettet, bliver det en advarsel på siden (rødt i *Today / budget* og i feltet *Paused sites*) og en hændelse af typen *throttle*. Det blokerer aldrig noget. Et overskredet budget er et tegn på, at noget bruger usædvanligt mange opslag.

> **Bemærk:** Radaren sender én ærlig identifikation (User-Agent) og bruger hverken proxyer eller skiftende identiteter for at komme uden om grænser.

## Kommandolinjen

`uv run radar ops` giver det samme overblik i terminalen for de seneste 7 dage: forespørgsler og fejl det seneste døgn, den seneste opdatering, websteder på pause, websteder over budget og en tabel pr. websted og kilde med antal, fejlprocent, 429'er, p50, p95 og seneste fejl.

```
uv run radar ops
uv run radar ops --days 30
uv run radar ops --errors     # også de seneste 20 fejlhændelser
```

`radar run`, `radar update` og `radar discover` registreres som job med deres log, så du også kan se dem på siden.

## Loggens størrelse

Driftsloggen ligger i `data/ops.db`. Forespørgsler gemmes i {{settings:ops.keep_requests_days}} dage, hændelser og job i {{settings:ops.keep_events_days}} dage; ældre rækker ryddes op efter hvert job og når appen starter.

Filen kan slettes når som helst, mens appen ikke kører. Intet i den indgår i en markedsaflæsning, og radaren opretter en ny tom log. Du mister kun historikken på denne side og eventuelle aktive pauser.
