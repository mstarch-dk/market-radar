# Portefølje: handler, kontanter og import

Siden [Portfolio](/portfolio) er stedet, hvor du fører handlerne på dine konti (de rigtige porteføljer). Handlerne er sandheden: positioner, gennemsnitlig anskaffelseskurs og afkast regnes altid ud fra dem, pr. konto. Alt gemmes i `radar.db` i din datamappe på din egen computer, og intet sendes nogen steder hen. Der tages automatisk backup af det; se [Dine data, backup og opdatering](brugervejledning/dine-data).

Virtuelle porteføljer (A/B-testen, simuleringer og forks) vises ikke her, men på siden [Experiments](/experiments). Se [Eksperimenter: virtuelle porteføljer](brugervejledning/eksperimenter).

## Siden i overblik

Øverst står en række kort, ét pr. konto, med kontoens navn, skattetype og værdi i DKK. *All accounts* viser alle dine konti samlet (standard); klikker du på en konto, viser siden kun den (`?pf=` i adressen).

Derunder er siden delt i fire faner (`?tab=` i adressen, så *Tilbage* i browseren går til den forrige fane):

- ***Positions***: dine positioner med antal, gennemsnitlig anskaffelseskurs (*Average cost*), seneste kurs, værdi, urealiseret afkast og dato for første køb. *Total* lægger kontiene sammen, *By account* viser dem hver for sig. Har en konto kontantrækker, står kontantbeholdningen i DKK under tabellen. Værdierne er i hvert papirs egen valuta.
- ***Transactions***: alle rækker, nyeste først, med *Edit* og *Delete*. Knapperne *Add a trade* og *Add a cash row* åbner formularen lige over tabellen, og *Download your transactions (CSV)* henter de viste rækker. Sletter du en række, kan du fortryde med *Undo* lige bagefter.
- ***Imports***: *Import a file…* åbner guiden til import fra en bank eller et regneark, og *Past imports* viser tidligere importer med mulighed for at fortryde (se [Fortryd en import](#fortryd-en-import)).
- ***Accounts***: dine konti med skattetype, tags, kurtageskema og arkiv. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

Ligger der handler i porteføljen *Main* (handler fra før porteføljerne fandtes), og har du andre konti, viser siden over fanerne en linje, hvor du kan flytte dem: alle eller ét symbol ad gangen.

Et gammelt bogmærke til en virtuel portefølje på denne side sender dig videre til [Experiments](/experiments).

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

I feltet *Ticker* kan du skrive et firmanavn eller et symbol: listen under feltet viser forslag fra Yahoo med symbol, navn, børs og type, og et papir, radaren allerede følger, er markeret *tracked*. Vælg med piletasterne og Enter eller med musen; når du har valgt, står papirets navn og børs under feltet, så NOVO-B.CO ikke forveksles med NVO.

Når du vælger ticker og dato til en handel, udfylder formularen kursen med den dags lukkekurs (*close …*) i papirets egen valuta. Kurtage angives i samme valuta; har kontoen et kurtageskema, udfyldes den med et estimat (se [Kurtage-estimatet](#kurtage-estimatet)). For papirer i fremmed valuta kan du skrive den kurs, du handlede til, i feltet *DKK per …* (for London-papirer i pence: *DKK per penny*); er feltet tomt, bruges Yahoos kurs den dag.

Kontantrækker indtastes altid i DKK. Et gebyr på en handel skrives i feltet *Fee*; et gebyr uden handel er en række for sig af typen *Fee*.

> **Bemærk:** Udbytte tæller kun, når porteføljens udbyttepolitik er *cash*. Med standarden *reinvested* indeholder de justerede kurser allerede udbyttet, så en udbytterække gemmes til orientering uden at blive talt med. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags).

Kontantrækker er frivillige. Uden dem regner radaren hvert køb som nye penge og hvert salg som penge taget ud. Med ind- og udbetalinger fører radaren en kontantbeholdning, og afkastet regnes på beholdning plus kontanter. Se [Afkast over tid](brugervejledning/afkast).

## Kurtage-estimatet

Hver konto kan have et kurtageskema: for hvert marked en procentsats af handlens værdi med en mindstekurtage og eventuelt en maksimal kurtage. Du sætter det under fanen *Accounts* ved at klikke *fees: …* ud for kontoen.

- *Start from* udfylder skemaet fra en mægler: Saxo (Classic), Danske Bank (Netbank online) eller Danske Banks kampagne uden kurtage på aktiesparekontoen. Hver skabelon har datoen for prislisten og et link til kilden. Priserne ændrer sig, så sammenlign med din mæglers aktuelle prisliste, og ret tallene til.
- Markederne er *Denmark* (`.CO`), *Nordic* (`.ST`, `.OL`, `.HE`, `.IC`), *USA* (symboler uden endelse), *Europe* (fx `.DE`, `.PA`, `.AS`), *UK* (`.L`) og *Other markets*, som bruges for alt, skemaet ikke har en regel for. Mindste- og maksimalkurtagen står i reglens egen valuta (fx 1 USD) og omregnes med dagens valutakurs.
- *Currency exchange surcharge* er mæglerens vekselgebyr. Det vises ved siden af estimatet, men lægges ikke til: skriver du den kurs, du handlede til, er vekselgebyret allerede med i den.

I formularen udfyldes *Fee* med estimatet, og under feltet står grundlaget, fx *estimated 4,20: 0.2% (min 29 DKK)*. Skriver du selv et beløb, beholdes det, og estimatet står som *schedule says …* med knappen *use it*. Uden et skema, eller uden en valutakurs til at omregne en mindstekurtage, udfyldes intet: et manglende estimat er aldrig 0.

> **Bemærk:** Estimatet er et skøn. Det er beløbet på din afregning, der tæller; skatter som fransk FTT og britisk stempelafgift er ikke med.

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

*Import a file…* under fanen *Imports* åbner en guide i fire trin: vælg en fil, tjek kolonnerne, bekræft symbolerne, gennemse og importér. Intet gemmes før sidste trin.

### 1. Vælg en fil

Vælg en CSV- eller Excel-fil, eller fold *…or paste rows from a spreadsheet* ud og indsæt rækker direkte. Under *Format* vælger du formatet eller lader radaren genkende det, og under *Into portfolio* vælger du porteføljen (standard: din standardportefølje).

Listen *Format* rummer en eksport fra Yahoo Finance, som er afprøvet, og færdige formater for nogle danske banker og mæglere, fx Danske Bank, Nordea, Saxo Bank eller Nordnet. Hvilke der findes, ser du i listen. Bankernes formater er ikke afprøvet. Står din bank ikke på listen, kan du stadig importere filen med den generelle genkendelse af kolonner (se næste trin).

De ikke-afprøvede formater bygger på offentlige beskrivelser og bliver først markeret som afprøvet, når en rigtig eksport er brugt som test. Siden skriver *unverified format: check the rows below*: gennemse rækkerne med ekstra omhu.

### 2. Tjek kolonnerne

Kender radaren ikke formatet, vælger du selv, hvilken kolonne der er dato, køb/salg, symbol, ISIN, navn, antal, kurs, kurtage, valuta, konto, handels-id og kontantbeløb. Den generelle genkendelse forstår almindelige kolonnenavne.

Decimaltegnet læses for hver kolonne ud fra hele filen: står der et sted `12,50`, bruger kolonnen komma som decimaltegn, og `1.234` i samme kolonne er da tusind to hundrede fireogtredive. En kolonne uden spor følger filens andre talkolonner. Kan filen ikke afgøre det (fx en kolonne, hvor kun `1.234` står), får rækken en advarsel i stedet for et gæt. Tal i et regneark (`.xlsx`) bruges, som de står i arket, uanset formatets decimaltegn. En tom kurtagecelle eller en tankestreg er ingen kurtage. Står der noget, der ikke kan læses som et tal (fx `n/a`), springes rækken over med årsagen *unreadable fee*, i stedet for at kurtagen bliver 0.

Har filen en valutakolonne, sammenlignes den med den valuta, papiret handles i på Yahoo. Er de forskellige (fx DKK for en aktie, der handles i USD), får rækken en advarsel: kurs og kurtage gemmes i papirets egen valuta og skal omregnes, eller du skal vælge den notering, der handles i filens valuta. Kortlægger du kontokolonnen (*Account (→ portfolio)*), havner hver række i porteføljen med det navn; mangler en portefølje, oprettes den som rigtig ved importen. Vil du hellere samle alt i den valgte portefølje, så lad kontokolonnen være tom.

### 3. Bekræft symbolerne

Hvert værdipapir i filen skal have et Yahoo-symbol. Radaren prøver i rækkefølge: et symbol du tidligere har valgt for samme papir, radarens egen ISIN-liste, symbolet selv og til sidst Yahoos søgning. Fund fra søgningen er markeret *please check* og skal bekræftes med fluebenet, før du kan importere. Du kan vælge et andet forslag eller skrive et symbol selv med *other…*. Dine valg huskes til næste import.

### 4. Gennemse og importér

Hver række vises med sin status: *new*, *already stored* (springes over), *skipped* (fx en ukendt transaktionstype), en advarsel eller en fejl. Er der fejl, kan du ikke importere. Advarsler skal bekræftes. Knappen *Import N trades* gemmer rækkerne som én samlet import. Serveren gennemfører hele kontrollen igen, før den gemmer.

En Yahoo-eksport er et øjebliksbillede af hele porteføljen og erstatter derfor din forrige Yahoo-import i samme portefølje. Andre importer lægger rækker til og springer dem over, der allerede findes.

### Fortryd en import

Under *Past imports* står hver import med tidspunkt, kilde, fil og antal rækker. *Undo* fjerner alle rækker, importen tilføjede. Radaren tager en sikkerhedskopi af databasen i `backups/` i datamappen før hver import og hver fortrydelse.

En Yahoo-import, der erstattede en tidligere, kan ikke fortrydes med *Undo*: det ville fjerne de nye rækker uden at bringe de gamle tilbage. Der står i stedet *replaced N*, og holder du musen over, ser du navnet på kopien af databasen, der blev taget lige før importen. Gendan den kopi, eller importér den tidligere fil igen.

## Den hurtige Yahoo-import

På siden [Holdings & watchlist](/me) og på velkomstsiden ligger en kortere vej: *Choose the exported CSV file* indlæser en Yahoo Finance-eksport direkte, med beholdninger, solgte positioner og watchlist-navne. Den erstatter den forrige Yahoo-import, og dine watchlist-ændringer i appen bevares. Kurser for nye navne hentes ved næste opdatering.

Fordi den erstatter, afvises en fil med et køb eller salg uden købskurs eller handelsdato, eller med en handel dateret i fremtiden, og intet ændres. Ellers ville den handel forsvinde. Ret den i Yahoo og eksportér igen, eller brug importen på *Portfolio*-siden, hvor du kan udfylde den. En kurs omkring 100 gange dagens lukkekurs (pence og pund) eller langt fra den nævnes ved symbolet. Se [Mine beholdninger og watchlist](brugervejledning/beholdninger).

## Kommandolinjen

- `uv run radar portfolio list [--symbol X] [--portfolio P] [--tag T]` viser de gemte rækker.
- `uv run radar portfolio add BUY NOVO-B.CO 10 612.40 --date 2026-01-05 --portfolio ASK` tilføjer en handel med samme kontrol som i appen; advarsler kræver `--yes`, fejl blokerer altid. Kun køb og salg kan tilføjes her.
- `uv run radar portfolio export --out backup.csv [--all]` gemmer rækkerne som CSV.
- `uv run radar import-yahoo <fil.csv>` importerer en Yahoo-eksport.

Se [Kommandolinjen](brugervejledning/kommandolinjen).
