# Rigtige og virtuelle porteføljer

Alle dine handler ligger i en portefølje. Radaren skelner mellem to slags: **rigtige** porteføljer, som er dine konti, og **virtuelle**, som er simuleringer og A/B-tests. Forskellen afgør, hvad der tæller som "dit" i appen, i månedsbriefen og i Claude-skills. De har hver sin side: dine konti styrer du under fanen *Accounts* på siden [Portfolio](/portfolio), de virtuelle på siden [Experiments](/experiments) (se [Eksperimenter: virtuelle porteføljer](brugervejledning/eksperimenter)). På kommandolinjen: `uv run radar portfolios`.

## Rigtige og virtuelle

| | Rigtig (*real*) | Virtuel (*virtual*) |
|---|---|---|
| Hvad | En af dine konti, fx aktiesparekonto eller frie midler | En simulering, en test eller en kopi |
| Tæller som dit | Ja, overalt: beholdninger, `summary.json`, briefs, skills | Kun når du vælger den |
| Kontanter | Advarsel, hvis kontanterne går i minus (kun med kontantrækker) | Kan kun bruge, hvad der er indbetalt (fejl) |
| Slet | Kun når den er tom; ellers arkivér eller flyt rækkerne | Kan slettes med alle rækker (der tages en sikkerhedskopi) |

Handler fra før porteføljerne fandtes, ligger i den rigtige portefølje *Main*, indtil du flytter dem.

Virtuelle porteføljer kommer aldrig med af sig selv. De vises kun på siden *Experiments*, når du vælger dem i porteføljevælgeren på *Holdings & watchlist* eller *Returns*, nævner dem ved navn på kommandolinjen eller beder om dem med `--include-virtual`, når du pakker dine data til en anden computer.

## Opret en portefølje

En ny konto: skriv et navn i feltet nederst under fanen *Accounts* på siden *Portfolio*, vælg skattetype, og klik *Add account*. En ny virtuel portefølje opretter du nederst på siden *Experiments*; den får automatisk tagget `virtual`.

Skattetypen bestemmer, hvordan fanen *Tax* regner kontoen: en aktiesparekonto og en pensionskonto hver for sig, konti med frie midler samlet pr. ejer. Hvem der ejer hver konto, sætter du på fanen *Tax*; se [Skat: radarens skatteestimat](brugervejledning/skat).

