# Stop-loss, take-profit og positionsstørrelse

## Intuition

Hvor meget du kan tabe på en position, afhænger af to ting: hvor stor den er, og hvor langt du lader den falde, før du tager stilling. Det første er **positionsstørrelse**, det andet er **stoppet**. De hænger sammen: en position med et tæt stop kan være større end en med et vidt stop, for samme samlede risiko.

Et stop-loss er en regel, der på forhånd siger: "falder kursen hertil, tager jeg stilling (eller sælger)". Det beskytter mod den mest almindelige fejl hos private investorer, at holde fast i tabere i håbet om at komme tilbage (se [Beslutninger, bias og falsifikation](laerebog/adfaerd)). Men et stop har en pris: almindelig støj kan ramme det, så du sælger lige før en stigning, og hver handel koster.

Et godt stop er derfor:

- **Volatilitetsskaleret**: vidt for en aktie, der svinger meget, tæt for en rolig.
- **Glidende** (trailing): det følger kursen op, men aldrig ned, så en gevinst låses delvist.
- **Regelbaseret**: bestemt før, ikke under, et fald.

En **take-profit** (kursmål) er det modsatte: et niveau, hvor gevinsten er stor nok til at tage stilling. Forholdet mellem den mulige gevinst og det mulige tab kaldes **reward/risk**.

## Teori

### Evidensen for stop-loss

Forskningen er blandet. Kaminski og Lo (2014) viser, at hvis afkast følger en ren random walk, sænker et stop-loss det forventede afkast: du sælger efter et fald og misser det efterfølgende (lige så sandsynlige) opsving. Hvis afkast derimod har momentum, altså positiv autokorrelation, kan et stop både øge afkastet og mindske risikoen, fordi et fald varsler flere fald. Lo og Remorov (2017) finder, at gevinsten afhænger stærkt af handelsomkostninger og af, hvor tæt stoppet ligger: for tætte stop bliver ramt af støj.

Han, Zhou og Zhu (2016) viser, at en simpel stop-loss-regel på en momentumstrategi kan reducere de store momentumkrak markant. Det passer til radaren, der netop er bygget om momentum på 1–6 måneder (se [Momentumeffekten](laerebog/momentumeffekten)).

Den ærlige konklusion: et stop er først og fremmest et risikostyrings- og disciplinværktøj. Det begrænser, hvor galt det kan gå, og tvinger en genovervejelse. Det er ikke en kilde til merafkast i sig selv.

### Virker stop på momentumaktier?

Momentumaktier er netop dem, hvor et stop har det sværest:

- **Den højre hale.** Momentum tjener en stor del af sit afkast på få aktier, der stiger meget. Et kursmål (take-profit) sælger dem tidligt, og et stop, der ligger tæt, ryster dem ud i et almindeligt tilbagefald, før de stiger videre.
- **Høj volatilitet.** De stærkeste aktier svinger typisk 3–5 % om dagen. Et ATR-stop på 3 × ATR ligger så 10–15 % under toppen, mens fald på 20–30 % undervejs er almindelige for en vinder.
- **Ingen vej tilbage.** Når pengene efter et salg står i et bredt indeks, er en fejlagtig udrystning permanent. Genkøb hjælper kun, hvis det ikke selv bliver til flere handler i støjen.
- **Spredning gør meget af arbejdet.** I en kurv på 15 aktier udligner de enkelte styrt hinanden delvist. Det, der er tilbage, er markedets fald, og dem tager et stop på hver aktie ofte for sent og køber ikke tilbage i tide.

Alternativet til stop er **størrelse**: læg kun en del af pengene i momentumkurven og resten i et bredt indeks fra starten. Det skærer risikoen lineært, uden at amputere den højre hale, og koster kun merafkastet på den del, der står i indekset.

