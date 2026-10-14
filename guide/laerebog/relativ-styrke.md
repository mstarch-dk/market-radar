# Relativ styrke

## Intuition

Et afkast på 8 % på tre måneder lyder godt, men det siger ikke ret meget alene. Steg hele verdensmarkedet 10 % i samme periode, har du faktisk tabt terræn. Steg det 2 %, har du klaret dig markant bedre end alternativet. Relativ styrke er netop det spørgsmål: *hvordan har noget klaret sig i forhold til et alternativ, du lige så godt kunne have ejet?*

For en dansk investor, der sammenligner med MSCI ACWI, er alternativet konkret: en billig globalindeksfond. Hver sektor, region, tema eller faktor, radaren følger, måles derfor mod ACWI. Er Europas banker stærkere end verdensindekset? Taber forsyningssektoren terræn? Det er relativ styrke, og den er byggestenen i hele rotationsdelen af radaren, herunder [rotationsgrafen](laerebog/rrg).

Relativ styrke er ikke det samme som "går op". En defensiv sektor kan have positiv relativ styrke i et faldende marked, fordi den falder mindre. Og en sektor kan stige kraftigt og alligevel have negativ relativ styrke, hvis markedet stiger endnu mere. Det er pointen: rotation handler om, *hvor* pengene hellere vil være, ikke om markedet som helhed stiger eller falder.

## Teori

### RS-linjen: en kursratio

Den klassiske definition er en simpel ratio mellem to kurser. Lad $P_i(t)$ være kursen på aktiv $i$ (fx en sektor-ETF) og $P_b(t)$ kursen på benchmark (ACWI) på dag $t$:

$$
RS_i(t) = \frac{P_i(t)}{P_b(t)}
$$

Niveauet af $RS$ betyder ingenting i sig selv; det afhænger af, hvad de to kurser tilfældigvis står i. Det er *retningen*, der tæller. Stiger $RS$, har aktivet slået benchmark i perioden; falder den, har det tabt. Tegner du $RS$ som en graf over tid (RS-linjen), kan du læse den præcis som en kursgraf: trend, toppe, bunde, gennembrud. Det er derfor, den relative styrke også kan analyseres med de samme værktøjer som i [Glidende gennemsnit og trend](laerebog/trend).

### Normalisering

For at kunne sammenligne flere RS-linjer i samme graf normaliseres de. Den mest almindelige måde er at rebasere til 100 på en startdato $t_0$:

$$
RS^{*}_i(t) = 100 \cdot \frac{RS_i(t)}{RS_i(t_0)} = 100 \cdot \frac{P_i(t)/P_i(t_0)}{P_b(t)/P_b(t_0)}
$$

Nu betyder 105, at aktivet har klaret sig 5 % bedre end benchmark siden $t_0$, uanset kursniveauerne. Valget af $t_0$ påvirker billedet: starter du lige efter et stort fald i aktivet, ser det stærkt ud bagefter.

