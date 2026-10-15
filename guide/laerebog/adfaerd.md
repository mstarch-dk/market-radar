# Beslutninger, bias og falsifikation

## Intuition

De fleste investeringsfejl skyldes ikke manglende data, men måden vi bruger dem på. Vi husker vores gode beslutninger og glemmer de dårlige. Vi sælger vinderne for tidligt og holder fast i taberne. Vi finder en god historie og leder derefter efter tal, der bekræfter den. Og når udfaldet er kendt, er vi sikre på, at vi vidste det hele tiden.

Adfærdsøkonomien har beskrevet disse mønstre grundigt. Den gode nyhed er, at de fleste kan modvirkes med enkle vaner:

- **Skriv beslutningen ned, før du kender udfaldet**: tese, horisont og hvad der ville bevise, at du tog fejl.
- **Start med basisraten**: hvor ofte lykkes den slags beslutninger i almindelighed?
- **Forestil dig, at det er gået galt** (pre-mortem), og spørg hvorfor.
- **Gennemgå beslutningerne jævnligt** og bedøm processen, ikke kun resultatet.

Radaren understøtter dem med beslutningsjournalen, med markedssyn, der har en eksplicit falsifikator, og med en løbende kontrol af, om dataene støtter eller modsiger dine syn.

## Teori

### Tabsaversion og prospektteori

Kahneman og Tversky (1979) viste, at mennesker vurderer udfald i forhold til et referencepunkt (ofte købsprisen), og at et tab føles omtrent dobbelt så stærkt som en lige så stor gevinst. Desuden er vi risikovillige i tab ("jeg venter, til den kommer tilbage") og risikoaverse i gevinst ("tag gevinsten hjem"). Værdifunktionen er konkav for gevinster og konveks for tab.

### Dispositionseffekten

Shefrin og Statman (1985) kaldte tendensen til at sælge vindere for tidligt og holde tabere for længe for **dispositionseffekten**. Odean (1998) målte den i 10.000 private konti: investorerne realiserede gevinster markant oftere end tab. Han definerede to andele:

$$
PGR = \frac{\text{realiserede gevinster}}{\text{realiserede} + \text{urealiserede gevinster}} \qquad PLR = \frac{\text{realiserede tab}}{\text{realiserede} + \text{urealiserede tab}}
$$

Er $PGR > PLR$, sælger du hellere vindere end tabere. Odean fandt desuden, at de solgte vindere efterfølgende klarede sig bedre end de beholdte tabere. For en momentuminvestor er det dobbelt dyrt: momentum siger netop, at vindere har tendens til at fortsætte og tabere til at blive ved med at falde (se [Momentumeffekten](laerebog/momentumeffekten)).

### Overmod

Barber og Odean (2000) fandt, at de husstande, der handlede mest, fik det laveste nettoafkast; handelsomkostningerne åd fordelen op. Overmod viser sig som for mange handler, for koncentrerede porteføljer og for snævre forventninger til udfaldet. Den målte alfa for en enkeltaktie er næsten altid statistisk støj (se [Beta, alfa og faktorer](laerebog/beta-og-alfa)), men den føles som evne.

### Bagklogskab, bekræftelse og fortællinger

- **Bagklogskabsbias** (Fischhoff, 1975): når udfaldet er kendt, vurderer vi det som mere forudsigeligt, end det var. Uden en skriftlig optegnelse omskriver hukommelsen, hvad du troede.
- **Bekræftelsesbias**: vi søger og vægter information, der bekræfter det, vi allerede tror. En investor med en tese om AI læser AI-optimisme.
- **Fortællingsfejlen** (*narrative fallacy*, Taleb, 2007): en sammenhængende historie føles mere sandsynlig end en usammenhængende, selv om hver ekstra detalje gør den mindre sandsynlig.
- **Nylighedsbias** (*recency*): de seneste måneders udvikling vægtes for højt. Efter et års stigninger føles risikoen lav; efter et krak føles den uendelig.

### Basisrater

Kahneman (2011) skelner mellem *indefra*-synet (detaljerne i netop denne sag) og *udefra*-synet (hvordan det går for sager af samme type). Basisraten er udgangspunktet, som de konkrete detaljer så kan flytte en smule.

For aktier er basisraterne nøgterne. Bessembinder (2018) fandt, at fire ud af syv amerikanske aktier over deres levetid gav et lavere afkast end statsveksler, og at hele aktiemarkedets nettoformueskabelse kom fra omkring 4 % af selskaberne. En tilfældig enkeltaktie er altså oftere en skuffelse end en succes, mens markedet som helhed klarer sig godt. Det er en grund til, at radarens benchmark er ACWI: hver idé skal måles mod nul-indsats-alternativet.

### Pre-mortem

Klein (2007) foreslog **pre-mortem**: før beslutningen forestiller du dig, at den er gået galt, og skriver ned, hvorfor. Det udnytter, at det er lettere at forklare et kendt udfald end at forudsige et ukendt, og gør det socialt acceptabelt at være kritisk over for sin egen idé.

