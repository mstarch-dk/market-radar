# Mine markedssyn

Et markedssyn er din egen, subjektive overbevisning om, hvor markederne er på vej hen: "europæiske forsvarsudgifter bliver ved med at stige", "AI-aktier er i en boble", "renterne i euroområdet stiger". På siden [My market views](/views) skriver du dem ned med hvor sikker du er, over hvilken horisont, og hvad der ville få dig til at skifte mening.

Radaren dømmer ikke dine syn. Den gør to ting:

- **Evidens**: hvad radarens egne data har gjort de seneste tre måneder i forhold til hvert syn.
- **Sammenhæng**: hvordan hver aktie eller fond passer med dine syn, hvis de viser sig at holde.

Så bliver det synligt, når et navn passer med dit syn, men data taler imod synet. Teorien bag at skrive en falsifikation står i [Beslutninger, bias og falsifikation](laerebog/adfaerd).

## Skriv et syn

Du kan starte på to måder:

- *Start from a ready-made view*: en liste af færdige syn, ordnet efter område. Modsatte syn står side om side (fx "AI bliver ved med at drive indtjeningen" og "AI-aktier er i en boble"); vælg det, du faktisk tror på, eller ingen af dem. *Use this* åbner synet i editoren med udsagn, eksponeringer, indikatorer og et forslag til falsifikation udfyldt.
- *Write your own view*: en tom editor.

Editoren har disse felter:

| Felt | Indhold |
|---|---|
| *Statement* | Synet i én sætning |
| *How sure are you?* | Overbevisning 1–5: *a hunch*, *leaning*, *fairly sure*, *confident*, *very sure* |
| *Over what horizon?* | 3 måneder, 6 måneder, 1 år eller 3 år |
| *Why do you believe it?* | Din begrundelse (valgfri) |
| *What would change your mind?* | Den observation, der ville få dig til at droppe synet |

### Hvad synet hjælper og skader

Under *What it helps or hurts* tilføjer du eksponeringer med *+ Add exposure*. Hver har en retning (*helps* eller *hurts*) og en type:

- *ETF / theme*: en ETF, radaren følger, fx SMH for halvledere.
- *Sector*: en Yahoo-sektor, fx Technology.
- *Industry*: en branche; et navn matcher, når branchen indeholder teksten, fx "Banks".
- *Region / country*: en af radarens regioner eller et land.
- *Ticker*: et bestemt symbol, fx NOVO-B.CO.

En ETF matcher også enhver aktie, hvis ugentlige afkast i forhold til ACWI bevæger sig med ETF'en (se [Sammenhæng pr. navn](#sammenhæng-pr-navn)).

### Hvad ville vise det i data

Under *What would show it in the data* vælger du indikatorer med *+ Add indicator* og om de bør stige (*should rise*) eller falde (*should fall*), hvis du har ret. Indikatorerne kommer fra et fast katalog i `config/views.yaml`:

- en ETF's afkast minus ACWI's (fx halvledere mod ACWI),
- forholdet mellem to kurser (fx kobber mod guld),
- et symbols eget afkast,
- ændringen i en FRED-serie (fx en rente) eller en OECD-ledende indikator.

Alle måles over cirka tre måneder.

## Kortene

Hvert aktivt syn vises som et kort med udsagnet, overbevisningen som prikker (●●●○○), horisont, oprettelsesdato, eksponeringerne (*helps …* / *hurts …*), indikatortabellen, begrundelse og falsifikation. Knapperne er *Edit*, *Archive* (eller *Re-activate*) og *Delete*. En sletning kan fortrydes med *Undo* lige bagefter. Arkiverede syn ligger under *Archived views* og tæller ikke med i sammenhængen.

## Evidens

For hver indikator viser kortet værdien og en af fire tilstande:

| Tilstand | Betyder |
|---|---|
| *supports* | Indikatoren har bevæget sig i den retning, synet forventer |
| *contradicts* | Den har bevæget sig modsat |
| *flat* | Ændringen ligger inden for indikatorens bånd: intet klart signal |
| *no data* | Ingen eller for gamle data |