Under *Accounts* sætter du også kontoens kurtageskema (*fees: …*), som formularen bruger til at estimere kurtagen på en handel. Se [Kurtage-estimatet](brugervejledning/portefolje#kurtage-estimatet).

### Skattetype

Skattetypen fortæller radaren og Claude-skills, hvordan kontoen beskattes. Den ændrer ikke radarens afkastberegninger.

| Type | I appen | Kort fortalt |
|---|---|---|
| `ask` | *Aktiesparekonto* | Lagerbeskatning med 17 % af alt; kun aktier og fonde på positivlisten |
| `frie_midler` | *Frie midler* | Aktier beskattes ved realisation; fonde på positivlisten lagerbeskattes som aktieindkomst |
| `pension` | *Pension* | PAL-skat (15,3 % lager) af afkastet |
| `other` | *Other* | Alt andet |

Satserne står i appen som korte påmindelser; reglerne er beskrevet i [Dansk skat for investorer](laerebog/skat).

### Udbyttepolitik

Hver portefølje har en udbyttepolitik:

- `reinvested` (standard): udbytte er allerede med i de udbyttejusterede kurser. Udbytterækker gemmes til orientering, men tælles ikke.
- `cash`: radaren bruger de handlede kurser og lægger dine udbytterækker (*Dividend*) til som kontanter.

Politikken ændres på kommandolinjen: `uv run radar portfolios edit ASK --dividends cash`. Kortet i appen viser den ikke.

## Standardporteføljen

Nye handler og importer havner i standardporteføljen, medmindre du vælger en anden. Klik *make default* ud for en rigtig, aktiv portefølje, eller kør `uv run radar portfolios default ASK`. Kun rigtige, ikke-arkiverede porteføljer kan være standard.

## Tags og A/B-grupper

Et tag er en fri etiket, fx `momentum-a` eller `core`. Klik *+ tag* for at tilføje et og × på tagget for at fjerne det. Tags gemmes med små bogstaver og må højst være 32 tegn.

Tags ændrer aldrig, hvad der tæller som dit. De bruges til at gruppere:

- I porteføljevælgeren under *Tagged* kan du vise alle porteføljer med et tag samlet.
- På siden [Returns](/returns) bliver et tag til én linje, hvor porteføljerne er lagt sammen. To tags giver en A/B-test: fx tre porteføljer med `momentum-a` mod tre med `momentum-b`.

## Arkivér, slet og flyt

- **Arkivér** (*archive*): porteføljen beholder alle rækker, men tæller ikke længere som din og forsvinder fra listen. *show N archived* viser den igen, og *unarchive* henter den tilbage.
- **Slet** (*delete*): en virtuel portefølje slettes med alle rækker, efter at radaren har taget en sikkerhedskopi i `backups/` i datamappen. En rigtig portefølje kan kun slettes, når den er tom.
- **Flyt rækker**: på siden *Portfolio* kan handler i *Main* flyttes til en anden rigtig portefølje, alle eller ét symbol ad gangen. På kommandolinjen kan alle porteføljer flyttes: `uv run radar portfolios move Main --to ASK --symbol NOVO-B.CO`. En flytning afvises, hvis et salg ville miste det køb, det hører til.

Radaren tager en sikkerhedskopi før hver flytning.

## Fork: en kopi ved en dags lukkekurs

En fork er en virtuel kopi af en portefølje, som den stod ved lukkekursen en bestemt dag. Den bruges til at teste en ændring mod originalen: kopiér porteføljen, foretag ændringen i kopien, og sammenlign de to fra den dag.

1. Klik *fork into an experiment* ud for kontoen under fanen *Accounts* (kun konti med rækker).
2. Skriv datoen (ÅÅÅÅ-MM-DD) og et navn til kopien.
3. Radaren opretter en virtuel portefølje med én indbetaling af porteføljens værdi den dag og et køb af hver beholdning til dagens lukkekurs og valutakurs. Kopien får tagget `fork`.
4. Siden [Experiments](/experiments) åbner med kopien. Under fanen *Returns* kan du åbne den på siden *Returns* og sammenligne den med originalen fra den dag.

Mangler en beholdning kurs eller valutakurs den dag, afvises forken. Udbytte, som originalen fik før dagen, bliver hos originalen.

Kopiens køb koster ingen kurtage: de kopierer beholdningen, de er ikke handler. Kopien overtager originalens kurtageskema, så de handler, du laver i den bagefter, får samme kurtage-estimat som på kontoen (fx Danske Banks mindstekurtage på 29 kr.). Har originalen intet skema, har kopien heller intet, og simuleringer regner da med {{settings:backtest.fee_bps}} basispoint (`backtest.fee_bps`). Kopiens parametre (`fee_model`) siger, hvilken af delene der gælder. Se [Kurtagen i simuleringen](brugervejledning/stop-simulering#kurtagen-i-simuleringen).

På kommandolinjen: `uv run radar portfolios fork ASK "ASK test" --date 2026-06-30 [--cash 10000] [--tag test]`. `--cash` lægger ekstra kontanter i kopien.

## Simuleringer af dine handler

`uv run radar sim exits` laver to virtuelle porteføljer pr. rigtig portefølje, fx *ASK · exits overlay* og *ASK · exits rules*. De afspiller dine handler med radarens stop og take-profit fulgt og har tagget `exits-overlay` eller `exits-rules`. En ny kørsel erstatter den forrige. Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering).

## A/B-test: kvalitet og værdi mod momentum

Radaren kan køre en test fremad i tid af sine to scorer mod hinanden. `uv run radar abtest start` laver tre virtuelle porteføljer med tagget `ab-qvm`:

- *A/B · Kvalitet+værdi*: de {{settings:abtest.n}} aktier med den højeste K+V (gennemsnittet af [kvalitets- og værdiscoren](laerebog/kvalitetsscore); med `abtest.value_score: value` kun værdiscoren).
- *A/B · Momentum*: de {{settings:abtest.n}} med den højeste [momentumscore](laerebog/momentumscore), rangeret på tværs af alle fire regioner på én gang.
- *A/B · 50/50*: begge lister med halv vægt hver. En aktie på begge lister får begge halvdele.

Hver kurv har lige vægte, højst {{settings:abtest.max_per_sector}} aktier fra samme sektor og starter med {{settings:abtest.capital}} kr. (virtuelt). Kandidaterne er radarens egne aktielister, og kun aktier med en kurs og en DKK-kurs kan købes.

**Én gang om måneden.** Den første rapport i hver kalendermåned (efter *Update data* eller `uv run radar run`) gemmer nye lister ud fra den dags scorer. Næste handelsdag sælges det, der er røget af listen, og alle tre porteføljer handles til de nye vægte til dagens lukkekurser og DKK-kurser. Et køb bruger aldrig flere penge, end kurven har, og er næste handelsdags kurser ikke hentet endnu, venter listen til næste opdatering. Mangler en aktie, kurven ejer, kurs eller DKK-kurs den dag, beholdes den uændret. Den tæller med sin seneste kurs i den værdi, de andre vægte regnes af, så pengene ikke bliver liggende kontant. Hver handel koster {{settings:backtest.fee_bps}} basispoint (`backtest.fee_bps`). Porteføljerne kommer ikke fra en konto, så intet kurtageskema gælder for dem. En gemt liste ændres aldrig bagefter, så testen kan ikke se frem eller justeres i bakspejlet. Det er den rene test, som backtests på fortiden ikke kan give.

**Følg den** på siden [Experiments](/experiments), hvor testen har sit eget kort med kurvenes afkast og næste ombalancering, og hver kurv viser beholdning, handler og ombalanceringer. Eller med `uv run radar abtest status`, eller på siden [Afkast](/returns) med tagget `ab-qvm`, mod ACWI. Status viser også korrelationen mellem kurvenes ugentlige afkast; den kræver mindst {{settings:risk.min_weeks}} uger. Se [Diversifikation og korrelation](laerebog/diversifikation#værdi-og-momentum-side-om-side).

> **Bemærk:** Et par måneder siger næsten intet. Forskelle mellem strategier af denne slags kræver typisk flere år at skelne fra tilfældigheder.

## Porteføljevælgeren og ?pf=

Siderne [Holdings & watchlist](/me), [Portfolio](/portfolio), [Returns](/returns) og [Experiments](/experiments) læser valget af porteføljer fra `?pf=` i adressen. *Portfolio* viser kun dine konti (vælg én med kortene øverst), og *Experiments* viser en virtuel portefølje, når den er valgt. Vælgeren *Portfolio* på *Holdings & watchlist* har disse muligheder:

| Valg | I adressen |
|---|---|
| *Yours: every real portfolio* (standard) | intet, eller `?pf=real` |
| Én bestemt portefølje | `?pf=3` (portefølje-id) |
| Flere porteføljer | `?pf=3,5` |
| *Every virtual portfolio* | `?pf=virtual` |
| Alle med et tag | `?pf=tag:momentum-a` |
| *Everything, virtual included* | `?pf=all` |

Da valget står i adressen, kan du gemme en visning som bogmærke. *back to yours* nulstiller valget.

## Kommandolinjen

| Kommando | Gør |
|---|---|
| `radar portfolios list [--json] [--archived]` | Viser porteføljerne med type, skattetype, antal rækker og tags |
| `radar portfolios add NAVN [--virtual] [--kind ask\|frie_midler\|pension\|other] [--tag T]` | Opretter en portefølje |
| `radar portfolios edit NAVN [--rename NYT] [--kind …] [--dividends reinvested\|cash] [--note …]` | Ændrer navn, skattetype, udbyttepolitik eller note |
| `radar portfolios tag NAVN TAG…` / `untag NAVN TAG…` | Tilføjer eller fjerner tags |
| `radar portfolios default NAVN` | Gør porteføljen til standard |
| `radar portfolios move NAVN --to ANDEN [--symbol X]` | Flytter rækker |
| `radar portfolios fork NAVN NYT --date D [--cash X] [--tag T]` | Laver en virtuel kopi |
| `radar portfolios archive NAVN [--undo]` | Arkiverer eller henter tilbage |
| `radar portfolios delete NAVN [--yes]` | Sletter (virtuel, eller tom rigtig) |

Alle kommandoer køres som `uv run radar …`. Se også [Kommandolinjen](brugervejledning/kommandolinjen).

> **Tip:** Brug de samme navne på dine rigtige porteføljer som i `notes/investor.md` i datamappen. `/journal` registrerer handler i porteføljen ved navn. Se [Claude Code-skills](brugervejledning/claude-code).