Et alternativ er at normalisere mod et glidende gennemsnit af RS-linjen selv i stedet for mod et fast startpunkt. Så måler tallet, om den relative styrke er over eller under sit eget nylige niveau. Det er princippet bag [RS-Ratio i rotationsgrafen](laerebog/rrg#rs-ratio).

### Relativt afkast: ratio eller differens

Ændringen i RS-linjen over $n$ dage er det *eksakte* relative afkast:

$$
\frac{RS_i(t)}{RS_i(t-n)} - 1 = \frac{1 + r_i}{1 + r_b} - 1
$$

hvor $r_i$ og $r_b$ er de almindelige afkast over perioden. I praksis bruger man ofte den simplere *differens*:

$$
r^{\text{rel}}_i = r_i - r_b
$$

målt i procentpoint. De to er næsten ens, når afkastene er små, men differensen overvurderer forskellen en smule, når benchmark er steget (og undervurderer den, når benchmark er faldet), fordi den ignorerer, at et afkast i et stigende marked er "billigere". Med logaritmiske afkast forsvinder forskellen: $\ln(1+r_i) - \ln(1+r_b) = \ln\big(RS_i(t)/RS_i(t-n)\big)$. Se [Afkast og renters rente](laerebog/afkast) for logaritmiske afkast og [Benchmark og relativt afkast](laerebog/benchmark) for valget af benchmark.

### Relativ og absolut momentum

Momentumforskningen skelner mellem to spørgsmål:

| | Spørgsmål | Sammenligning |
|---|---|---|
| **Relativ momentum** (tværsnit) | Hvilke aktiver er stærkest *i forhold til hinanden*? | Rangering inden for en gruppe |
| **Absolut momentum** (tidsserie) | Stiger aktivet overhovedet? | Aktivets eget afkast mod nul eller den risikofrie rente |

Jegadeesh og Titman (1993) dokumenterede relativ momentum i aktier: vindere over 3–12 måneder har en tendens til at fortsætte med at slå tabere i de følgende måneder. Moskowitz og Grinblatt (1999) viste, at en stor del af effekten findes på *brancheniveau*, hvilket er præcis det niveau, sektorrotation arbejder på. Moskowitz, Ooi og Pedersen (2012) dokumenterede absolut momentum (time-series momentum) på tværs af aktivklasser. Antonacci (2014) populariserede kombinationen: vælg det relativt stærkeste aktiv, men kun hvis det også har positiv absolut momentum. Ellers er kontanter eller obligationer alternativet.

Pointen for dig: relativ styrke fortæller, *hvad* der er stærkest, men ikke om det er en god idé at være i aktiemarkedet. Den stærkeste sektor i et bjørnemarked falder ofte stadig. Derfor viser radaren begge dele, og derfor findes [regimet](laerebog/risk-on-risk-off) som en separat vurdering. Den bredere evidens for momentum er beskrevet i [Momentumeffekten](laerebog/momentumeffekten).

### Flere horisonter

Relativ styrke over én måned er støjfyldt og påvirket af kortsigtet tilbagevenden (reversal): det, der steg mest sidste måned, falder ofte lidt tilbage. Relativ styrke over 6–12 måneder er mere robust, men reagerer langsomt. En udbredt løsning er at vægte flere horisonter sammen, så et signal kræver bekræftelse fra mere end én tidsskala. Faber (2010) viser, at simple rangeringer af sektorer efter en blanding af 1-, 3-, 6- og 12-måneders afkast har givet en overvægt mod de stærke sektorer, der historisk har betalt sig, men med store perioder, hvor strategien halter.

## Sådan gør radaren

Radaren beregner relativ styrke for alle ETF'er i `config/universe.yaml` (`etf_groups`: amerikanske sektorer, europæiske sektorer, regioner og lande, temaer, faktorer) i funktionen `relative_table` i `src/radar/signals/rotation.py`.

**Data.** Udbyttejusterede dagslukkekurser fra Yahoo (se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser)), i noteringsvalutaen. Benchmark er ACWI (US-noteret). En ETF skal have mindst 130 lukkekurser, ellers udelades den af tabellen (grænsen ligger i koden).

**Relative afkast.** For tre horisonter, målt i handelsdage (bars):

| Kolonne | Horisont | Beregning |
|---|---|---|
| *Rel 1m* | 21 dage | $r_i - r_b$ over 21 dage |
| *Rel 3m* | 63 dage | $r_i - r_b$ over 63 dage |
| *Rel 6m* | 126 dage | $r_i - r_b$ over 126 dage |

Radaren bruger altså **differensen** $r_i - r_b$ i procentpoint, ikke ratioen. Benchmarkens serie skæres af på ETF'ens sidste dato, så en ETF, der er holdt op med at opdatere, ikke måles mod nyere benchmarkgevinster. Dagene tælles i radarens fælles datogitter: alle handelsdage på tværs af børserne, hvor en børs' helligdage udfyldes med seneste kurs (højst 5 dage frem).

**Score og rang.** De tre relative afkast vægtes sammen til en samlet score:

$$
\text{rs\_score} = 0.2 \cdot \text{rel}_{1m} + 0.4 \cdot \text{rel}_{3m} + 0.4 \cdot \text{rel}_{6m}
$$

