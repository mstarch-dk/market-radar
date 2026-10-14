# Markedsbredde

## Intuition

Et aktieindeks som S&P 500 er vægtet efter markedsværdi. De ti største selskaber udgør en tredjedel af indekset eller mere, så indekset kan stige, selv om de fleste aktier falder. Indekset fortæller dig, hvordan *de store* har det. Markedsbredden fortæller dig, hvordan *den typiske aktie* har det.

Tænk på en hær: hvis generalerne marcherer fremad, men soldaterne trækker sig tilbage, holder fremrykningen ikke længe. Et sundt opadgående marked har bred deltagelse: mange aktier i optrend, mange nye højder, få nye bunde. Et marked, hvor indekset stiger på skuldrene af få giganter, er mere sårbart: hvis de få vender, er der intet at falde tilbage på.

Markedsbredde er derfor et af de ældste værktøjer i teknisk analyse, og det er en af grundpillerne i radarens risk-on/risk-off-afstemning.

## Teori

### Andel over 200-dages gennemsnittet

Det mest udbredte mål er andelen af aktierne i et univers, der handles over deres eget 200-dages glidende gennemsnit:

$$
B_t = 100 \cdot \frac{\#\{i : P_{i,t} > \overline{P}^{(200)}_{i,t}\}}{\#\{i : \overline{P}^{(200)}_{i,t} \text{ findes}\}}
$$

hvor $\overline{P}^{(200)}_{i,t}$ er gennemsnittet af aktie $i$'s seneste 200 lukkekurser. 200-dages gennemsnittet er en gængs grænse for den langsigtede trend (se [Glidende gennemsnit og trend](laerebog/trend)), så $B_t$ svarer på spørgsmålet: *hvor stor en del af aktierne er i langsigtet optrend?*

Tommelfingerregler: over 60–70 % er bredt sundt, under 30–40 % er bredt svagt, og under 10–20 % ses kun i kraftige udsalg (som marts 2020), hvor det historisk ofte har været tæt på en bund. Andelen over 50-dages gennemsnittet bevæger sig hurtigere og bruges til den kortsigtede tilstand.

### Nye højder minus nye bunde

Et andet klassisk mål tæller aktier ved ekstremer: hvor mange lukker på deres højeste kurs i 52 uger (nye højder), og hvor mange på deres laveste (nye bunde)?

$$
NH_t = 100 \cdot \frac{H_t - L_t}{N_t}
$$

hvor $H_t$ og $L_t$ er antallet af aktier på 52-ugers højde og bund, og $N_t$ antallet af aktier med et års historik. Positive værdier betyder, at flere aktier sætter nye højder end nye bunde. Målet svinger meget fra dag til dag og udglattes derfor typisk med et glidende gennemsnit.

Nye højder og bunde fanger ekstremerne: et marked kan have mange aktier over 200-dages gennemsnittet, men samtidig et stigende antal nye bunde, hvilket er et tidligt tegn på, at deltagelsen svækkes.

### Advance-decline-linjen og andre mål

Det ældste breddemål er *advance-decline-linjen* (A/D-linjen): hver dag tælles antallet af aktier, der steg ($A_t$), og antallet, der faldt ($D_t$), og forskellen lægges til en løbende sum:

$$
AD_t = AD_{t-1} + (A_t - D_t)
$$

Linjens niveau er uden betydning; det er retningen og sammenligningen med indekset, der tæller. Stiger indekset, mens A/D-linjen falder, deltager færre og færre aktier. Afledte mål som McClellan-oscillatoren (forskellen mellem et hurtigt og et langsomt eksponentielt gennemsnit af $A_t - D_t$) bruges til at måle det kortsigtede momentum i bredden.

A/D-målene kræver data for alle aktier på en børs hver dag og er følsomme over for, hvad der tælles med (fx preferenceaktier og obligationsfonde på NYSE). Andelen over 200-dages gennemsnittet og nettonye højder kan derimod beregnes direkte fra kurshistorikken for en fast liste af aktier. Det er derfor, radaren bruger dem.

Fælles for alle breddemål er, at de giver hver aktie *én stemme*, uanset størrelse. De svarer på et andet spørgsmål end indekset, og det er netop deres værdi: når de to er enige, er trenden bredt funderet; når de er uenige, er der noget at undersøge.

### Lige vægt mod markedsværdivægt

En tredje vinkel er at sammenligne det samme indeks med to vægtninger. S&P 500 Equal Weight giver hver af de 500 aktier samme vægt (RSP er den største ETF på det), mens det almindelige indeks (SPY) vægter efter markedsværdi. Ratioen

$$
\frac{P_{\text{RSP}}(t)}{P_{\text{SPY}}(t)}
$$

stiger, når den gennemsnitlige aktie slår indekset (bredere deltagelse), og falder, når de største selskaber trækker indekset (smallere marked). Det er [relativ styrke](laerebog/relativ-styrke) anvendt på vægtningen selv. Bemærk, at RSP også har en systematisk hældning mod mindre og billigere selskaber; ratioen er derfor ikke kun et breddemål, men også en størrelses- og værdifaktor.

### Divergenser

Det mest omtalte breddesignal er divergensen: indekset sætter en ny top, men bredden gør ikke. Færre aktier deltager i den nye top end i den forrige. Klassiske eksempler er 1999–2000 (hvor teknologiaktier bar indekset, mens den gennemsnitlige aktie faldt) og 2007. Divergenser kan dog vare længe: i 2023 slog det markedsværdivægtede S&P 500 det ligevægtede med over 10 procentpoint, drevet af få store teknologiselskaber, uden at det førte til et markedsfald det år.

Den modsatte situation, et *breadth thrust*, er når bredden på få dage går fra meget svag til meget stærk. Zweig (1986) beskrev en variant, der historisk ofte har markeret starten på et nyt opsving.

### Overlevelsesbias

Breddemål kræver en liste over aktier. Bruger man *dagens* indeksmedlemmer til at beregne bredden bagud i tid, opstår overlevelsesbias (survivorship bias): selskaber, der gik konkurs, blev opkøbt eller røg ud af indekset, mangler, og selskaber, der kom ind *fordi* de var steget, er med i perioden, før de kom ind. Historisk bredde ser derfor bedre ud, end den var. Brown, Goetzmann, Ibbotson og Ross (1992) viste, hvordan den slags bias systematisk forvrænger performancemålinger.

Dagens værdi er mindre påvirket (dagens liste er jo den rigtige i dag), men sammenligninger med historikken, fx "bredden er lavere end i 2022", bør tages med forbehold.

## Sådan gør radaren

Funktionerne `breadth_history` og `net_highs_lows` i `src/radar/signals/regime.py` beregner bredden på radarens aktiegrupper (`stock_groups` i `config/universe.yaml`): *US (S&P 500)* fra den officielle SPY-beholdningsfil, *Europe large caps*, *Nordic (C25 + large caps)* og *Asia (semis & leaders)*. De sidste tre er kuraterede lister.

### Bredde pr. region

For **hver gruppe** beregnes andelen af aktier over deres 200-dages gennemsnit, blandt de aktier der har mindst 200 kurser. Hver gruppe er sin egen række i afstemningen:

- **risk-on**, hvis andelen er mindst {{settings:regime.breadth_strong}} %,
- **risk-off**, hvis den er højst {{settings:regime.breadth_weak}} %,
- **neutral** ellers.

Noten ved rækken viser ændringen over den seneste måned (22 handelsdage), andelen over 50-dages gennemsnittet, og hvor mange af gruppens aktier der har kurser. Har ingen aktie 200 dages historik, bliver rækken *n/a*.

### Nettonye højder

Én samlet række for **alle aktier** i alle grupper: andelen, der lukker på en 52-ugers lukkehøjde (252 handelsdage, dagens kurs medregnet), minus andelen på en 52-ugers lukkebund, i procent af de aktier der har 252 dages historik. Serien udglattes med et 10-dages gennemsnit.

- **risk-on**, hvis værdien er mindst +{{settings:regime.highs_lows_band}},
- **risk-off**, hvis den er højst −{{settings:regime.highs_lows_band}},
- **neutral** ellers.

Fordi omkring 500 af aktierne er amerikanske, er rækken i praksis domineret af USA.

### RSP/SPY

Rækken *Equal vs cap weight (RSP/SPY)* viser den procentvise ændring i ratioen RSP/SPY over 63 handelsdage (cirka 3 måneder). Den **stemmer aldrig**: status er altid neutral, uanset værdien. Den informerer kun, med noten "Broadening" (positiv ændring: den gennemsnitlige aktie slår indekset) eller "Narrow" (negativ: de største bærer indekset). Farvegraderingen bruger ±3 %, som ligger fast i koden.

Graferne på [Regime](/regime) viser bredden pr. region med linjer ved {{settings:regime.breadth_weak}} og {{settings:regime.breadth_strong}} % samt nettonye højder med linjer ved ±{{settings:regime.highs_lows_band}}. Se [brugervejledningen til regimet](brugervejledning/regime).

## Regneeksempel

**Bredde, USA.** Af 503 aktier i S&P 500-listen har 480 mindst 200 dages kurser. 300 af dem lukker over deres 200-dages gennemsnit:

$$
B = 100 \cdot \frac{300}{480} = 62.5\ \%
$$

Med grænser på 60 og 40 % (eksemplets antagelse; din opsætning bruger i dag {{settings:regime.breadth_strong}} og {{settings:regime.breadth_weak}} %) stemmer rækken risk-on. Hvis bredden for en måned siden var 68 %, viser noten −6 pts over 1 month: stadig risk-on, men faldende.

**Bredde, Asien.** Gruppen har kun 10 aktier. Står 5 over gennemsnittet, er bredden 50 % (neutral). Én aktie mere giver 60 % og en risk-on-stemme. Én aktie flytter altså målet 10 procentpoint, og rækken har samme vægt i afstemningen som USA's 480 aktier.

**Nettonye højder.** I dag har 495 aktier i alle grupper et års historik. 30 lukker på en 52-ugers højde og 12 på en 52-ugers bund:

$$
NH = 100 \cdot \frac{30 - 12}{495} = 3.64
$$

Rækken bruger 10-dages gennemsnittet. Har de ti seneste dage været 2,1; 2,6; 2,9; 3,3; 3,0; 3,4; 3,8; 3,5; 3,8 og 3,64, er gennemsnittet 32,04 / 10 = 3,20. Med et bånd på ±3 (i din opsætning ±{{settings:regime.highs_lows_band}}) stemmer rækken risk-on.

**RSP/SPY.** For 63 dage siden var ratioen 0,2900, i dag 0,2842. Ændringen er 0,2842 / 0,2900 − 1 = −2,0 %: "Narrow". Det stemmer ikke, men hvis indekset samtidig står på ny top, er det en divergens, der er værd at notere.

## Faldgruber og begrænsninger

- **Overlevelsesbias i USA.** Den amerikanske gruppe er *dagens* S&P 500. Historiske breddeværdier er derfor for pæne, og sammenligninger bagud skal tages med forbehold. De kuraterede lister for Europa, Norden og Asien har samme problem: de er valgt i dag.
- **Små grupper er grove.** Asien-gruppen har 10 aktier; hver aktie er 10 procentpoint. Den nordiske og europæiske gruppe er større, men stadig udvalg, ikke hele markeder.
- **Fire bredderækker stemmer.** Hver region er én stemme, og i et globalt udsalg falder alle samtidig. Bredden kan derfor veje tungt i afstemningen, netop når den er mest korreleret. Se [Radarens afstemningsmodel](laerebog/afstemningsmodellen).
- **200-dages gennemsnittet er langsomt.** Bredden reagerer sent på et vendepunkt. Andelen over 50-dages gennemsnittet (vist i noten) er hurtigere, men stemmer ikke.
- **Bredde kan forblive smal længe.** Et smalt marked kan stige i årevis. RSP/SPY informerer derfor uden at stemme.
- **RSP er også en faktor.** Ratioen RSP/SPY blander bredde med en hældning mod mindre selskaber og value.
- **Udbyttejusterede kurser.** Radaren bruger justerede lukkekurser; et 52-ugers højdepunkt i radaren kan afvige lidt fra det, du ser i en kursgraf uden udbytter. Se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser).

## Videre læsning

- Zweig, M. (1986): *Winning on Wall Street*, Warner Books.
- Colby, R. W. (2003): *The Encyclopedia of Technical Market Indicators*, 2. udgave, McGraw-Hill (afsnittene om advance-decline, new highs/new lows og andele over glidende gennemsnit).
- Brown, S. J., Goetzmann, W., Ibbotson, R. G. og Ross, S. A. (1992): "Survivorship Bias in Performance Studies", *Review of Financial Studies* 5(4).
- Murphy, J. J. (1999): *Technical Analysis of the Financial Markets*, New York Institute of Finance (kapitlet om markedsbredde).