Båndet er sat pr. indikator i `config/views.yaml`. Data regnes for for gamle efter nogle dage for kurser og efter nogle måneder for månedlige serier som OECD; grænserne ligger i koden.

Kortets mærke *data: …* samler indikatorerne:

- *supported*: mindst én støtter, ingen modsiger.
- *contradicted*: mindst én modsiger, ingen støtter.
- *mixed*: begge dele.
- *unclear*: kun flade indikatorer (og evt. nogle uden data).
- *no data*: ingen indikatorer med data, eller ingen indikatorer valgt.

Har et syn ingen indikatorer, står der, at radaren ikke kan tjekke det mod data.

> **Bemærk:** Evidensen er en beskrivelse af de seneste tre måneder, ikke en prognose. Et syn med horisont på tre år kan sagtens have tre dårlige måneder bag sig.

## Sammenhæng pr. navn

For hvert navn ser radaren på hvert aktivt syn og finder de eksponeringer, der gælder for navnet:

- *Ticker*, *Sector*, *Industry* og *Region / country* matcher fuldt, når de passer.
- *ETF / theme* matcher fuldt, når navnet er ETF'en eller dens UCITS-version. Ellers matcher den med styrken af korrelationen, når navnets ugentlige afkast i forhold til ACWI over det seneste år korrelerer mindst 0,5 med ETF'ens (kræver mindst 26 ugers fælles historik; begge tal står i `config/views.yaml`).

Pr. syn bliver scoren den stærkeste *helps* minus den stærkeste *hurts*, mellem −1 og 1. Med en score på mindst 0,35 er navnet *aligned* med synet, med højst −0,35 er det *conflicts*. Trækker synet begge veje uden at nå grænsen, er det *mixed*; gælder ingen eksponering, er det *unrelated* (ikke neutralt: synet siger bare intet om navnet).

Det samlede mærke vægter de syn, der gælder for navnet, med din overbevisning. Det vises som:

| Mærke | Betyder |
|---|---|
| *fits your views* | Samlet *aligned* |
| *against your views* | Samlet *conflicts* |
| *mixed* | Trækker begge veje |
| *unrelated* | Ingen af dine syn siger noget om navnet |

### Hvor du ser det

- På [tickerprofilen](brugervejledning/tickerprofil) i kortet *Your market views*: det samlede mærke, de syn der gælder med begrundelse, og hvad data siger om hvert syn.
- På [Momentum](brugervejledning/momentum) og [Discover](brugervejledning/discover) i kolonnen *Views* (den vises, når du har mindst ét aktivt syn).
- I Claude-skills `/research`, `/compare` (kun med `--personal`), `/market-brief` og `/journal`. Se [Claude Code-skills](brugervejledning/claude-code).

## Personlige data

Dine syn er personlige og gemmes i `userdata/radar.db`. De kommer med i:

- tickerprofilen i appen og `uv run radar info <TICKER>`,
- `uv run radar info A B` (sammenligning) kun med `--personal`,
- `uv run radar views [--json] [--archived]`, som skills læser,
- bundtet til [månedsbriefen](brugervejledning/maanedsbrief) som `views.json`.

`uv run radar views` viser hvert syn med overbevisning, horisont, hvad det hjælper og skader, evidensen pr. indikator og din falsifikation.

## Tips

- Skriv falsifikationen konkret: "halvledere taber relativ styrke i et kvartal, mens estimaterne falder" er brugbar, "hvis det går dårligt" er ikke.
- Brug overbevisningen ærligt. Et syn på 1 (*a hunch*) vægter mindre i det samlede mærke.
- Når data i længere tid modsiger et syn med høj overbevisning, så læs din egen falsifikation igen. Arkivér synet, hvis du har skiftet mening; så forbliver historikken.
- Et syn er en hypotese, du vil teste, ikke en grund i sig selv til at købe eller sælge.
