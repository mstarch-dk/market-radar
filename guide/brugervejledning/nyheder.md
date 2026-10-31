# Nyheder

Hvad der er nyt i hver version af Market Radar, med den nyeste først, og om der kræves noget af dig, når du opdaterer. Hvordan du opdaterer, står i [Dine data, backup og opdatering](brugervejledning/dine-data#opdatering-til-en-ny-version).

## Unreleased

**Scout: hypoteser fra det, markedet taler om.** Den nye Claude-skill `/scout` søger på nettet efter de historier, investorer og medier er begyndt at fortælle, fx kernekraft eller sundhed i afrikanske lande. Den holder dem op mod radarens tal og giver dig 3–5 hypoteser. Hver har et stadie: *hvisken* (omtalen vokser, men kursen har ikke fulgt med), *bekræftes* eller *konsensus* (et advarselsflag). Se [Scout: hypoteser fra markedets snak](brugervejledning/scout).

- **Du vælger:** adoptér en kandidat som markedssyn (Claude viser det først og gemmer kun efter dit ja), følg den, eller afvis den. Beslutningerne kan skrives i journalen, og `/journal review` gennemgår dem.
- **Alle kandidater måles,** også de afviste: de fryses med en proxy-kurv og står mod ACWI på [Evidens-siden](brugervejledning/scoretest#resultaterne-fremad) under *Scout candidates* og i `uv run radar scout review`.
- **Andre steder:** et syn fra scouten har mærket *from scout* på *My market views*, scout-rapporterne ligger under *Research* på *Notebook*, og månedsbriefen har en linje om dem.
- **Lærebogen** har et nyt kapitel: [Rygter, opmærksomhed og fortællinger](laerebog/rygter-og-opmaerksomhed).
- **Ved opdatering** får radar.db en ny kolonne; der tages en backup først. Du skal ikke gøre andet.

**Danske indeksfonde i porteføljens røntgen.** Yahoo viser danske investeringsforeninger som aktier uden sektor, så røntgenbilledet kunne ikke placere dem og viste dem som *unknown*. Nu kender radaren 26 børsnoterede danske indeksfonde fra Danske Invest, Sparindex, Nordea Invest, BankInvest og Sydinvest og tæller hver som det indeks, den følger. En valutasikret andelsklasse (*DKK h*) tæller som kroner. Noterne siger, hvilket indeks hver fond er talt som. Se [Porteføljens røntgen](brugervejledning/xray#sådan-placeres-fondene). Du skal ikke gøre noget, når du opdaterer.

## 0.4.0

Versionen efter 0.2.0; der er ingen 0.3.0. Du skal ikke gøre noget, når du opdaterer: den nye version finder selv dine data og tager en backup først.

**Følg en opdatering, mens den kører.** En dataopdatering viser nu, hvilket trin den er nået til (fx trin 4 af 20), hvor langt den er i trinnet, og hvert problem i det øjeblik, det opstår: en kilde der fejler (den beholder sine gemte data), tickers uden data eller uden den seneste handelsdag. Før så du kun et tal for kursdownloaden, og problemerne først i loggen til sidst. Se [Data og opdatering](brugervejledning/data-og-opdatering) og [Drift](brugervejledning/drift#kører-nu).

- **Uanset hvor den er startet.** En opdatering fra Claude (fx til månedsbriefen) eller fra `radar run` i en terminal vises nu i appen: på siden *Operations* under *Running now* og i panelet *Update data*.
- **Månedsbriefen fortæller undervejs.** Kører du `/market-brief`, skriver Claude en kort linje om, hvor langt opdateringen er, og hvilke problemer der er opstået, og siger med det samme, hvad en fejlet kilde betyder for briefen.
- **I terminalen** skriver `radar run` hvert trin og hvert problem, når det sker.
- **Ved opdatering** får driftsloggen (ops.db i cache-mappen) en ny tabel. Du skal ikke gøre noget.

**Mine handelsregler.** Den nye side *Trading rules* under *Mine* er stedet, hvor du skriver de regler ned, du vil handle efter: "ingen aktie over 10 %", "ingen genkøb inden for 30 dage", "aldrig sælge mere end 15 % på en uge". Test en handling, og hver regel siger, om den brydes, er tæt på eller overholdes, med tallene og hvad der skal til for at overholde den. Reglerne er et spejl, aldrig en bom: intet blokeres. Se [Mine handelsregler](brugervejledning/handelsregler).

- **Brud lige nu** vises på siden, som et flag i beholdningstabellen og i månedsbriefen.
- **Når du registrerer en handel,** står de regler, den bryder, som advarsler, og du kan skrive, hvorfor du gør det alligevel.
- **Ville reglerne have hjulpet?** kører dagens regler på dine egne tidligere handler.
- **Claude:** den nye skill `/rules`; `/journal` tjekker en handling mod reglerne, og `/propose-portfolio` holder sig under dine lofter.
- **Ved opdatering** får radar.db to nye tabeller; der tages en backup først. Du skal ikke gøre andet.

**Claude kan bruge radaren direkte.** Åbner du programmappen i Claude Code, får Claude radarens tal som værktøjer i stedet for at køre kommandoer og læse hele filer. Første gang spørger Claude Code, om du vil bruge serveren `radar` fra projektet; svar ja. Se [Claude og radarens værktøjer](brugervejledning/claude-mcp).

- **Skills læser mindre.** `/research`, `/compare`, `/journal`, `/market-brief`, `/propose-portfolio` og `/hindsight` henter kun det, de skal bruge. Et `/research`-notat læser cirka to tredjedele mindre og månedsbriefen omkring en fjerdedel mindre, og Claude skal ikke bede om lov til at læse i datamappen.
- **Svarene siger, hvor gamle de er,** og manglende data er stadig "n/a", aldrig 0.
- **Det, der gemmer, spørger først.** En handel, Claude registrerer for dig, tjekkes som i appen og gemmes først, når du siger ja. Et dokument, der findes, erstattes kun efter at være læst.
- **Opdatering og studier fra Claude** vises på siden *Operations*, og kører der allerede et job i appen eller en terminal, starter Claude ikke et til.
- **Uden værktøjerne virker alt som før**: skills bruger så kommandolinjen. Du skal ikke gøre noget, når du opdaterer.

**Positioner i kroner.** Tabellen *Positions* på *Portfolio* har fået kolonnen *Value (DKK)*: værdien omregnet til kroner med valutakursen fra dagen for den seneste kurs, så du kan sortere dine positioner efter størrelse på tværs af valutaer. Se [Portefølje](brugervejledning/portefolje).

**Shareholder yield for selskaber med helårlige pengestrømme.** Har Yahoo kun et selskabs pengestrømsopgørelse for hele år (mange europæiske og japanske selskaber, fx Santander og BBVA), manglede shareholder yield og FCF-tallene, så snart regnskabsåret var over {{settings:fundamentals.ttm_max_age_days}} dage gammelt. Nu bruges det seneste regnskabsår, med en note i kortet *Quality & value*. Se [Radarens kvalitets- og værdiscore](laerebog/kvalitetsscore).

**En kalender over det, du ejer og følger.** Den nye side *Calendar* under *Mine* viser de næste {{settings:calendar.days}} dages regnskaber og udbyttedage for dine beholdninger og din watchlist, og dine egne datoer: gennemgangsdatoer i journalen og tidsstop i dine porteføljeforslag. Hvert punkt siger, hvorfor det er fremhævet, efter faste regler: hvor meget af porteføljen der står på spil, hvor tæt kursen er på dit gennemgangsniveau, svagt momentum, nedjusterede skøn, og hvor sikker datoen er. Se [Kalenderen](brugervejledning/kalender).

- **Datoerne er Yahoos, og det står der.** Et vindue vises som et vindue, aldrig som dets første dag. En aktie uden kendt dato står under *No date known* med grunden; fonde tælles, men listes ikke.
- **Et nyt trin i opdateringen** læser Yahoos kalender for dine aktier hver {{settings:calendar.refresh.max_age_days}}. dag, og dagligt når et regnskab nærmer sig. Læsningerne gemmes i historikken i datamappen, så kalenderen kan se, når en dato flytter sig. Første opdatering efter skiftet læser alle dine aktier og tager lidt længere tid.
- **Samme kalender andre steder**: båndet *Soon* på forsiden, flaget *earnings in N d* på *Holdings & watchlist*, `radar calendar` på kommandolinjen og afsnittet *Kommende uger* i månedsbriefen.
- **Nye indstillinger** under `calendar:`; se [Indstillinger](brugervejledning/indstillinger#calendar-regnskabsdatoer). Du skal ikke gøre noget, når du opdaterer.

**Et skøn over skatten.** Siden *Portfolio* har fået fanen *Tax*, der regner den danske skat af dine egne handler for et indkomstår: aktiesparekonto og pension hver for sig, og dine konti med frie midler samlet, fordi gennemsnitsmetoden og aktieindkomsten opgøres pr. person. Du ser realiserede gevinster og tab i kroner, udbytte, lagergevinst på fonde, aktieindkomsten mod progressionsgrænsen, kapitalindkomst og det, der fremføres. Det er et estimat, ikke skatterådgivning; din årsopgørelse gælder. Se [Skat: radarens skatteestimat](brugervejledning/skat).

- **Satserne har kilde og dato.** De står i `config/tax_dk.yaml` for 2025 og 2026. Et år uden tjekkede satser viser beløbene, men ingen skat.
- **Intet gættes.** En fond uden ISIN-kode, et år uden positivliste eller en dansk fond uden for listen står under *Not in the estimate* med værdi og årsag, og du kan rette den direkte der.
- **Positivlisten pr. år.** Hver fond slås op på listen for netop det indkomstår, så en ETF, der forlader listen, skifter beskatning det år.
- **Din årsopgørelse er udgangspunktet.** Skriv det, din seneste årsopgørelse fører ind i året, under *Losses carried in* (0, hvis intet fremføres). Så får du et estimat, også når dine handler går længere tilbage end satserne.
- **Ukendt udbytte står som ukendt.** Viser kurserne et udbytte på en aktie, du ejede, uden at det er bogført, står udbyttet som –, ikke 0, og noten siger hvilket.
- **Indskudsloftet på aktiesparekontoen** måles nu som hos SKAT: mod kontoens værdi den 31. december året før. Har du sat `propose.ask_deposit_cap` eller `propose.ask_cap_year` i din egen `settings.yaml`, så slet dem; loftet står nu i `tax_dk.yaml`.
- **Din database opdateres** med personer, ISIN-koder og fremførte tab; der tages en backup først. Alle dine konti tilhører personen *Me*, indtil du ændrer det.

**Rettelser.** Siden *X-ray* fejlede med *Internal Server Error*, når en portefølje havde både en fond og aktier; det gør den ikke længere. Xtrackers MSCI World (XDWD.DE) regnes nu som en bred verdensfond som de andre på listen `risk.world_funds`: røntgenbilledet spreder den med ACWI's vægte, og loftet pr. aktie i dine handelsregler tæller den ikke med. Peger du en ny version på en datamappe, du allerede har (opsætningsskærmen eller `radar setup --use`), tages der nu en backup, før den nye version ændrer noget, som når du bare starter den.

## 0.2.0

**Dine data har fået deres egen mappe.** Porteføljer, handler, markedssyn, watchlist, noter, briefs, research, journal og den historik, radaren har samlet op, ligger nu i en datamappe uden for programmappen, som standard `Market Radar` i din brugermappe. Markedsdata ligger i en cache-mappe for sig og kan altid hentes igen. Fremover pakker du bare en ny version ud og starter den; den finder selv dine data, og du skal ikke kopiere mapper.

- **Opsætningsskærm ved første start.** Appen finder dine data fra den gamle version (i programmappen eller i en mappe ved siden af den), kopierer dem til datamappen og tjekker kopien fil for fil. Den gamle mappe ændres ikke; den får kun en `MOVED.txt`, der siger, hvor dataene er flyttet hen. Fra kommandolinjen: `uv run radar setup`.
- **Automatisk backup.** Én gang om dagen og før en ny version første gang bruger dine data tages en backup af database, dokumenter og historik. Du kan vælge en anden mappe, fx i OneDrive eller på en USB-disk, som hver backup også kopieres til, og gendanne en backup med ét klik. En gendannelse kan fortrydes.
- **Eksport til åbne formater.** *Export my data (CSV, JSON, Markdown)* giver dig alle dine handler, porteføljer, markedssyn, watchlist og dokumenter i en zip-fil, som kan læses uden Market Radar og indlæses igen med `radar import-export`.
- **Tjek for nye versioner.** Kan slås til på siden *Data & coverage*. Appen spørger så GitHub højst én gang om dagen og viser et banner, når der er en ny version. Der sendes intet om dig.
- **Beskyttelse mod ældre versioner.** Starter du en ældre version på data, som en nyere version har skrevet, åbner den dem skrivebeskyttet, så de ikke kan blive ødelagt.
- **Dine konti og dine eksperimenter hver for sig.** Siden *Portfolio* viser kun dine konti, med et kort pr. konto øverst og fanerne *Positions*, *Transactions*, *Imports* og *Accounts*, så du ikke skal rulle forbi det hele. Formularen til en ny handel åbner lige over handelstabellen. Virtuelle porteføljer (A/B-testen, simuleringer, forks) har fået deres egen side, *Experiments*, hvor du kan åbne hver enkelt og se beholdning, handler, ombalanceringer og afkast mod ACWI. Se [Eksperimenter](brugervejledning/eksperimenter).
- **Kurtage-estimat.** Hver konto kan have et kurtageskema (procent, mindste- og maksimalkurtage pr. marked), startet fra Saxo eller Danske Bank. Formularen udfylder så kurtagen med et estimat, som du kan rette. Se [Kurtage-estimatet](brugervejledning/portefolje#kurtage-estimatet).
- **Simuleringer betaler kontoens kurtage.** `radar sim exits` regner med kontoens kurtageskema (mindstekurtage og vekselgebyr med) i stedet for en fast sats, og en fork overtager skemaet fra originalen. Se [Kurtagen i simuleringen](brugervejledning/stop-simulering#kurtagen-i-simuleringen).
- **Kvalitet og værdi ved siden af momentum.** Radaren læser nu selskabernes regnskaber: fra SEC EDGAR for amerikanske selskaber og fra Yahoo for resten. Ud fra dem regner den to nye scorer fra 0 til 100 mod sektorens selskaber i alle regioner.
  - *Kvalitetsscoren* måler forretningen: frit cash flow, ROIC, stabile marginer og omsætning, balancen og udbytterækken.
  - *Værdiscoren* måler prisen: FCF yield, EBIT/EV, shareholder yield og prisen mod selskabets egen historik.
  - *K+V* er gennemsnittet af de to.
  - Scorerne står på den nye side *Quality & value*, som kolonner på *Momentum* og *Holdings & watchlist* og i et kort på tickerprofilen.
  - Se [Kvalitet og værdi](brugervejledning/kvalitet-og-vaerdi).
- **A/B-test fremad i tid.** Tre virtuelle kurve: kvalitet + værdi, momentum og en blanding 50/50. De vælges én gang om måneden og køres mod ACWI og mod hinanden, uden at kunne justeres bagefter. Start dem på siden *Quality & value* eller med `radar abtest start`. Se [A/B-testen](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum).
- **Scorens regel testet over årtier.** `radar study longrun` tester momentumscoren på 49 amerikanske brancher siden 1926 og 23 udviklede aktiemarkeder siden 1986, bygget af forskere af alle noterede aktier, så testen ikke har survivorship bias. Den prøver varianter af vinduerne og vægtene, deler resultaterne op pr. årti, trend og recession og viser basisrater for momentum, værdi og kvalitet. Serierne kommer fra Kenneth R. French Data Library og JKP Global Factor Data og hentes en gang om måneden. Se [Testen over årtier](brugervejledning/scoretest#testen-over-årtier).
- **Porteføljeforslagene vejer den lange historik ind.** Det forventede merafkast i `/propose-portfolio` trækkes nu mod, hvad de samme egenskaber har givet i alle aktier i udviklede markeder siden 2008 (JKP's porteføljer, uden overlevelsesbias), med størst vægt på det, der er mindst støj i. Fradraget for overlevelsesbias følger målingen i `radar study longrun`, når den peger på mere end {{settings:propose.survivorship_haircut|pct}}. Ved værdi og blanding markeres aktier uden for USA som ikke testet af regeltesten. Se [Porteføljeforslag](laerebog/portefoeljeforslag#sådan-gør-radaren).
- **Længere kurshistorik.** Radaren gemmer nu {{settings:history_years}} års kurser (før 6), så `radar study score` får omkring dobbelt så mange måneder og også dækker coronakrakket i 2020. Den første opdatering efter skiftet henter alle kurser igen og tager længere tid end normalt.
- **Scorerne testet på historikken.** `radar study score --signal qv` tester K+V på hver månedsafslutning for amerikanske aktier ud fra de regnskaber, der var indleveret på dagen. Se [Kvalitet og værdi](brugervejledning/scoretest#kvalitet-og-værdi) i *Test momentumscoren på historikken*.
- **Claude-skills bruger scorerne.**
  - `/research` får et afsnit om kvalitet og værdi.
  - `/compare` har scorerne i sin rubrik.
  - `/market-brief` skriver om de bedste K+V-navne, overlappet med momentum og A/B-testen.
  - `/hindsight` kan vælge en kurv efter K+V.
- **Byg aflæsningerne igen uden at hente noget.** Har en kilde ændret sig siden sidste rapport (fx efter `radar update` i terminalen eller en ændring i `config/settings.yaml`), viser markedssiderne et banner med knappen *Rebuild the readings*. Knappen findes også på *Data & coverage*. Efter en ny version bygger appen selv rapporten igen ved start. Se [Byg aflæsningerne igen](brugervejledning/data-og-opdatering#byg-aflæsningerne-igen).
- **Forslag til en portefølje.** `/propose-portfolio ASK 50000` i Claude Code foreslår en spredt kurv af nye aktier til et beløb, med momentum, værdi eller en blanding og mindst {{settings:propose.min_ticket_dkk}} kr. pr. aktie for at holde kurtagen nede. Lofterne gælder porteføljen efter købet: sektor, region og valuta mod ACWI's egne vægte, korrelation og positionsstørrelse. Notatet viser forventet maks. drawdown, det forventede merafkast over ACWI og alternativerne (ACWI selv, reglens egen kurv, færre eller flere aktier, sektor-ETF'er) og har exitkriterier for hver aktie. Det forventede merafkast kommer kun fra en test af selve reglen på alle tidligere måneder (`radar study propose`). Konklusionen kan sagtens være "køb ACWI". Se [/propose-portfolio](brugervejledning/claude-code#propose-portfolio).
- **Én regel for momentumscoren overalt.** Siden *Momentum*, *Discover*, regimet og A/B-testen rangerede før med en lidt anden percentil end *Mine beholdninger*, tickerprofilen og testene af scoren. Nu bruger alle andelen af aktier strengt under, så det, testene har vist, er det, du ser. Rækkefølgen er den samme, men regionens stærkeste aktie får nu højst 100 · (N−1)/N og den svageste 0. På en liste med 40 aktier er scorerne omkring 2,5 point lavere end før, i S&P 500 0,2 point. En aktie, der står alene i sit marked på *Discover*, har ingen score. Se [Radarens momentumscore](laerebog/momentumscore#scoren).
- **Porteføljeforslag følger dit valg af stemmegrupper** i regimet med det samme, som forsiden og tickerprofilerne gør. Før brugte de regimet fra seneste `radar report`.
- **Indstillingerne tjekkes, når de indlæses.** En stavefejl, en nøgle der mangler eller en forkert type i `config/settings.yaml` stopper med det samme og nævner nøglen, og sundhedstjekket viser det under *Settings*. Se [Sundhedstjekket](brugervejledning/fejlfinding#sundhedstjekket-radar-doctor).
- **Bedre tickeropslag** i handelsformularen: piletaster, *tracked*-markering og papirets navn og børs under feltet.
- **Siden *Data & coverage*** har fået afsnittet *Your data* med mapperne, backupperne og versionen. Nye kommandoer: `radar paths`, `radar backup`, `radar backups`, `radar restore`, `radar export`, `radar import-export`, `radar updates` og `radar --version`.

**Det skal du gøre:** første gang du starter 0.2.0, vælger du, hvor dine data skal ligge. Har du brugt en ældre version, så pak 0.2.0 ud ved siden af den gamle mappe, start den, og klik *Copy my data*. Ligger den gamle mappe et andet sted, så skriv stien og klik *Look there*. Når den nye version viser dine porteføljer, noter og research, kan du slette den gamle mappe. Læg ikke datamappen i OneDrive, iCloud Drive eller Dropbox; vælg i stedet sådan en mappe som anden backupmappe. Har du selv lagt en nyere positivliste i `imports/` i den gamle version, så læg den også i den nye programmappe. Har du ændret noget i `config/`, så gør det igen i den nye. Bruger du Claude Code, ligger `notes/investor.md` nu i datamappen; den bliver kopieret med. Vil du have regnskaber fra SEC EDGAR for de amerikanske selskaber, så skriv en kontakt-e-mail på siden *Data & coverage* (SEC beder om det). De første dage henter den daglige opdatering regnskaberne lidt ad gangen; vil du have dem alle med det samme, så kør `uv run radar fundamentals update --all`.