Radaren tester det med `radar study exits` (se [Test momentumscoren på historikken](brugervejledning/scoretest#varianter-af-stopreglen)). I testen fra oktober 2026 (månedens 15 bedste aktier, 54 datoer, 6 måneder) gjaldt:

| | Afkast | Gns. største fald | 10 % dårligste |
|---|---|---|---|
| Beholdt | 25,0 % | −17,5 % | −1,1 % |
| Radarens regel | 7,6 % | −10,9 % | −5,8 % |
| Uden take-profit, $k$ 5 | 16,0 % | −14,9 % | −5,7 % |
| Salg under 200-dages gennemsnittet | 22,3 % | −16,8 % | −5,8 % |
| 75 % i kurven, 25 % i ACWI | 20,1 % | −15,1 % | −0,3 % |
| 50 % i kurven, 50 % i ACWI | 15,2 % | −12,7 % | 0,1 % |

Hver variant af stoppet købte et mindre fald med en større del af afkastet end en tilsvarende fordeling med ACWI, og ingen af dem forbedrede det dårligste udfald over 6 måneder: et stop låser tabet, før aktien kommer igen. Testen er påvirket af overlevelsesbias (aktier, der styrtede helt og forsvandt fra indekset, mangler), og det taler for stoppet. Så et stop kan stadig give mening som nødbremse langt fra kursen eller på en enkelt stor position, men som fast salgsregel på en spredt momentumkurv har det ikke betalt sig.

### Average true range

**True range** for en dag er det største af tre spænd: dagens høj minus lav, høj minus gårsdagens lukkekurs, og gårsdagens lukkekurs minus lav (i absolut værdi). Det fanger også kurshop over natten:

$$
TR_t = \max\left(H_t - L_t,\; |H_t - C_{t-1}|,\; |L_t - C_{t-1}|\right)
$$

**ATR** (Wilder, 1978) er et udglattet gennemsnit af true range over $n$ dage, med Wilders udglatning (et eksponentielt gennemsnit med $\alpha = 1/n$):

$$
ATR_t = ATR_{t-1} + \frac{1}{n}\left(TR_t - ATR_{t-1}\right)
$$

ATR er udtrykt i kroner (eller aktiens valuta), ikke procent. Det er det typiske daglige kursudsving og dermed et naturligt mål for, hvor meget støj et stop skal tåle. Se også [Tekniske indikatorer](laerebog/tekniske-indikatorer).

### ATR-stop og chandelier-stop

Et **chandelier-stop** (lysekronestop, populariseret af Chuck LeBeau) hænger fra den højeste kurs siden indgang:

$$
\text{Stop}_t = \max_{s \le t} C_s - k \cdot ATR_t
$$

Når kursen sætter nye toppe, rykker stoppet op. Falder kursen, bliver stoppet liggende (eller rykker kun lidt, hvis ATR ændrer sig). Parameteren $k$ bestemmer bredden: typisk 2–4. Et lavt $k$ giver et tæt stop, der låser gevinster tidligt men ofte rammes af støj; et højt $k$ giver plads til trenden men tillader større tilbagefald.

En naturlig udvidelse er at lade $k$ afhænge af omstændighederne: mere plads, når trenden er stærk, mindre når den svækkes, når kursen er strakt langt over sit gennemsnit, eller når markedet som helhed er i risk-off.

### Take-profit og reward/risk

Hvis afstanden fra indgang til stop er én risikoenhed $R$, er et kursmål på $2R$ over indgang en reward/risk på 2:1. Med en sandsynlighed $p$ for at nå målet før stoppet er det forventede udfald pr. handel cirka

$$
E = p\cdot b\cdot R - (1 - p)\cdot R
$$

hvor $b$ er reward/risk. Med $b = 2$ er handlen positiv i forventning, så snart $p > 1/3$. Det er logikken bag at kræve en vis reward/risk. Men $p$ er ukendt og afhænger af målet: et fjernt mål nås sjældnere.

Analytikernes kursmål kan bruges som en ekstern ankring: når kursen er over gennemsnittet af analytikernes mål, er meget af den forventede opside allerede i prisen (se [Estimatrevisioner](laerebog/estimatrevisioner)).

### Positionsstørrelse efter risiko

**Fast brøkdel** (*fixed fractional*) bestemmer størrelsen, så et stop koster en fast andel af porteføljen, fx 1 %:

$$
\text{andel} = \frac{\text{risikobudget}}{\text{afstand til stop}}
$$

Med et budget på 1 % og et stop 8 % under kursen bliver positionen $1\,\% / 8\,\% = 12.5\,\%$ af porteføljen. Med et stop 20 % under bliver den 5 %. Volatile aktier får automatisk mindre vægt. Metoden bygger på, at stoppet faktisk holder; kurshop (gap) over stoppet giver et større tab.

### Kelly-kriteriet

Kelly (1956) fandt den andel, der maksimerer formuens langsigtede vækstrate. For et spil med gevinstsandsynlighed $p$ og odds $b$:

$$
f^* = p - \frac{1 - p}{b}
$$

For et aktiv med forventet merafkast $\mu$ og varians $\sigma^2$ er den kontinuerte version $f^* = \mu / \sigma^2$. Thorp (2006) beskriver anvendelsen på aktier. Kelly er teoretisk elegant men praktisk farlig: $\mu$ kendes ikke, og fejlskøn giver alt for store positioner med voldsomme drawdowns. Mange bruger derfor halv Kelly eller mindre. For en privat investor er Kelly mest nyttig som en øvre grænse: overstiger din position Kelly-andelen, tager du mere risiko end selv en optimist burde.

## Sådan gør radaren

Niveauerne beregnes i `signals/levels.py` for dine beholdninger af aktier og sektor- og tema-ETF'er (brede indeksfonde får ingen). Reglen har to tilstande (`stops.mode`):

- **trend** (standard): niveauet er aktiens {{settings:stops.trend_sma}}-dages gennemsnit, og der er intet kursmål. En lukkekurs under gennemsnittet er en anledning til at gennemgå positionen, ikke en salgsordre (`stops.action: review`). Det er resultatet af radarens egen test (se [Virker stop på momentumaktier?](#virker-stop-på-momentumaktier)): salg under 200-dages gennemsnittet var den eneste exit, der kostede lidt afkast, og kursmålet kostede mest. Niveauet hedder *Review* på [My holdings](/me) og *Review level (rule)* på tickerprofilen.
- **atr**: det glidende ATR-stop og kursmålet, som beskrevet i resten af dette afsnit. Sådan var reglen indtil oktober 2026, og sådan bruges den stadig i simuleringerne af varianter (`radar sim exits --rule-spec atr-tp`).

I ATR-tilstanden står hver justering af $k$ som en grund med sin effekt. Begge er mekaniske regler til disciplin og opfølgning, ikke anbefalinger.

### Gennemgangsniveauet

Niveauet er det simple gennemsnit af de seneste {{settings:stops.trend_sma}} lukkekurser (justerede for udbytte). Har aktien kortere historik, er der intet niveau. *below review level* betyder, at den seneste lukkekurs er under gennemsnittet; *near review level*, at den er inden for {{settings:stops.near_atr}} ATR af det. Risikobudgettet (se nedenfor) regnes med afstanden til niveauet, og da et 200-dages gennemsnit typisk ligger 10–30 % under en momentumaktie, giver det en mindre position end et tæt stop.

### ATR

ATR beregnes med Wilders udglatning over {{settings:stops.atr_days}} handelsdage (`stops.atr_days`) på aktiens daglige høj, lav og lukkekurs.

### Anker

Ankeret er den højeste lukkekurs siden din første handel i positionen. For en ticker, du ikke ejer (fx i `radar info`), bruges den højeste lukkekurs over de seneste {{settings:stops.info_anchor_days}} handelsdage (`stops.info_anchor_days`).

Radaren går desuden stoppet igennem fra indgangen og frem. Hver gang en lukkekurs har ligget på eller under stoppet, er det et brud; stoppet starter så forfra fra den følgende dag, og ankeret bliver den højeste lukkekurs siden det seneste brud. Et brud inden for den seneste måned (21 handelsdage, fast i koden) vises som et flag.

### Stopbredden k

$k$ starter på {{settings:stops.k_base}} (`stops.k_base`). Hvert signal flytter det med ét trin på {{settings:stops.k_step}} (`stops.k_step`) eller et halvt trin:

| Signal (i appen) | Betingelse | Effekt på k |
|---|---|---|
| *Strong momentum* | trenden er intakt (50-dages over et stigende 200-dages gennemsnit) og momentumscore ≥ {{settings:stops.strong_score}} | + 1 trin |
| *Trend broken* | kursen under 200-dages gennemsnittet | − 1 trin |
| *Losing momentum* | kursen under 50-dages gennemsnittet og negativt 1-måneds afkast | − 1 trin |
| *Extended* | kursen mere end {{settings:stops.extended_vs_sma50|pct}} over 50-dages gennemsnittet | − 1 trin |
| *Macro regime* | regimet er *Risk-off* | − 1 trin |
| *Macro regime* | regimet er blandet (*Mixed*) | − ½ trin |
| *Above all analyst targets* | kursen over analytikernes højeste kursmål | − 1 trin |
| *Above analyst target* | ellers: kursen over analytikernes gennemsnitlige kursmål | − 1 trin |
| *Targets being cut* | gennemsnitligt kursmål sænket mere end {{settings:stops.target_cut|pct}} på 30 dage | − ½ trin |
| *Targets being raised* | hævet mere end {{settings:stops.target_cut|pct}} | kun en note |
| *Rotation* | rotationsgrafens kvadrant mod ACWI er svækkes eller halter | kun en note |

De to analytikerregler udelukker hinanden: over det højeste mål tæller kun den første. Analytikerdata bruges kun med mindst {{settings:stops.min_analysts}} analytikere (`stops.min_analysts`) og når konsensus højst er {{settings:coverage.max_age.analyst}} dage gammel. Momentumscoren er forklaret i [Radarens momentumscore](laerebog/momentumscore), trenden i [Glidende gennemsnit og trend](laerebog/trend) og regimet i [Radarens afstemningsmodel](laerebog/afstemningsmodellen).

Til sidst begrænses $k$ til intervallet fra {{settings:stops.k_min}} til {{settings:stops.k_max}} (`stops.k_min`, `stops.k_max`). Stoppet er så:

$$
\text{Stop} = \text{anker} - k\cdot ATR \qquad k \in [{{settings:stops.k_min|raw}},\, {{settings:stops.k_max|raw}}]
$$

Ligger 200-dages gennemsnittet mellem kursen og stoppet, tilføjes en note: et brud dér er et tidligere varsel.

### Take-profit

Radaren finder to kandidater og tager den laveste:

1. Kursen plus {{settings:stops.reward_risk}} gange stopbredden: $\text{kurs} + {{settings:stops.reward_risk|raw}}\cdot k \cdot ATR$ (`stops.reward_risk`). Risikoenheden er hele stopbredden $k \cdot ATR$, ikke afstanden fra kursen til stoppet, så målet ikke skrumper, når kursen nærmer sig stoppet.
2. Analytikernes gennemsnitlige kursmål, hvis det ligger over kursen.

Ligger kursen over analytikernes højeste mål, er der intet kursmål: der er ingen ekstern støtte til yderligere opside.

### Flag

- *stop hit*: kursen er på eller under stoppet.
- *near stop*: kursen er mindre end {{settings:stops.near_atr}} ATR over stoppet (`stops.near_atr`).
- *near target*: kursmålet er mindre end {{settings:stops.near_atr}} ATR væk.

### Risikobudget

Risikokortet viser *Size at … risk*: den andel af porteføljen, hvor et fald til stoppet koster {{settings:risk.budget|pct}} af porteføljen (`risk.budget`):

$$
\text{andel} = \frac{{{settings:risk.budget|raw}}}{-\left(\text{Stop}/\text{kurs} - 1\right)}
$$

Er andelen over 100 %, ligger stoppet så tæt, at reglen ikke kan begrænse risikoen meningsfuldt, og appen skriver det. Radaren beregner ikke Kelly.

### Backtest af reglen

`radar sim exits` afspiller dine egne handler med reglen fulgt dag for dag (`backtest/`). Inputtene til $k$ er dem, der var kendt den dag: kurser til og med dagen, momentumscoren mod universet den dag, regimet fra ugens sidste lukkekurs med forsinkelse på makrodata og analytikerkonsensus hentet senest den dag. Take-profit låses ved købet, fordi kursmålet regnes fra den aktuelle kurs og ellers aldrig ville blive nået. Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering).

### Pengene fra et salg

Et salg er kun halvdelen af en beslutning. Den anden halvdel er, hvor pengene går hen. Momentum er en relativ effekt: de bedste aktier de seneste 3–12 måneder har i gennemsnit klaret sig bedre end de andre det næste stykke tid. En take-profit, der sælger en vinder og lægger pengene i ACWI, flytter dem altså fra den gruppe, momentum peger på, til gennemsnittet. Så skal take-profit enten undgå de fald, der kommer efter en stor stigning, eller også koster den afkast. Flyttes pengene i stedet til den næste aktie med høj score, bliver take-profit en måde at holde kurven fuld af aktier med stærk momentum, og spørgsmålet bliver, om det slår at lade vinderen løbe.

Den rene version af den idé er en rotation: hver måned sælges de aktier, der er faldet langt ned på listen, og de bedste købes. Det er den klassiske momentumstrategi fra litteraturen (Jegadeesh og Titman 1993), og den har ingen stop. Skal et stop eller en take-profit tilføje noget, skal de altså slå rotationen alene, ikke bare det at beholde kurven.

`radar study redeploy` tester begge dele med samme kurve: reglen med pengene parkeret, reglen med pengene i en ny aktie, rotationen alene og rotationen med reglen. Bedømmelsen sker på risikojusteret afkast:

$$
\text{Sharpe} = \frac{\bar r - \bar r_f}{\sigma_r}\sqrt{252}, \qquad
\text{Sortino} = \frac{\bar r - \bar r_f}{\sqrt{\tfrac{1}{n}\sum \min(r_t - r_{f,t}, 0)^2}}\sqrt{252}, \qquad
\text{IR} = \frac{\overline{r - r_b}}{\sigma_{r - r_b}}\sqrt{252}
$$

med daglige afkast $r$ i DKK, ECB's indlånsrente som $r_f$ (kronen følger euroen) og ACWI i DKK som $r_b$. Calmar er det årlige afkast divideret med det største fald. Over vinduer på 6 eller 12 måneder er tallene støjfyldte; de skal sammenlignes mellem varianterne på de samme datoer, ikke med langsigtede tal. To ting trækker resultatet i hver sin retning: at flytte pengene koster kurtage og, i frie midler, skat ved hvert salg; og universet er dagens, så de aktier, pengene flyttes til, er nogle, der overlevede. Det sidste får rotation til at se bedre ud, end den var.

### Regnskaber og kursgab

Et regnskab offentliggøres som regel før åbning eller efter lukning. Kursen reagerer derfor i ét spring fra den ene lukkekurs til den næste åbning, og et stop, der ligger 5 % under kursen, beskytter ikke mod et fald på 15 % fra den ene dag til den næste: ordren udløses på åbningskursen, langt under stoppet. Risikobudgettet ovenfor forudsætter, at stoppet kan eksekveres tæt på niveauet. Det gør det ikke hen over et regnskab.

Det, du selv styrer før et regnskab, er altså to ting:

- **Positionens størrelse**: hvor meget af porteføljen der står på spil, hvis kursen springer.
- **Afstanden til gennemgangsniveauet**: ligger kursen tæt på, kan selv en almindelig reaktion føre den forbi.

Det er netop to af de grunde, [kalenderen](brugervejledning/kalender#fremhævningsreglerne) fremhæver et kommende regnskab med: en beholdning på mindst {{settings:calendar.highlight.big_position|pct}} af porteføljen og en kurs inden for {{settings:calendar.highlight.near_level|pct}} af gennemgangsniveauet. Kalenderen siger ikke, hvad du skal gøre; den viser, hvor et kursgab ville betyde mest.

## Regneeksempel

Eksemplet bruger ATR-tilstanden (`stops.mode: atr`, $k$ starter på 3, trin 0,5, budget 1 %, reward/risk 2); standarden er i dag gennemgangsniveauet ved 200-dages gennemsnittet.

Du købte en aktie for nogle måneder siden. Siden da er den højeste lukkekurs 250 kr. I dag:

- Kurs 240 kr., 50-dages gennemsnit 225 kr., over 200-dages gennemsnittet, trenden intakt.
- Momentumscore 85, ATR(14) = 8 kr.
- Regimet er blandet (*Mixed*).
- 12 analytikere, gennemsnitligt kursmål 270 kr., højeste 300 kr., ingen større ændring på 30 dage.

**Justeringer.** *Strong momentum* (+0,5). *Extended*? $240/225 - 1 = 6.7\,\%$, under 25 %, så nej. *Macro regime*, blandet (−0,25). Kursen er under både gennemsnits- og højeste mål. Altså $k = 3 + 0.5 - 0.25 = 3.25$, inden for [1,5; 3,5].

**Stop.** $250 - 3.25 \cdot 8 = 250 - 26 = 224$ kr. Det er $224/240 - 1 = -6.67\,\%$ under kursen.

**Take-profit.** Kandidat 1: $240 + 2 \cdot 3.25 \cdot 8 = 240 + 52 = 292$ kr. Kandidat 2: analytikernes 270 kr. Den laveste er 270 kr. (+12,5 %).

**Flag.** Afstanden til stoppet er 16 kr., dvs. 2 ATR, så ikke *near stop*. Afstanden til målet er 30 kr., heller ikke *near target*.

**Størrelse.** $1\,\% / 6.67\,\% = 15\,\%$ af porteføljen. Med en portefølje på 400.000 kr. er det 60.000 kr., eller 250 aktier á 240 kr. Rammer kursen stoppet, er tabet $250 \cdot 16 = 4.000$ kr., præcis 1 % af porteføljen (hvis der ikke er et kurshop forbi stoppet).

**Et andet scenarie.** Tre måneder senere er kursen steget til 320 kr. (ny top), 50-dages gennemsnittet er 250 kr., regimet er skiftet til *Risk-off*, og analytikerne har sænket gennemsnitsmålet med 7 %, mens kursen nu er over det højeste mål. Momentumscoren er stadig 85. Så: +0,5 (*Strong momentum*), −0,5 (*Extended*: $320/250 - 1 = 28\,\%$), −0,5 (*Risk-off*), −0,5 (*Above all analyst targets*), −0,25 (*Targets being cut*): $k = 3 + 0.5 - 0.5 - 0.5 - 0.5 - 0.25 = 1.75$. Med ATR 10 kr. er stoppet $320 - 17.5 = 302.5$ kr. Og der er intet kursmål, fordi kursen er over det højeste analytikermål. Reglen siger altså: gevinsten er stor, omgivelserne er blevet mere usikre, stram stoppet.

**Kelly til sammenligning.** Tror du, at aktien har 55 % chance for at nå 2R før −1R, giver Kelly $f^* = 0.55 - 0.45/2 = 0.325$, altså 32,5 % af formuen på én idé. Det viser, hvor aggressiv fuld Kelly er, selv med en beskeden fordel, og hvor følsom den er: ved 45 % chance er $f^* = 0.45 - 0.55/2 = 0.175$.

## Faldgruber og begrænsninger

- **Kurshop.** Et stop er ikke en garanti. Efter et regnskab eller over en weekend kan aktien åbne langt under stoppet. Risikobudgettet holder kun, hvis stoppet kan eksekveres tæt på niveauet. Se [Regnskaber og kursgab](#regnskaber-og-kursgab).
- **Støj og whipsaw.** Et for tæt stop rammes af almindelige udsving. Det er grunden til volatilitetsskalering og til, at $k$ har en nedre grænse.
- **Dagslukkekurser.** Radaren regner på lukkekurser; et stop-ordre hos en mægler udløses ofte på intradagkurs. De to kan give forskellige resultater på volatile dage.
- **Valuta.** Stop og ATR er i aktiens egen valuta. Et fald i dollaren ændrer dit tab i kroner, men ikke stoppet.
- **Skat og omkostninger.** Hver handel koster kurtage og spread, og i frie midler udløser et salg beskatning af en gevinst (se [Dansk skat for investorer](laerebog/skat)). Et stop, der ofte rammes, kan være dyrt.
- **Analytikermål er ikke sandhed.** De halter efter kursen og er ofte for optimistiske. Radaren bruger dem kun som en ekstern ankring og kun med mindst {{settings:stops.min_analysts}} analytikere.
- **Backtests snyder let.** En test, der bruger data, som først blev kendt senere (look-ahead), eller kun aktier, der stadig findes (overlevelsesbias), ser bedre ud, end reglen var. Radarens backtest skærer hvert input ved dagen, men aktieuniverset er dagens liste, og makrodata er de reviderede tal.
- **Stop på en spredt kurv.** På en kurv af momentumaktier har en fast stopregel i radarens egen test kostet mere afkast end den samme risikoreduktion opnået ved at lægge en del i et bredt indeks (se [Virker stop på momentumaktier?](laerebog/stop-og-storrelse#virker-stop-på-momentumaktier)).
- **Det er en regel, ikke et råd.** Radaren foreslår ingen handel. Stoppet er et niveau, hvor din tese bør genovervejes, gerne skrevet ned på forhånd i din [beslutningsjournal](laerebog/adfaerd).

## Videre læsning

- J. Welles Wilder, *New Concepts in Technical Trading Systems*, Trend Research, 1978.
- Kathryn M. Kaminski og Andrew W. Lo, "When Do Stop-Loss Rules Stop Losses?", *Journal of Financial Markets* 18, 2014.
- Andrew W. Lo og Alexander Remorov, "Stop-Loss Strategies with Serial Correlation, Regime Switching, and Transaction Costs", *Journal of Financial Markets* 34, 2017.
- Yufeng Han, Guofu Zhou og Yingzi Zhu, "Taming Momentum Crashes: A Simple Stop-Loss Strategy", arbejdspapir, SSRN, 2016.
- John L. Kelly Jr., "A New Interpretation of Information Rate", *Bell System Technical Journal* 35(4), 1956.
- Edward O. Thorp, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market", i *Handbook of Asset and Liability Management*, bind 1, Elsevier, 2006.