### Falsifikation

Popper (1959) argumenterede for, at en videnskabelig påstand skal kunne vises forkert. "AI vil ændre verden" kan ikke falsificeres; "halvlederaktier taber relativ styrke i et kvartal, mens estimaterne falder" kan. En investeringstese, der ikke kan vise sig forkert, kan aldrig give dig et signal om at genoverveje den. Tetlock og Gardner (2015) viste, at de bedste prognosemagere formulerer præcise, tidsbestemte påstande, holder regnskab med deres træfsikkerhed og justerer i små skridt.

### Proces mod udfald

Et godt udfald kan komme af en dårlig beslutning (held), og en god beslutning kan give et dårligt udfald (uheld). Duke (2018) kalder sammenblandingen *resulting*. Over få beslutninger dominerer heldet; først over mange viser processens kvalitet sig.

| | Godt udfald | Dårligt udfald |
|---|---|---|
| **God proces** | fortjent | uheld: gentag processen |
| **Dårlig proces** | held: lær ikke af det | fortjent |

Beslutningsjournalen er værktøjet til at kunne udfylde tabellen ærligt bagefter.

## Sådan gør radaren

### Beslutningsjournalen

Skillen `/journal` i Claude Code (se [Claude Code-skills](brugervejledning/claude-code)) skriver en beslutning ned som en fil i `journal/` i din datamappe, når du køber, sælger, øger, reducerer eller bevidst lader være (*pass*). Hver post har:

- **Handling, konto og horisont**, og en dato for opfølgning (`review_by`).
- **Tesen med dine egne ord.** Skillen omformulerer den ikke.
- **Radaren på beslutningstidspunktet**: momentumscore, trend, afkast over 1, 3 og 6 måneder, relativt afkast mod ACWI, sektorens kvadrant og regimet. Det er dit værn mod bagklogskab: du kan se, hvad du vidste dengang.
- **Markedssyn**, som beslutningen udtrykker, hvis nogen.
- **Exitregler** i tre dele: hvad der ville ugyldiggøre tesen, en stop- eller trendregel (fx radarens regelbaserede stop, se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse)), og et kursmål eller en tidsgrænse. Giver du ingen ugyldighedsregel, foreslår skillen en og markerer den som et forslag.
- **Pre-mortem**: den mest sandsynlige grund til, at det går galt.

Med `/journal review` gennemgås alle åbne poster månedligt. Hver får status **Intact** (intakt), **Weakening** (nogle regler er tæt på at udløses) eller **Invalidated** (en regel er udløst) ud fra de aktuelle radardata. Lukkede handler fra de seneste tre måneder gennemgås også: hvad skete der efter exit? Gennemgangen slutter med to-tre mønstre på tværs af beslutningerne, fx at sælge vindere for tidligt, at øge i tabere eller at samle for meget i ét tema. Skillen ændrer ikke en posts status uden at spørge dig.

Skillen `/compare` har desuden en indbygget *red team*-runde (de stærkeste modargumenter) og en beslutningsoptegnelse, og sammenligner altid med blot at eje ACWI: basisraten i praksis.

### Markedssyn med falsifikator

Et markedssyn på [My market views](/views) er din subjektive overbevisning, fx "AI bliver ved med at drive indtjeningsvækst". Hvert syn har en **falsifikator**: hvad ville vise, at du tager fejl? De færdige skabeloner i `config/views.yaml` har én hver, og de kommer ofte i modsatte par (fx "AI dominerer" over for "AI er en boble"), så du ser begge sider. Se [Mine markedssyn](brugervejledning/markedssyn).

Synet knyttes til **indikatorer** med en forventet retning (op eller ned). Radaren (`signals/views.py`) måler hver indikators ændring over cirka tre måneder:

- For kursbaserede indikatorer: 63 handelsdage. Det kan være et papirs afkast minus ACWI's, et forhold mellem to papirer (fx kobber/guld) eller et eget afkast.
- For FRED-serier og OECD's ledende indikatorer: sidste værdi mod værdien cirka tre måneder før (mindst 88 dage tidligere).

Hver indikator får en af fire tilstande:

| Tilstand | Betingelse |
|---|---|
| *supports* (støtter) | ændringen er uden for båndet og i den forventede retning |
| *contradicts* (modsiger) | ændringen er uden for båndet og i modsat retning |
| *flat* (flad) | ændringen er inden for ± båndet (indikatorens `band` i `config/views.yaml`) |
| *no data* (ingen data) | data mangler eller er for gamle |

"For gamle" betyder, at den seneste observation er ældre end en fast grænse i koden: 10 dage for kursdata, 75 dage for FRED og 120 dage for OECD's ledende indikatorer.

