# Dine data, backup og opdatering

Market Radar holder dine egne data adskilt fra selve programmet. Programmappen (den mappe, du pakkede zip-filen ud i) indeholder kun koden, standardindstillingerne og guiden. Alt, hvad der er dit, ligger i en **datamappe** for sig, og markedsdata ligger i en **cache-mappe** et tredje sted. Derfor kan du skifte til en ny version uden at flytte noget, og en ny version rører aldrig dine data uden først at tage en backup.

## Tre slags data

| Slags | Hvad | Hvor | Kan hentes igen? |
|---|---|---|---|
| Dine data | Porteføljer, handler, markedssyn, watchlist, dine valg i appen, noter, briefs, research, journal, eksporter, filer fra din bank | Datamappen | **Nej** |
| Historik | Det, radaren har samlet op kørsel for kørsel: rangsnapshots, analytikernes kursmål, ugentlige P/E-snapshots m.m. | `history/` i datamappen | **Nej** |
| Markedsdata | Kurser, makroserier, profiler, Discover-universet, kildeloggen, driftsloggen og de byggede rapporter | Cache-mappen | Ja, ved næste opdatering |

Historikken er ikke privat, men den kan ikke hentes igen: kilderne viser kun dagens tal (eller nogle få dage eller et år tilbage), så radarens egne snapshots er den eneste kopi af fortiden. Derfor ligger den i datamappen og kommer med i backuppen.

### Datamappen

