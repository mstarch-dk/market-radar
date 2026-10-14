# Portefølje: handler, kontanter og import

Siden [Portfolio](/portfolio) er stedet, hvor du fører dine handler. Handlerne er sandheden: positioner, gennemsnitlig anskaffelseskurs og afkast regnes altid ud fra dem, pr. portefølje. Alt gemmes i `userdata/radar.db` på din egen computer, og intet sendes nogen steder hen.

## Siden i overblik

Øverst står tre knapper og porteføljevælgeren:

- *Add a trade or cash row* åbner formularen til en ny række.
- *Import…* åbner guiden til import fra en bank eller et regneark.
- *Download your trades (CSV)* henter de viste rækker som en CSV-fil. Vælger du andre porteføljer, hedder knappen *Download these trades (CSV)*.
- *Portfolio* vælger, hvilke porteføljer siden viser (`?pf=` i adressen). Standarden er dine rigtige porteføljer. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

Derunder kommer:

- **Positions**: dine positioner med antal, gennemsnitlig anskaffelseskurs (*Average cost*), seneste kurs, værdi, urealiseret afkast og dato for første køb. *Total* lægger porteføljerne sammen, *By portfolio* viser dem hver for sig. Har en portefølje kontantrækker, står kontantbeholdningen i DKK under tabellen. Værdierne er i hvert papirs egen valuta.
- **Trades**: alle rækker, nyeste først, med *Edit* og *Delete*. Sletter du en række, kan du fortryde med *Undo* lige bagefter.
- **Past imports**: tidligere importer med mulighed for at fortryde (se [Fortryd en import](#fortryd-en-import)).
- **Portfolios**: dine porteføljer, tags og arkiv.

Ligger der handler i porteføljen *Main* (handler fra før porteføljerne fandtes), og har du andre rigtige porteføljer, viser siden en linje, hvor du kan flytte dem: alle eller ét symbol ad gangen.

## Handler og kontantrækker

En række er enten en handel eller en kontantrække:

| Type | I appen | Felter |
|---|---|---|
| BUY | *Buy* | Ticker, dato, antal, kurs pr. aktie, kurtage, evt. valutakurs |
| SELL | *Sell* | Som køb |
| DEPOSIT | *Deposit* | Beløb i DKK (indbetaling) |
| WITHDRAW | *Withdrawal* | Beløb i DKK (udbetaling) |
| DIVIDEND | *Dividend* | Ticker og beløb i DKK |
| FEE | *Fee* | Beløb i DKK (fx depotgebyr) |
| INTEREST | *Interest* | Beløb i DKK (renter) |

Når du vælger ticker og dato til en handel, udfylder formularen kursen med den dags lukkekurs (*close …*) i papirets egen valuta. Kurtage angives i samme valuta. For papirer i fremmed valuta kan du skrive den kurs, du handlede til, i feltet *DKK per …* (for London-papirer i pence: *DKK per penny*); er feltet tomt, bruges Yahoos kurs den dag.

Kontantrækker indtastes altid i DKK. Et gebyr på en handel skrives i feltet *Fee*; et gebyr uden handel er en række for sig af typen *Fee*.

> **Bemærk:** Udbytte tæller kun, når porteføljens udbyttepolitik er *cash*. Med standarden *reinvested* indeholder de justerede kurser allerede udbyttet, så en udbytterække gemmes til orientering uden at blive talt med. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

Kontantrækker er frivillige. Uden dem regner radaren hvert køb som nye penge og hvert salg som penge taget ud. Med ind- og udbetalinger fører radaren en kontantbeholdning, og afkastet regnes på beholdning plus kontanter. Se [Afkast over tid](brugervejledning/afkast).

## Kontrollen af en række

Formularen tjekker rækken, mens du skriver. Under felterne ser du, hvad handlen gør ved positionen (antal og gennemsnitskurs før og efter). Fund kommer i to slags:

- **Fejl** (✗) blokerer gemning.
- **Advarsler** (⚠) skal bekræftes med fluebenet *I checked this; save anyway*.

| Kontrol | Niveau |
|---|---|
| Ukendt ticker (ingen kursdata hos Yahoo) | Fejl |
| Dato i fremtiden | Fejl |
| Antal, kurs eller beløb ikke over 0; negativ kurtage | Fejl |
| Salg af flere aktier, end porteføljen havde på datoen | Fejl |
| Kontantrække i anden valuta end DKK, eller med kurtage | Fejl |
| Kursen er omkring 100 gange dagens lukkekurs eller 1/100 af den | Advarsel |
| Kursen er mere end 25 % fra dagens lukkekurs | Advarsel |
| Den samme række findes allerede i porteføljen | Advarsel |
| Udbytte på et papir, porteføljen ikke ejede på datoen | Advarsel |
| Kontanterne ville gå i minus | Fejl i en virtuel portefølje, advarsel i en rigtig med kontantrækker |

### Kurstjekket

Kursen sammenlignes med papirets faktiske lukkekurs den dag (eller dagen før, hvis det var en helligdag). En pris på omkring 100 gange lukkekursen er den klassiske forveksling af pence og pund (GBp og GBP) på London-børsen, eller øre og kroner. Grænserne ligger i koden. Kurser er altid pr. aktie i papirets noteringsvaluta, som hos Yahoo.

En rigtig portefølje uden kontantrækker tjekkes ikke for negative kontanter. En virtuel portefølje kan kun bruge, hvad der er indbetalt.

## Gennemsnitsmetoden

Positionerne opgøres efter gennemsnitsmetoden, som SKAT bruger for aktier:

- Kurtage er en del af anskaffelsessummen.
- Et køb lægger antal og anskaffelsessum til; gennemsnitskursen er summen divideret med antallet.
- Et salg fjerner en forholdsmæssig andel af anskaffelsessummen, så gennemsnitskursen er uændret.

Hver portefølje har sine egne positioner. Visningen *Total* lægger dem sammen, hvilket er rigtigt til sammenligningen med ACWI, men ikke til skat, hvor en aktiesparekonto opgøres for sig. Se [Dansk skat for investorer](laerebog/skat).

## Import fra bank eller regneark

*Import…* åbner en guide i fire trin: vælg en fil, tjek kolonnerne, bekræft symbolerne, gennemse og importér. Intet gemmes før sidste trin.

### 1. Vælg en fil

Vælg en CSV- eller Excel-fil, eller fold *…or paste rows from a spreadsheet* ud og indsæt rækker direkte. Under *Format* vælger du formatet eller lader radaren genkende det, og under *Into portfolio* vælger du porteføljen (standard: din standardportefølje).

Listen *Format* rummer en eksport fra Yahoo Finance, som er afprøvet, og færdige formater for nogle danske banker og mæglere, fx Danske Bank, Nordea, Saxo Bank eller Nordnet. Hvilke der findes, ser du i listen. Bankernes formater er ikke afprøvet. Står din bank ikke på listen, kan du stadig importere filen med den generelle genkendelse af kolonner (se næste trin).

De ikke-afprøvede formater bygger på offentlige beskrivelser og bliver først markeret som afprøvet, når en rigtig eksport er brugt som test. Siden skriver *unverified format: check the rows below*: gennemse rækkerne med ekstra omhu.

### 2. Tjek kolonnerne

Kender radaren ikke formatet, vælger du selv, hvilken kolonne der er dato, køb/salg, symbol, ISIN, navn, antal, kurs, kurtage, valuta, konto, handels-id og kontantbeløb. Den generelle genkendelse forstår almindelige kolonnenavne. Kortlægger du kontokolonnen (*Account (→ portfolio)*), havner hver række i porteføljen med det navn; mangler en portefølje, oprettes den som rigtig ved importen. Vil du hellere samle alt i den valgte portefølje, så lad kontokolonnen være tom.

### 3. Bekræft symbolerne

Hvert værdipapir i filen skal have et Yahoo-symbol. Radaren prøver i rækkefølge: et symbol du tidligere har valgt for samme papir, radarens egen ISIN-liste, symbolet selv og til sidst Yahoos søgning. Fund fra søgningen er markeret *please check* og skal bekræftes med fluebenet, før du kan importere. Du kan vælge et andet forslag eller skrive et symbol selv med *other…*. Dine valg huskes til næste import.

### 4. Gennemse og importér

Hver række vises med sin status: *new*, *already stored* (springes over), *skipped* (fx en ukendt transaktionstype), en advarsel eller en fejl. Er der fejl, kan du ikke importere. Advarsler skal bekræftes. Knappen *Import N trades* gemmer rækkerne som én samlet import. Serveren gennemfører hele kontrollen igen, før den gemmer.

En Yahoo-eksport er et øjebliksbillede af hele porteføljen og erstatter derfor din forrige Yahoo-import i samme portefølje. Andre importer lægger rækker til og springer dem over, der allerede findes.

### Fortryd en import

Under *Past imports* står hver import med tidspunkt, kilde, fil og antal rækker. *Undo* fjerner alle rækker, importen tilføjede. Radaren tager en sikkerhedskopi af databasen i `userdata/backups/` før hver import og hver fortrydelse.

## Den hurtige Yahoo-import

På siden [Holdings & watchlist](/me) og på velkomstsiden ligger en kortere vej: *Choose the exported CSV file* indlæser en Yahoo Finance-eksport direkte, med beholdninger, solgte positioner og watchlist-navne. Den erstatter den forrige Yahoo-import, og dine watchlist-ændringer i appen bevares. Kurser for nye navne hentes ved næste opdatering. Se [Mine beholdninger og watchlist](brugervejledning/beholdninger).

## Kommandolinjen

- `uv run radar portfolio list [--symbol X] [--portfolio P] [--tag T]` viser de gemte rækker.
- `uv run radar portfolio add BUY NOVO-B.CO 10 612.40 --date 2026-01-05 --portfolio ASK` tilføjer en handel med samme kontrol som i appen; advarsler kræver `--yes`, fejl blokerer altid. Kun køb og salg kan tilføjes her.
- `uv run radar portfolio export --out backup.csv [--all]` gemmer rækkerne som CSV.
- `uv run radar import-yahoo <fil.csv>` importerer en Yahoo-eksport.

Se [Kommandolinjen](brugervejledning/kommandolinjen).