Samlet får synet en dom: *supported* (kun støtte), *contradicted* (kun modsigelse), *mixed* (begge dele), *unclear* (hverken støtte eller modsigelse, kun flade eller manglende) eller *no data*. Radaren vurderer ikke, om dit syn er rigtigt. Den rapporterer, hvad dens egne målinger har gjort, og lader det være op til dig, om falsifikatoren er opfyldt.

## Regneeksempel

### Dispositionseffekten i din egen journal

Gennem et år noterer du hver gang, du sælger noget, hvilke positioner der stod med gevinst og tab på salgsdagen:

- Du realiserede 12 gevinster; på de samme dage havde du 28 urealiserede gevinster.
- Du realiserede 4 tab; på de samme dage havde du 36 urealiserede tab.

$$
PGR = \frac{12}{12 + 28} = 0.30 \qquad PLR = \frac{4}{4 + 36} = 0.10
$$

Du har realiseret gevinster tre gange så hyppigt som tab. Det er præcis det mønster, Odean fandt, og et konkret emne til næste månedlige gennemgang: hvilke tabere holder du, og hvad siger exitreglerne om dem?

### Evidens for et markedssyn

Synet "AI bliver ved med at drive indtjeningsvækst" har tre indikatorer, alle med forventningen "op" (båndene er skabelonens):

| Indikator | Ændring, 3 mdr. | Bånd | Tilstand |
|---|---|---|---|
| Halvledere (SMH) mod ACWI | +5,0 procentpoint | ±2 | støtter |
| Software (IGV) mod ACWI | −1,0 procentpoint | ±2 | flad |
| Nasdaq-100 (QQQ) mod ACWI | −3,0 procentpoint | ±1,5 | modsiger |

Én støtter, én modsiger, én er flad: dommen er *mixed*. Synets falsifikator ("halvledere og software taber relativ styrke i et kvartal, mens estimaterne falder") er ikke opfyldt, for halvlederne er stærke. Men det brede teknologiindeks halter, og det er værd at notere i journalen, hvis en position hviler på synet.

### Proces mod udfald

Du købte en aktie med en nedskrevet tese og et stop. Seks uger efter udløses stoppet, og du sælger med 7 % tab; tre måneder senere er aktien 30 % højere. Udfaldet var dårligt, men var processen? Hvis tesen var falsificerbar, stoppet var dimensioneret efter volatiliteten, og exit fulgte reglen, var det et uheld i tabellens øverste højre felt. Lærdommen er ikke "brug aldrig stop", men måske "var stoppet for tæt i forhold til ATR?", et spørgsmål du kun kan besvare, fordi du skrev tallene ned.

## Faldgruber og begrænsninger

- **En journal, du ikke læser, hjælper ikke.** Værdien ligger i gennemgangen. Brug opfølgningsdatoen.
- **Exitregler skal være konkrete.** "Hvis fundamentet ændrer sig" kan altid bortforklares. "Hvis kursen lukker under 200-dages gennemsnittet" eller "hvis næste to kvartaler viser faldende omsætning" kan ikke.
- **Radarens evidens er ikke en dom over dit syn.** Tre måneders data kan være støj, og indikatorerne er kun proxyer. Et syn kan være rigtigt på lang sigt og modsiges på kort.
- **Bias virker også på fortolkningen af radaren.** Det er fristende at fremhæve de indikatorer, der støtter, og affeje de andre som "flade". Skriv på forhånd, hvad der tæller.
- **Basisrater skal passe.** Bessembinders tal gælder amerikanske enkeltaktier over hele deres levetid, ikke en momentumstrategi over seks måneder. Brug den nærmeste relevante referenceklasse.
- **Proces kan også blive ritual.** En journal udfyldt bagefter for at retfærdiggøre en handel er værre end ingen, fordi den giver falsk tryghed.

## Videre læsning

- Daniel Kahneman og Amos Tversky, "Prospect Theory: An Analysis of Decision under Risk", *Econometrica* 47(2), 1979.
- Hersh Shefrin og Meir Statman, "The Disposition to Sell Winners Too Early and Ride Losers Too Long", *Journal of Finance* 40(3), 1985.
- Terrance Odean, "Are Investors Reluctant to Realize Their Losses?", *Journal of Finance* 53(5), 1998.
- Brad M. Barber og Terrance Odean, "Trading Is Hazardous to Your Wealth", *Journal of Finance* 55(2), 2000.
- Hendrik Bessembinder, "Do Stocks Outperform Treasury Bills?", *Journal of Financial Economics* 129(3), 2018.
- Gary Klein, "Performing a Project Premortem", *Harvard Business Review* 85(9), 2007.
- Daniel Kahneman, *Thinking, Fast and Slow*, Farrar, Straus and Giroux, 2011.
- Philip E. Tetlock og Dan Gardner, *Superforecasting*, Crown, 2015.
- Annie Duke, *Thinking in Bets*, Portfolio, 2018.
- Karl Popper, *The Logic of Scientific Discovery*, Hutchinson, 1959.