Vægtene ligger fast i koden og favoriserer 3–6 måneder, som passer til radarens horisont på 1–6 måneder og dæmper støjen fra den seneste måned. Scoren rangeres *inden for hver gruppe* (kolonnen *#*, hvor 1 er stærkest), så en amerikansk sektor kun konkurrerer med andre amerikanske sektorer. Kolonnen *Δ rank* viser ændringen i rang siden et tidligere snapshot, der er mindst {{settings:snapshot_min_gap_days}} dage gammelt.

**Absolut momentum ved siden af.** Tabellen viser også *Abs 3m* (det almindelige 3-måneders afkast) og *>200d* (om kursen ligger over sit 200-dages gennemsnit). Det er de absolutte tal, der svarer på "stiger det overhovedet?".

Du ser det hele på [Sektorrotation](/rotation) og [Temaer og faktorer](/themes); se også [brugervejledningen til sektorrotation](brugervejledning/sektorrotation).

## Regneeksempel

To ETF'er, X og Y, i samme gruppe. Kurserne for X og ACWI:

| | 126 dage siden | 63 dage siden | 21 dage siden | I dag |
|---|---|---|---|---|
| X | 50,00 | 52,00 | 55,00 | 56,10 |
| ACWI | 100,00 | 104,00 | 106,00 | 107,06 |

**Afkast for X:** 1m: 56,10/55,00 − 1 = 2,00 %. 3m: 56,10/52,00 − 1 = 7,88 %. 6m: 56,10/50,00 − 1 = 12,20 %.

**Afkast for ACWI:** 1m: 107,06/106,00 − 1 = 1,00 %. 3m: 107,06/104,00 − 1 = 2,94 %. 6m: 107,06/100,00 − 1 = 7,06 %.

**Relative afkast (differens):** 1m: 1,00 pp. 3m: 7,88 − 2,94 = 4,94 pp. 6m: 12,20 − 7,06 = 5,14 pp.

**Score for X:**

$$
0.2 \cdot 1.00 + 0.4 \cdot 4.94 + 0.4 \cdot 5.14 = 0.200 + 1.976 + 2.056 = 4.23
$$

Y har haft en stærkere måned, men svagere 3 og 6 måneder: relative afkast på 3,0, 1,0 og 2,0 pp. Score: 0,2 · 3,0 + 0,4 · 1,0 + 0,4 · 2,0 = 0,6 + 0,4 + 0,8 = 1,80. X rangeres over Y, selv om Y har vundet den seneste måned. Det er vægtningen, der virker som tilsigtet.

**Ratio mod differens.** RS-linjen for X var 50/100 = 0,5000 for 126 dage siden og er 56,10/107,06 = 0,5240 i dag. Det eksakte relative afkast er

$$
\frac{0.5240}{0.5000} - 1 = \frac{1.1220}{1.0706} - 1 = 4.80\ \%
$$

mens differensen gav 5,14 pp. Forskellen på 0,34 pp skyldes, at ACWI steg 7 % i perioden. Logaritmisk: ln 1,1220 − ln 1,0706 = 0,1151 − 0,0682 = 0,0469, og exp(0,0469) − 1 = 4,80 %, som ratioen. Til rangering betyder forskellen sjældent noget, fordi alle i gruppen måles mod samme benchmark i samme periode, men du skal ikke læse *Rel 6m* som et præcist merafkast.

## Faldgruber og begrænsninger

- **Relativ styrke er ikke købssignal.** En sektor, der falder 5 %, mens markedet falder 12 %, har stærk relativ styrke, men du taber stadig penge. Se altid *Abs 3m*, *>200d* og [regimet](laerebog/risk-on-risk-off) ved siden af.
- **Valutaen er indbygget.** ETF'er noteret i euro måles mod en dollarnoteret ACWI uden valutaomregning. En stærkere euro får europæiske ETF'er til at se relativt svagere ud i deres egen valuta, end de er for en dollarinvestor, og omvendt. Den hjemlige sammenligning (europæiske sektorer mod STOXX 600, se [rotationsgrafen](laerebog/rrg)) fjerner det problem for Europa.
- **Differensen er en tilnærmelse.** Som regneeksemplet viser, afviger $r_i - r_b$ fra det eksakte relative afkast, når benchmark har bevæget sig meget.
- **Forskellige kalendere.** Børserne har forskellige helligdage. Radaren lægger alle kurser i ét fælles datogitter og udfylder helligdage med seneste kurs, så "21 dage" er samme periode for ETF og benchmark. Prisen er, at en helligdag tæller som en dag uden kursbevægelse, og at en bevægelse, der sker på en dag, hvor den ene børs er lukket, først ses dagen efter. Effekten er lille.
- **Rangering inden for små grupper.** I en gruppe med 8 faktor-ETF'er er rang 1 og rang 3 måske kun 0,5 pp fra hinanden. Se på selve scoren og de relative afkast, ikke kun rangen.
- **Momentumkrak.** Relativ momentum kan vende brat, især efter store markedsfald, hvor de hårdest ramte sektorer ofte fører i opsvinget (Daniel og Moskowitz, 2016). En rangering bygget på 6 måneder reagerer sent på sådan et skift.
- **Overlap.** Mange temaer og sektorer deler beholdninger (fx halvledere, software og teknologi). Tre "stærke" ETF'er kan være én og samme satsning.

## Videre læsning

- Jegadeesh, N. og Titman, S. (1993): "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency", *Journal of Finance* 48(1).
- Moskowitz, T. J. og Grinblatt, M. (1999): "Do Industries Explain Momentum?", *Journal of Finance* 54(4).
- Moskowitz, T. J., Ooi, Y. H. og Pedersen, L. H. (2012): "Time Series Momentum", *Journal of Financial Economics* 104(2).
- Antonacci, G. (2014): *Dual Momentum Investing*, McGraw-Hill.
- Faber, M. (2010): "Relative Strength Strategies for Investing", arbejdspapir, SSRN.
- Daniel, K. og Moskowitz, T. J. (2016): "Momentum Crashes", *Journal of Financial Economics* 122(2).
