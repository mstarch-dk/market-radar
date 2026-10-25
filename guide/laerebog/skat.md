# Dansk skat for investorer

> **Bemærk:** Skatteregler ændrer sig, ofte hvert år: satser, grænsebeløb, indskudsloftet på aktiesparekontoen og hvilke fonde der står på positivlisten. Dette kapitel forklarer principperne, så du kan forstå radarens tal og stille de rigtige spørgsmål. Det er ikke skatterådgivning. Tjek altid de aktuelle regler på [skat.dk](https://skat.dk), og spørg en rådgiver, hvis din situation er speciel.

## Intuition

To investorer kan eje præcis de samme papirer og få forskelligt afkast efter skat. Det afhænger af, **hvor** papirerne ligger (frie midler, aktiesparekonto eller pension), **hvilken slags** papir det er (en aktie, en dansk fond, en udenlandsk ETF på eller uden for SKATs positivliste), og **hvornår** skatten betales (når du sælger, eller hvert år uanset om du sælger).

For en dansk investor, der bruger ETF'er til at følge temaer og sektorer, er det især to forhold, der betyder noget:

- En udenlandsk ETF, der står på positivlisten, beskattes som aktieindkomst. En, der ikke gør, beskattes som kapitalindkomst, hvilket for de fleste er dyrere.
- På en aktiesparekonto beskattes hele afkastet med en lav, fast sats hvert år, men kun visse papirer må stå der, og der er et loft over indskuddet.

Radaren giver et skøn over skatten af dine egne handler, pr. konto og pr. person, på fanen *Tax* (se [Skat: radarens skatteestimat](brugervejledning/skat)). Det er et estimat: din årsopgørelse er det, der gælder.

## Teori

### Aktieindkomst og kapitalindkomst

Dansk skat deler investeringsindkomst i to hovedkasser:

- **Aktieindkomst**: gevinst, tab og udbytte på aktier og aktiebaserede investeringsforeninger og -selskaber. Den beskattes med en lav sats op til et grænsebeløb og en højere sats derover. Satserne har i en årrække været 27 % og 42 %; grænsebeløbet reguleres hvert år, og for ægtefæller kan uudnyttet grænsebeløb overføres. Tjek det aktuelle år på skat.dk.
- **Kapitalindkomst**: renter, kursgevinster på obligationer og afkast af fonde, der ikke er aktiebaserede eller ikke står på positivlisten. Den lægges sammen med din øvrige indkomst, så satsen afhænger af din samlede situation; for de fleste er den højere end aktieindkomstens laveste sats.

Udbytte fra udenlandske aktier er desuden ofte pålagt udenlandsk kildeskat, som kun delvist kan modregnes eller tilbagesøges.

### Realisations- og lagerbeskatning

- **Realisationsbeskatning**: gevinst eller tab beskattes, når du sælger. Indtil da er gevinsten urealiseret og ubeskattet. Det giver en skattekredit: du betaler skatten senere og har imens hele beløbet investeret.
- **Lagerbeskatning**: hvert år beskattes ændringen i værdi fra årets start (eller købsprisen) til årets slutning, uanset om du har solgt. Der er ingen skattekredit, og en stigning kan udløse skat, uden at du har frigjort penge til at betale den.

### Frie midler

For penge, du investerer uden for pension og aktiesparekonto:

- **Enkeltaktier**: realisationsbeskatning som aktieindkomst. Tab på børsnoterede aktier kan som udgangspunkt modregnes i gevinst og udbytte på børsnoterede aktier, og uudnyttet tab kan fremføres. Tab skal være indberettet; reglerne har særlige betingelser.
- **Danske udloddende aktiebaserede investeringsforeninger**: realisationsbeskatning af kursgevinsten og beskatning af den løbende (minimums)udlodning, begge som aktieindkomst.
- **Aktiebaserede investeringsselskaber**, herunder udenlandske ETF'er og akkumulerende fonde på **positivlisten**: lagerbeskatning som aktieindkomst.
- **Fonde, der ikke er aktiebaserede eller ikke står på positivlisten**: lagerbeskatning som kapitalindkomst.

### Aktiesparekontoen

Aktiesparekontoen (ASK) er en særlig konto med sin egen skat:

- Hele kontoens afkast (kursændringer og udbytte) **lagerbeskattes** hvert år med en fast sats, {{tax:2026.ask.rate|pct}} i 2026. Skatten trækkes typisk direkte fra kontoen.
- Der er et **loft over indskud**, {{tax:2026.ask.deposit_cap}} kr. i 2026. Det måles mod kontoens værdi den 31. december året før: er den 105.000 kr., kan du i 2026 indskyde forskellen op til loftet. Loftet er ændret flere gange; tjek det aktuelle beløb på skat.dk.
- Kun visse papirer må stå på kontoen: børsnoterede aktier og aktiebaserede investeringsforeninger og -selskaber, herunder udenlandske ETF'er **på positivlisten**.
- Et negativt afkast giver negativ skat, som ikke udbetales, men fremføres på kontoen og modregnes i skatten de følgende år med positivt afkast. Ved lukning af kontoen går en uudnyttet negativ skat som udgangspunkt tabt.
- Kontoen er adskilt fra dine frie midler: handler på ASK påvirker ikke gennemsnitsmetoden eller tabsfremførsel i frie midler.

### Positivlisten

SKAT offentliggør hvert år en **liste over aktiebaserede investeringsselskaber**, i daglig tale positivlisten. En udenlandsk fond kommer på listen, hvis udbyderen har registreret den og dokumenteret, at den er aktiebaseret. Listen er afgørende i to henseender:

- I frie midler beskattes en fond på listen som aktieindkomst (lager), en fond uden for listen som kapitalindkomst (lager).
- På aktiesparekontoen må kun fonde på listen stå.

Listen findes pr. **ISIN** (værdipapirets internationale kode), ikke pr. ticker. Samme ETF kan have flere andelsklasser med hver sit ISIN, og kun nogle af dem står måske på listen. SKAT opdaterer listen, og en fond kan både komme på og forsvinde fra den.

### Gennemsnitsmetoden

Når du sælger en del af en aktiebeholdning, skal anskaffelsessummen for de solgte aktier opgøres efter **gennemsnitsmetoden**: den gennemsnitlige købspris for alle dine aktier i samme selskab (af samme slags), ikke prisen for netop de aktier, du købte først eller sidst. Købsomkostninger (kurtage) lægges til anskaffelsessummen, salgsomkostninger trækkes fra salgssummen.

$$
\text{gns. pris} = \frac{\sum (\text{antal}\cdot\text{kurs} + \text{kurtage})}{\text{antal i beholdning}}
$$

Et salg fjerner anskaffelsessum i forhold til det solgte antal og ændrer ikke gennemsnittet for resten. Til skat skal beløbene opgøres i kroner med valutakursen på handelsdagene. Gennemsnittet opgøres på tværs af dine depoter med frie midler; aktiesparekonto og pension holdes uden for.

### Pension

Afkast på pensionsopsparing beskattes med **pensionsafkastskat (PAL-skat)**, {{tax:2026.pension.pal_rate|pct}} i 2026, som lagerbeskatning af det årlige afkast. Et år med negativt afkast giver negativ skat, der fremføres uden tidsbegrænsning. Udbetalingerne beskattes efter pensionstypen. Mange regler om, hvad der må stå på en pensionskonto, afhænger af udbyderen.

## Sådan gør radaren

Fanen *Tax* på [Portfolio](/portfolio) regner skatten for et indkomstår ud fra dine handler (koden: `model/tax.py` og `tax.py`). Brugen af fanen står i [Skat: radarens skatteestimat](brugervejledning/skat); her er metoden.

- **Satser pr. år.** Satser, progressionsgrænse, indskudsloft og PAL-sats står i `config/tax_dk.yaml`, ét afsnit pr. år, hvert tal med kilde og den dato, det er tjekket mod skat.dk. For 2026: aktieindkomst {{tax:2026.share_income.low_rate|pct}} op til {{tax:2026.share_income.progression_limit}} kr. og {{tax:2026.share_income.high_rate|pct}} derover, aktiesparekonto {{tax:2026.ask.rate|pct}} med et indskudsloft på {{tax:2026.ask.deposit_cap}} kr., PAL {{tax:2026.pension.pal_rate|pct}}. Et år uden tjekkede tal giver grundlaget uden skat; et andet års tal bruges aldrig.
- **Konto og person.** Hver rigtig portefølje har en skattetype (*Aktiesparekonto*, *Frie midler*, *Pension* eller *Other*) og en ejer, en skatteperson. En aktiesparekonto og en pensionskonto er hver ét regnskab; konti med frie midler regnes sammen pr. person. *Other* får intet estimat.
- **Kroner på handelsdagen.** Hver handel omregnes med sin egen valutakurs, ellers Yahoos kurs den dag. Værdier ved årets start og slut er lukkekursen den sidste handelsdag i kroner, ikke de udbyttejusterede kurser, så udbytte ikke tælles to gange.
- **Gennemsnitsmetoden** regnes i kroner pr. person og papir over alle personens konti med frie midler: kurtage ved køb lægges til anskaffelsessummen, kurtage ved salg trækkes fra provenuet, og et salg fjerner anskaffelsessum forholdsmæssigt. Køb på aktiesparekonto og pension er holdt uden for. Det er en anden opgørelse end gennemsnitsprisen under *Positions*, som er i papirets egen valuta.
- **Lager** pr. fond og år: $V_{slut} + \text{salg} - V_{start} - \text{køb}$, alle i kroner. Det er SKATs "værdi ved årets slut minus værdi ved årets start eller anskaffelsessummen", skrevet for et vilkårligt antal handler i året.
- **Aktiesparekonto og pension**: afkastet er $V_{slut} - V_{start} - \text{indbetalt} + \text{udbetalt}$ for hele kontoen (beholdning plus kontanter, hvis kontoen har kontantrækker; ellers tæller hvert køb som indbetalt og hvert salg og udbytte som udbetalt). Skatten er afkastet gange satsen; et negativt år giver negativ skat, som fremføres og modregnes i de næste års skat.
- **Klassificering pr. år.** En aktie (Yahoos *quoteType* EQUITY, eller en aktie radaren følger) er realisationsbeskattet aktieindkomst. En fond slås op på positivlistens ark for netop det indkomstår ("Kalenderåret 2026" er arket for 2026) ud fra sin ISIN-kode: på listen er den lagerbeskattet aktieindkomst, uden for listen lagerbeskattet kapitalindkomst. En dansk udloddende fond angiver du selv. En fond uden ISIN, et år uden ark eller en dansk fond uden for listen er *ukendt* og regnes ikke med; den nævnes med værdi og årsag.
- **Aktieindkomst** pr. person: realiserede gevinster på aktier og danske udloddende fonde, udbytte og lagergevinst på positivlistefonde. Tab på børsnoterede aktier (med det fremførte) modregnes i gevinster, udbytte og lagergevinst på positivlistefonde; resten fremføres. Lagertab på positivlistefonde trækkes fra, som det er. Bliver aktieindkomsten negativ, fremføres den. Skatten er den lave sats op til progressionsgrænsen og den høje derover.
- **Kapitalindkomst** fra fonde uden for listen vises som grundlag. Skatten kræver din marginale sats på kapitalindkomst, som du selv angiver; ellers står der ingen skat.
- **Fremførsel** regnes fra kontoens eller personens første år med handler, plus de fremførte tab fra før din historik, som du selv angiver.

> **Bemærk:** Radarens andre sider regner afkast puljet over dine konti og før skat. Det er rigtigt til sammenligningen med ACWI. Skatten regnes kun på fanen *Tax*, og der pr. konto og pr. person. Udbytte tæller med det beløb, du har bogført; udenlandsk kildeskat og ægtefælleregler er ikke med. Listen over, hvad der er med og ikke med, står i [brugervejledningen](brugervejledning/skat#hvad-radaren-regner-med-og-hvad-den-ikke-gør).

## Regneeksempel

Tallene illustrerer principperne. Satser og regler skal tjekkes for det aktuelle år.

### Aktiesparekonto over tre år

| År | Værdi 1. jan. | Indskud | Værdi 31. dec. | Afkast | Fremført tab | Skattepligtigt | Skat 17 % |
|---|---|---|---|---|---|---|---|
| 1 | 100.000 | 20.000 | 132.000 | 12.000 | 0 | 12.000 | 2.040 |
| 2 | 129.960 | 0 | 124.960 | −5.000 | 5.000 | 0 | 0 |
| 3 | 124.960 | 0 | 132.960 | 8.000 | 0 | 3.000 | 510 |

År 1: afkastet er slutværdi minus startværdi minus indskud, $132000 - 100000 - 20000 = 12000$. Skatten trækkes fra kontoen, så år 2 starter på $132000 - 2040 = 129960$. År 2 er negativt; tabet på 5.000 fremføres. År 3 modregnes tabet: $8000 - 5000 = 3000$ er skattepligtigt.

### Gennemsnitsmetoden i frie midler

| Handel | Antal | Kurs | Kurtage | Anskaffelsessum | Beholdning | Gns. pris |
|---|---|---|---|---|---|---|
| Køb | 10 | 100 | 20 | 1.020 | 10 | 102,00 |
| Køb | 10 | 130 | 20 | 2.340 | 20 | 117,00 |
| Salg | 5 | 150 | 20 | 1.755 | 15 | 117,00 |

Salget giver $5 \cdot 150 - 20 = 730$ kr. Den solgte del har en anskaffelsessum på $5 \cdot 117 = 585$ kr. Gevinsten er $730 - 585 = 145$ kr., som er aktieindkomst. De resterende 15 aktier har fortsat gennemsnitsprisen 117 kr. Fanen *Tax* viser salget med anskaffelsessum 585 og gevinst 145 (eksemplet er en af radarens tests).

### Positivliste eller ej

Du køber i frie midler en udenlandsk ETF for 50.000 kr. i løbet af året. Den 31. december er den 56.000 kr. værd. Du har ikke solgt.

- **På positivlisten**: 6.000 kr. er aktieindkomst i år (lagerbeskatning). Næste år er udgangspunktet 56.000 kr.
- **Ikke på positivlisten**: de 6.000 kr. er kapitalindkomst i år, også lagerbeskattet, og typisk med en højere sats.
- **Samme ETF på aktiesparekontoen** (kun mulig, hvis den står på listen): de 6.000 kr. indgår i kontoens afkast og beskattes med kontoens sats.
- **En enkeltaktie i stedet** for ETF'en: ingen skat i år, fordi aktien ikke er solgt (realisationsbeskatning).

## Faldgruber og begrænsninger

- **Satser og grænser ændrer sig.** Indskudsloftet på aktiesparekontoen, grænsebeløbet for aktieindkomst og andre beløb ændres jævnligt. Brug aldrig tal fra et ældre kapitel eller en ældre artikel uden at tjekke.
- **Ticker er ikke ISIN.** En ETF kan findes i flere andelsklasser (akkumulerende, udloddende, forskellige valutaer) med hver sit ISIN. Det er ISIN'et hos din mægler, der skal stå på positivlisten.
- **Lagerskat uden likviditet.** Lagerbeskatning kan give en skatteregning i et år, hvor du ikke har solgt noget. Hav likviditet til den.
- **Skattekredit.** Realisationsbeskatning udskyder skatten. Det er en reel fordel over mange år, som en sammenligning af afkast før skat ikke viser.
- **Tab har begrænsninger.** Hvor og hvordan et tab kan bruges, afhænger af papirets type og kontoen. Et tab på aktiesparekontoen kan kun bruges på kontoen.
- **Puljede tal er ikke skattetal.** Radarens samlede positioner og afkast blander kontotyper. Det er rigtigt til sammenligning med ACWI, men forkert til skat; fanen *Tax* regner pr. konto og person.
- **Udenlandsk kildeskat.** Udbytte fra udenlandske aktier kan være pålagt kildeskat, som ikke altid kan modregnes, særligt på aktiesparekontoen og pension.
- **Radarens skat er et estimat.** Den regner kun med det, du har ført ind, og ikke med alle regler (se listen i [brugervejledningen](brugervejledning/skat#hvad-radaren-regner-med-og-hvad-den-ikke-gør)). Din mæglers årsopgørelse, din forskudsopgørelse og skat.dk er det, der gælder.

## Videre læsning

- Skattestyrelsen, [skat.dk](https://skat.dk): vejledninger om aktier, investeringsfonde og aktiesparekonto, og den årlige liste over aktiebaserede investeringsselskaber (positivlisten).
- Skatteministeriet, *Den juridiske vejledning*, afsnittene om aktier og investeringsbeviser (på skat.dk).
- Aktieavancebeskatningsloven (ABL): beskatning af gevinst og tab på aktier og investeringsbeviser.
- Lov om aktiesparekonto (aktiesparekontoloven), 2018 med senere ændringer.
- Pensionsafkastbeskatningsloven (PAL): beskatning af afkast på pensionsopsparing.