| Mappe eller fil | Indhold | Kan hentes igen? |
|---|---|---|
| `radar.db` | Dine porteføljer og handler, markedssyn, ændringer til watchlisten og valg i appen (fx regimeafstemningen) | **Nej** |
| `notes/` | Din investorprofil (`investor.md`) og egne noter | **Nej** |
| `briefs/`, `research/`, `journal/` | Det, Claude Code-skills skriver | **Nej** |
| `exports/` | Eksporter og sammenligninger | **Nej** |
| `imports/` | Filer fra din bank eller mægler | Kun fra banken |
| `history/` | Rangsnapshots (`snapshots/`), Discover-snapshots, analytikerkonsensus som hentet, ugentlige P/E-snapshots for aktier og ETF'er, FactSet-rapporter og put/call-data ud over det seneste år | **Nej** |
| `backups/` | Sikkerhedskopier (se [Backup](#backup)) | – |
| `README.txt` | En kort forklaring på dansk af mappens indhold | – |
| `market-radar.json` | Datamappens format, hvilke versioner af Market Radar der har brugt den, en log over hvad der er sket med den, din anden backupmappe og dit valg om opdateringstjek | – |

### Cache-mappen

Cache-mappen indeholder alt det, `radar run` kan hente eller bygge igen: kurser, makroserier, positionering, sentiment, markedets værdiansættelse, tickerprofiler, Discover-universet og dets kurser, opdateringsloggen (`sources.json`), driftsloggen (`ops.db`) og svaret fra opdateringstjekket. Undermappen `reports/` holder dashboardet (`dashboard.json`), `summary.json` til Claude Code og rapporterne fra Discover, scoretesten og simuleringerne.

Du kan slette cache-mappen når som helst, når appen er lukket. Næste opdatering henter det hele igen; den første tager et par minutter. Dine data og historikken bliver liggende.

## Hvor mapperne ligger

| | Windows | Mac | Linux |
|---|---|---|---|
| Datamappe (standard) | `C:\Users\<navn>\Market Radar` | `/Users/<navn>/Market Radar` | `/home/<navn>/Market Radar` |
| Cache-mappe | `%LOCALAPPDATA%\MarketRadar\Cache` | `~/Library/Caches/MarketRadar` | `~/.cache/MarketRadar` |
| Hvor computeren husker datamappen | `%LOCALAPPDATA%\MarketRadar\location.json` | `~/Library/Application Support/MarketRadar/location.json` | `~/.config/MarketRadar/location.json` |

Datamappen kan ligge, hvor du vil; du vælger den første gang. Siden [Data & coverage](/data) viser under *Your data*, hvor hver mappe ligger, hvor mange filer den har, og en knap *Open*, der åbner mappen. Fra kommandolinjen viser `uv run radar paths` det samme og hvordan appen fandt mappen (`--json` giver det som JSON, som Claude Code-skills bruger).

### Filen, der husker datamappen

Computeren husker, hvor datamappen ligger, i en lille fil, `location.json`, uden for programmappen. Derfor finder enhver ny version, du pakker ud, dine data af sig selv. Sletter du filen, viser appen opsætningsskærmen igen næste gang.

Til særlige behov kan du pege et andet sted hen:

- `--home STI` på en kommando bruger den datamappe i stedet, kun for den kommando.
- Miljøvariablen `MARKET_RADAR_HOME` vælger datamappen, `MARKET_RADAR_CACHE` cache-mappen, og `MARKET_RADAR_CONFIG` mappen med `location.json`.

## Første start af en version med datamappe

Første gang du starter en version med datamappe (0.2.0 eller nyere), viser appen en opsætningsskærm, *Welcome to Market Radar …*, i stedet for siderne. Du vælger én gang, hvor dine data skal ligge.

### Flyt dine data fra en ældre version

1. **Find den gamle mappe.** Under *Copy your data from an earlier version* lister appen de gamle Market Radar-mapper med data, den har fundet: programmappen selv (*this folder*) og mapper ved siden af den, fx den gamle version, når du har pakket den nye ud lige ved siden af. For hver mappe står, hvad den indeholder (antal handler, porteføljer, noter, research, historikfiler) og hvornår der sidst blev ændret noget. En mappe, der allerede er kopieret fra, er markeret *(copied before)*.
2. **Ligger den et andet sted**, så skriv stien i feltet og klik *Look there*. Appen leder kun automatisk i mappen over programmappen; på en Mac ville en bredere søgning få systemet til at spørge om adgang til dine mapper.
3. **Vælg, hvor dine data skal ligge**, under *Where your data goes*. Standarden er `Market Radar` i din brugermappe. Mappen skal være ny eller tom.
4. **Markedsdata:** sæt flueben i *Copy the downloaded market data too*, hvis du vil undgå at hente det hele igen. Uden flueben henter næste opdatering det.
5. **Klik *Copy my data*.** Appen kopierer og tjekker kopien: databasen skal bestå SQLites integritetstjek og have præcis de samme rækker i hver tabel, og hver anden fil sammenlignes med originalen via en SHA-256-checksum. Fejler noget, bliver intet taget i brug.

Den gamle mappe bliver ikke ændret. Den får kun en ny fil, `MOVED.txt`, der siger, hvor dine data er flyttet hen. Når den nye version viser dine porteføljer, noter og research, kan du slette den gamle mappe.

Har du ikke brugt Market Radar før, klikker du *Start with an empty folder*.

> **Bemærk:** SKATs positivliste (`imports/positivliste.xlsx`) hører til programmet og ligger stadig i programmappen. Den bliver ikke kopieret. Har du selv lagt en nyere liste i den gamle version, så læg den også i den nye programmappe; se [Installation og første start](brugervejledning/installation#skats-positivliste).

### Fra kommandolinjen

`uv run radar setup` gør det samme i terminalen. Uden tilvalg viser den de gamle mapper, den har fundet, og spørger, hvilken der skal kopieres fra.

| Tilvalg | Hvad det gør |
|---|---|
| `--from MAPPE` | Kopiér fra denne gamle Market Radar-mappe |
| `--to MAPPE` | Læg datamappen her (standard: `~/Market Radar`) |
| `--fresh` | Start med en tom datamappe |
| `--use MAPPE` | Brug en datamappe, der allerede findes (flyttet, eller fra en anden computer) |
| `--no-market-data` | Kopiér ikke de hentede markedsdata; de hentes igen |
| `--yes` | Spørg ikke |

### Hvis datamappen ikke kan findes

Kan appen ikke finde den datamappe, computeren husker (fx fordi den ligger på et drev, der ikke er tilsluttet, eller fordi du har flyttet eller omdøbt den), starter den aldrig bare med en tom mappe. Den viser i stedet *Your data folder can't be found*:

- Ligger mappen på et drev, der ikke er tilsluttet, så tilslut det og genindlæs siden.
- Har du flyttet den, så skriv, hvor den ligger nu, og klik *Use this folder*. Eller kør `uv run radar setup --use "NY STI"`.

Kommandoerne nægter at køre, så længe mappen mangler, og siger det samme.

## Læg ikke datamappen i OneDrive, iCloud eller Dropbox

Datamappen indeholder en database, som appen skriver i, mens den kører. Synkroniserer en skytjeneste filen midt i en skrivning, kan databasen gå i stykker, og to computere, der skriver i den samme fil, kan overskrive hinanden. Appen viser derfor en advarsel, hvis datamappen ligger i en mappe fra OneDrive, iCloud Drive, Dropbox, Google Drive eller Box, eller på et netværksdrev.

Læg i stedet datamappen på din egen disk, og send backupperne til skyen. En backup er en færdig zip-fil, som er sikker at synkronisere. Se [En anden kopi, uden for denne disk](#en-anden-kopi-uden-for-denne-disk).

## Backup

Backupperne findes på siden [Data & coverage](/data) under *Your data*, i kortet *Backups*.

### Hvad en backup indeholder

En backup er én zip-fil i `backups/` i datamappen. Den indeholder `radar.db`, dine mapper (`notes/`, `briefs/`, `research/`, `journal/`, `exports/` og filerne i `imports/`) og historikken. Markedsdata kommer aldrig med; de kan hentes igen.

Hver zip har en fil, `backup.json`, med tidspunkt og årsag, versionen af Market Radar, databasens format, antal rækker pr. tabel og en SHA-256-checksum for hver fil. Inden en gendannelse tjekkes hver fil mod den, så en beskadiget backup aldrig bliver lagt tilbage.

### Hvornår der tages backup

- **Én gang om dagen:** når appen starter, og når du kører `radar run`, hvis der ikke allerede er taget en den dag.
- **Før en ny version tager dine data i brug:** første gang en ny version starter med datamappen, tages en backup, før noget ændres.
- **Når du beder om det:** knappen *Back up now*, eller `uv run radar backup`.

Gamle backupper ryddes op efter faste regler, der står i koden:

| Slags | Hvor mange gemmes |
|---|---|
| Daglige | Den nyeste fra hver af de seneste 7 dage, 5 uger og 12 måneder |
| Før en ny version | Alle fra de seneste 90 dage |
| Manuelle | De nyeste 20 |
| Før en gendannelse | De nyeste 20 |

Ud over zip-filerne ligger der i `backups/` stadig de hurtige kopier af databasen (`radar-….db`), som radaren tager før hver import, fortrydelse og sletning af en portefølje.

### En anden kopi, uden for denne disk

En backup på samme disk som dine data hjælper ikke, hvis disken går i stykker eller computeren bliver stjålet. Under *A second copy, off this disk* kan du derfor vælge en anden mappe, fx en mappe i OneDrive, iCloud Drive eller Dropbox eller på en USB-disk. Skriv stien, og klik *Use this folder*. Hver ny backup bliver så også kopieret dertil.

- Er der ikke valgt en anden mappe, viser kortet en advarsel om, at backupperne kun ligger på denne computer.
- Er den nyeste kopi i den anden mappe mere end 14 dage gammel (fx fordi USB-disken ikke har været tilsluttet), vises alderen med orange. Grænsen på 14 dage står i koden.
- *Change* vælger en anden mappe, og *Stop* holder op med at kopiere. Det, der allerede ligger der, bliver liggende; radaren rydder aldrig op i den anden mappe.
- Er den anden mappe ikke tilgængelig, bliver backuppen stadig taget i datamappen, og fejlen skrives i driftsloggen.

Den anden mappe skal ligge uden for datamappen. Fra kommandolinjen: `uv run radar backup --mirror "STI"`, og `--mirror off` for at stoppe.

### Gendan en backup

1. Find backuppen i listen under *Backups* (klik *All …* for at se dem alle). Hver linje viser tidspunkt, slags (*daily*, *upgrade*, *manual* eller *restore*) og størrelse.
2. Klik *Restore…*, og bekræft.
3. Appen tjekker backuppen fil for fil, **tager en backup af det, der er der nu**, og bytter derefter databasen, dine mapper og historikken ud med backuppens. Markedsdata røres ikke.

Fra kommandolinjen viser `uv run radar backups` backupperne (også dem i den anden mappe), og `uv run radar restore FIL` gendanner én; `--yes` springer spørgsmålet over.

### Fortryd en gendannelse

Fordi appen altid tager en backup lige før en gendannelse, kan en gendannelse fortrydes: gendan den backup af slagsen *restore*, der blev taget i samme øjeblik. Beskeden efter gendannelsen siger, hvad den hedder.

> **Bemærk:** En backup fra en nyere version af Market Radar kan ikke gendannes med en ældre version. Gendan den med den version, der lavede den, eller en nyere.

## Eksport til åbne formater

En backup er en nøjagtig kopi til Market Radar selv. En **eksport** er dine data i formater, alle kan læse: til et regneark, en revisor, en anden computer, eller hvis du holder op med at bruge Market Radar.

Klik *Export my data (CSV, JSON, Markdown)* i kortet *Backups*; browseren henter en zip-fil. Fra kommandolinjen skriver `uv run radar export` filen i `exports/` i datamappen (`--out FIL` vælger et andet sted). Zip-filen indeholder:

| Fil | Indhold |
|---|---|
| `transactions.csv` | Alle handler og kontantrækker i alle porteføljer (rigtige og virtuelle, også arkiverede). UTF-8 med BOM, så Excel viser æ, ø og å rigtigt |
| `portfolios.json` | Porteføljerne: navn, rigtig eller virtuel, kontotype, udbytte, tags og note |
| `views.json` | Dine markedssyn med eksponeringer og indikatorer |
| `watchlist.csv` | Dine ændringer til watchlisten |
| `regime_votes.json` | Hvilke indikatorgrupper der stemmer i regimet |
| `notes/`, `briefs/`, `research/`, `journal/` | Dine dokumenter som Markdown |
| `EXPORT.md` | Hvad hver fil og kolonne indeholder |

Markedsdata kommer ikke med i en eksport; de tilhører kilderne. Eksporten indeholder dine beholdninger, så hold den for dig selv.

### Indlæs en eksport

På en anden computer eller efter en geninstallation indlæser du en eksport med:

```
uv run radar import-export market-radar-export-ÅÅÅÅ-MM-DD.zip
```

Kommandoen viser først, hvad filen indeholder, og spørger. Derefter:

- Hver portefølje, eksporten nævner, får præcis eksportens rækker. Porteføljer, den ikke nævner, røres ikke.
- Markedssyn, watchlist og regimevalg læses ind.
- Dokumenter, der ikke findes i forvejen, bliver lagt ind. Et dokument, der allerede findes, bliver ikke overskrevet.
- Radaren tager en kopi af `radar.db` først.

`bundle-holdings` og `unbundle-holdings` findes stadig. De pakker den samme porteføljedel som én tekstfil (base64) uden dokumenterne; se [Kommandolinjen](brugervejledning/kommandolinjen#flyt-dine-data-til-en-anden-computer).

## Opdatering til en ny version

1. Hent den nye `market-radar-….zip`.
2. Pak den ud, hvor du vil, fx ved siden af den gamle.
3. Start den med startscriptet, som du plejer.

Den nye version finder selv din datamappe, tager en backup af den og åbner. Du skal ikke kopiere nogen mapper. Når alt ser rigtigt ud, kan du slette den gamle programmappe.

> **Bemærk:** På en Mac skal du igen højreklikke på `Start Market Radar.command` → *Open* → *Open* første gang, fordi macOS behandler hver nyhentet fil som ny.

Hvad der er nyt i hver version, og om der kræves noget af dig, står i [Nyheder](brugervejledning/nyheder).

### Tilbage til den forrige version

Vil du tilbage, så pak den forrige version ud igen og start den. Den finder også datamappen. Har den nye version ændret dataformatet, åbner den gamle dine data skrivebeskyttet (se næste afsnit). Så kan du gendanne den backup, den nye version tog, før den første gang brugte dine data (slagsen *upgrade*). Det, du har lavet i den nye version siden, går så tabt; tag en eksport først, hvis du vil gemme det.

## Skrivebeskyttet: data fra en nyere version

Har en nyere version af Market Radar skrevet i dine data i et format, den ældre version ikke kender, åbner den ældre version dem skrivebeskyttet. Appen viser et rødt banner, *Read-only:*, med hvilken version der sidst brugte dataene. Du kan se siderne, men intet kan gemmes, og kommandoerne nægter at køre. Det sikrer, at en gammel zip, du starter ved en fejl, ikke kan ødelægge data, den ikke forstår.

Løsningen er at starte den nyeste version, du har.

## Flyt datamappen

Datamappen er en almindelig mappe og kan flyttes.

**Til et andet sted på samme computer:**

1. Luk appen (luk det sorte vindue).
2. Flyt eller kopiér hele datamappen derhen, hvor den skal ligge.
3. Start appen. Den kan ikke finde mappen det gamle sted og viser *Your data folder can't be found*. Skriv den nye sti, og klik *Use this folder*. Eller kør `uv run radar setup --use "NY STI"` før du starter.

**Til en anden computer:**

1. Luk appen, og kopiér hele datamappen til den nye computer (fx via en USB-disk). Cache-mappen behøver du ikke tage med.
2. Pak Market Radar ud på den nye computer.
3. Kør i en terminal i programmappen: `uv run radar setup --use "STI TIL DATAMAPPEN"`.
4. Start appen, og klik *Update data* for at hente markedsdata.

> **Tip:** Du kan også bruge en eksport: lav en eksport på den gamle computer, start med en tom mappe på den nye, og indlæs eksporten med `radar import-export`. Historikken kommer så ikke med; det gør den, når du kopierer hele datamappen.

## Tjek for nye versioner

Kortet *New versions* på siden [Data & coverage](/data) forklarer, hvordan du opdaterer. Er programmet sat op med et sted at tjekke (indstillingen `updates.repo` i `config/settings.yaml`, se [Indstillinger](brugervejledning/indstillinger)), kan du sætte flueben i *Check for a new version once a day (asks GitHub; nothing about you is sent)*.

- Tjekket er slået fra, til du selv slår det til.
- Når det er slået til, spørger appen højst én gang om dagen GitHub (`api.github.com`), hvad den nyeste udgivelse er. Der sendes intet om dig eller dine data.
- Er der en nyere version, viser appen et banner øverst med et link til udgivelsen og til dette kapitel.
- Opdateringen sker aldrig af sig selv. Du henter og pakker selv den nye zip ud.

Fra kommandolinjen: `uv run radar updates` viser status, `--on` og `--off` slår tjekket til og fra.

Versionen, du kører, står på opsætningsskærmen, under *Your data* på siden *Data & coverage* og i `uv run radar --version`.
