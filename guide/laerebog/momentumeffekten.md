# Momentumeffekten

Aktier, der er steget mest de seneste 3–12 måneder, har i gennemsnit fortsat med at klare sig bedre end aktier, der er steget mindst, i de følgende måneder. Det er *momentumeffekten*, og den er en af de bedst dokumenterede afvigelser fra den simple teori om effektive markeder. Den er fundet i næsten alle lande, aktivklasser og årtier, men den har også sine voldsomme sammenbrud. Dette kapitel gennemgår evidensen, forklaringerne og risikoen. Hvordan radaren omsætter den til et tal, står i [Radarens momentumscore](laerebog/momentumscore).

## Intuition

Hvis markederne straks indregnede al ny information i kurserne, skulle en akties afkast i går ikke kunne sige noget om dens afkast i morgen. Men det gør det, i hvert fald på mellemlang sigt. Når et selskab får gode nyheder, stiger kursen, men ofte ikke hele vejen med det samme. Investorer er langsomme til at ændre mening, analytikere justerer deres skøn gradvist, og nogle sælger for tidligt for at sikre gevinsten. Kursen kryber derfor videre i samme retning i måneder.

På meget kort sigt (en uge til en måned) er mønstret det modsatte: de seneste vindere har en svag tendens til at falde lidt tilbage. Det skyldes blandt andet handelsfriktioner og midlertidigt pres fra store ordrer. På lang sigt (tre til fem år) vender det også: de største vindere over flere år klarer sig typisk dårligere bagefter.

Momentum lever altså i et vindue: cirka 3 til 12 måneders historik forudsiger de næste måneder. Det er derfor, klassiske momentummål ser på de seneste 12 måneder, men springer den seneste måned over.

## Teori

### Krydssektionelt momentum: Jegadeesh og Titman (1993)

Narasimhan Jegadeesh og Sheridan Titman sorterede amerikanske aktier (1965–1989) efter deres afkast over de seneste $J$ måneder ($J$ = 3, 6, 9, 12), købte den bedste tiendedel (vinderne), solgte den dårligste tiendedel (taberne) short og holdt porteføljen i $K$ måneder. Alle kombinationer gav positive afkast. Den ofte citerede 6/6-strategi gav omkring 1 % om måneden, cirka 12 % om året, og afkastet kunne ikke forklares med markedsrisiko (beta). En del af gevinsten forsvandt igen i årene 2–5 efter dannelsen.

Det kaldes *krydssektionelt* momentum, fordi aktierne sammenlignes med hinanden på samme tidspunkt: det handler om at være *relativt* stærk, ikke om at være steget.

Jegadeesh og Titman (2001) viste, at effekten fortsatte i årene efter offentliggørelsen, og Rouwenhorst (1998) fandt den samme effekt i 12 europæiske lande. Geczy og Samonov (2016) fulgte den tilbage til 1801.

### Carhart (1997): momentum som faktor

Mark Carhart føjede en momentumfaktor (afkastet af vindere minus tabere over de seneste 12 måneder, kaldt *UMD* eller *WML*) til Fama og Frenchs trefaktormodel. Med fire faktorer (marked, størrelse, værdi, momentum) kunne han forklare det meste af den tilsyneladende vedvarende performance hos investeringsforeninger: fonde, der havde klaret sig godt sidste år, gjorde det især, fordi de tilfældigvis ejede vinderaktier, ikke på grund af evner. Siden er momentum en standardfaktor i performancemåling. Se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

### Asness, Moskowitz og Pedersen (2013): momentum overalt

I "Value and Momentum Everywhere" målte Clifford Asness, Tobias Moskowitz og Lasse Heje Pedersen momentum som afkastet over de seneste 12 måneder *eksklusive den seneste måned* i otte markeder: aktier i USA, Storbritannien, det kontinentale Europa og Japan, landeindeks, statsobligationer, valuta og råvarer. Momentum gav positive præmier næsten overalt (svagest for japanske aktier), og afkastene var korrelerede *på tværs* af markederne. Samtidig var momentum negativt korreleret med værdi (billige aktiver), så en kombination af de to var langt mere stabil end hver for sig.

### Hvorfor springe den seneste måned over?

På kort sigt vender afkast: aktier, der steg mest den seneste måned, falder i gennemsnit lidt den næste (Jegadeesh 1990; Lehmann 1990). Forklaringerne er især mikrostruktur: kurser, der springer mellem købs- og salgskurs (*bid-ask bounce*), og midlertidigt pres fra store handler, som udlignes, når likviditeten vender tilbage. Medtager man den seneste måned i momentummålet, blander man to modsatrettede effekter. Derfor standardmålet:

$$
r_{12\text{-}1} = \frac{P_{t-1m}}{P_{t-12m}} - 1
$$

Novy-Marx (2012) gik videre og viste, at afkastet 7–12 måneder tilbage forudsiger bedre end afkastet 2–6 måneder tilbage, men det fund er omdiskuteret.

### Forklaringer: adfærd

- **Underreaktion.** Investorer opdaterer deres forventninger for langsomt på ny information (konservatisme), så kursen kun gradvist når sin nye værdi (Barberis, Shleifer og Vishny 1998). Hong og Stein (1999) peger på, at information spredes langsomt mellem investorer.
- **Overreaktion med forsinkelse.** Overmod og selvbekræftelse kan få investorer til at fortsætte en bevægelse for langt, hvilket forklarer både momentum og den senere vending (Daniel, Hirshleifer og Subrahmanyam 1998).
- **Dispositionseffekten.** Investorer sælger vindere for tidligt og holder på tabere. Salget af vindere holder kursen nede under dens fundamentale værdi, så den senere stiger mere (Grinblatt og Han 2005).
- **Flokadfærd og strømme.** Penge strømmer ind i fonde og temaer, der har gjort det godt, og presser kurserne videre.

### Forklaringer: risiko

- **Tidsvarierende risiko.** Vinderaktier kan have højere forventede afkast, fordi de på dannelsestidspunktet har højere eksponering mod risikofaktorer, fx vækstrisiko (Johnson 2002) eller forskelle i forventede afkast på tværs af aktier (Conrad og Kaul 1998).
- **Krakrisiko som præmie.** Momentum har sjældne, men meget store tab (se nedenfor). En præmie for at bære den risiko er en rationel forklaring.
- **Likviditetsrisiko.** Asness, Moskowitz og Pedersen (2013) fandt, at momentum klarer sig dårligt, når finansieringslikviditeten strammes.

Der er ingen konsensus. Sandsynligvis bidrager både adfærd og risiko.

### Momentumkrak: Daniel og Moskowitz (2016)

Momentumstrategier har en ubehagelig egenskab: negativ skævhed. I lange perioder tjener de jævnt, men af og til taber de meget på kort tid. Kent Daniel og Tobias Moskowitz viste, at krakkene kommer i et bestemt mønster: efter et langt bjørnemarked med høj volatilitet, når markedet pludselig vender op. Taberne fra faldet er ofte de mest risikable aktier (høj beta), og når markedet vender, stiger de voldsomt, mens vinderne (ofte defensive aktier) halter. De værste perioder var sommeren 1932 og foråret 2009, hvor en long/short-momentumstrategi mistede en stor del af sin værdi på få måneder.

Krakkene er delvist forudsigelige: de sker efter markedsfald og ved høj volatilitet. Både Daniel og Moskowitz og Barroso og Santa-Clara (2015) viser, at en strategi, der skalerer momentumeksponeringen ned, når volatiliteten er høj, undgår en stor del af tabene.

For en investor, der kun køber (*long-only*), er krakket mildere, men mærkbart: vinderne stiger mindre end markedet, mens de tidligere tabere fører an i opsvinget.

### Industrimomentum: Moskowitz og Grinblatt (1999)

Tobias Moskowitz og Mark Grinblatt fandt, at hele brancher udviser momentum, og at en stor del af aktiemomentum kan forklares af branchemomentum: vinderaktier er ofte vindere, fordi deres branche er i fremgang. I modsætning til enkeltaktier har branchemomentum ikke den samme kortsigtede vending; effekten var stærkest på en måneds horisont. Det er grundlaget for sektorrotation: at følge relativ styrke på sektor- og temaniveau. Se [Relativ styrke](laerebog/relativ-styrke) og [Sektorer, temaer, faktorer og konjunkturcyklussen](laerebog/rotation-og-cyklus).

### Tidsseriemomentum: Moskowitz, Ooi og Pedersen (2012)

Krydssektionelt momentum spørger "hvem er stærkest?". Tidsseriemomentum spørger "er dette aktiv selv steget?". Moskowitz, Ooi og Pedersen fandt i 58 futures-markeder, at et positivt 12-måneders afkast forudsiger et positivt afkast den næste måned, med en effekt, der varer op til ca. et år og derefter delvist vender. Tidsseriemomentum klarede sig særlig godt i store bjørnemarkeder, fordi strategien da er gået short. Det er teorien bag trendfiltre; se [Glidende gennemsnit og trend](laerebog/trend).

### Relevans for en horisont på 1–6 måneder

Momentumeffekten er stærkest i de første måneder efter målingen og aftager inden for et år. Det passer til en horisont på 1–6 måneder, men det betyder også:

- **Signalet forældes.** En rangering fra for tre måneder siden siger mindre end dagens. Momentumlister skal opdateres løbende (de akademiske strategier rebalancerer månedligt).
- **Omsætning koster.** Månedlig rebalancering giver høj omsætning. For institutionelle investorer har handelsomkostninger spist en del af præmien i små og illikvide aktier (Lesmond, Schill og Zhou 2004), mens Frazzini, Israel og Moskowitz (2018) finder, at præmien overlever for store, likvide aktier.
- **Skat.** For en dansk investor med lagerbeskatning på aktiesparekonto er omsætning skattemæssigt neutral; for enkeltaktier i frie midler, som realisationsbeskattes, fremrykker hyppige salg med gevinst skatten. Se [Dansk skat for investorer](laerebog/skat).

## Sådan gør radaren

Radaren bruger momentumeffekten på tre niveauer:

1. **Enkeltaktier, krydssektionelt.** [Momentum](/momentum) rangerer aktier inden for fire regionale lister efter et gennemsnit af percentilerne for 12-1-måneders, 6-måneders og 3-måneders afkast. 12-1-målet er AMP's, og 3- og 6-måneders afkastene giver vægt til den nyere udvikling, som passer til en horisont på 1–6 måneder. Detaljerne står i [Radarens momentumscore](laerebog/momentumscore).
2. **Brancher og sektorer.** Momentumsiden markerer *clusters*: brancher eller sektorer, der er overrepræsenteret blandt de stærkeste aktier i en region. Det er et direkte nik til Moskowitz og Grinblatt: når mange vindere kommer fra samme branche, er det ofte branchen, der driver dem. Sektor- og tema-ETF'erne på [Sektorrotation](/rotation) rangeres efter relativ styrke mod ACWI over 1, 3 og 6 måneder; se [Relativ styrke](laerebog/relativ-styrke).
3. **Tidsserie.** ACWI-trenden på [Regime](/regime) og `trend_ok` for den enkelte aktie er tidsseriemomentum i form af glidende gennemsnit.

Radaren laver ingen short-ben og ingen automatisk volatilitetsskalering. Den viser en liste til videre research, ikke en portefølje. Advarslen fra Daniel og Moskowitz er derfor værd at have i baghovedet: når regimet har været risk-off længe, og markedet vender kraftigt op, er de gamle momentumledere ofte ikke dem, der fører an. Regime-siden har en række til netop det, *Momentum-crash setup (ACWI)*. Den står ved siden af *Momentum payoff* og *Return dispersion*, og ingen af de tre stemmer; se [Regime](brugervejledning/regime).

## Regneeksempel

### Effekten af at springe den seneste måned over

To aktier er begge steget 30 % over 12 måneder:

| | 12 mdr. i alt | Seneste måned | $r_{12\text{-}1}$ |
|---|---|---|---|
| A | +30 % | +15 % | 1,30 / 1,15 − 1 = **+13,0 %** |
| B | +30 % | −5 % | 1,30 / 0,95 − 1 = **+36,8 %** |

12-1-målet rangerer B langt over A. A's afkast er koncentreret i den seneste måned, hvor kortsigtet vending trækker den anden vej; B's stigning er sket tidligere og mere vedvarende.

### En lille vinder-minus-taber-strategi

Et univers på ti aktier rangeres efter $r_{12\text{-}1}$. De tre bedste købes, de tre dårligste sælges short, med lige vægte. Næste måned:

| Gruppe | Afkast næste måned |
|---|---|
| Vindere (gennemsnit) | +2,5 % |
| Midten | +1,2 % |
| Tabere (gennemsnit) | +0,4 % |

Long/short-afkastet er 2,5 − 0,4 = 2,1 procentpoint. Long-only mod hele universet (gennemsnit af alle ti, her (3 · 2,5 + 4 · 1,2 + 3 · 0,4)/10 = 1,35 %) er merafkastet 2,5 − 1,35 = 1,15 procentpoint.

### Et momentumkrak

Efter et bjørnemarked stiger markedet 20 % på en måned. Taberne (høj beta) stiger 60 %, vinderne (defensive) 8 %.

- Long/short: 8 − 60 = **−52 procentpoint** på en måned.
- Long-only: 8 − 20 = **12 procentpoint** bag markedet.

Det er den slags måned, der i den akademiske litteratur kan æde flere års momentumpræmie.

## Faldgruber og begrænsninger

- **Gennemsnit, ikke garanti.** Momentum er en statistisk tendens på tværs af mange aktier. Den enkelte vinderaktie kan sagtens vende.
- **Krak efter bjørnemarkeder.** Den største risiko kommer, når markedet vender op efter lange fald. Så kan momentum halte voldsomt.
- **Effekten er svagere end i de første studier.** Mange investorer kender den nu, og præmien har været mindre og mere svingende i nyere tid. Gennemsnit fra forskning er ikke et forventet afkast for dig.
- **Koncentration.** Momentumlister samler sig ofte i få brancher eller temaer. Det øger risikoen, fordi aktierne bevæger sig sammen.
- **Omsætning og skat.** At følge en momentumliste tæt giver mange handler. Overvej omkostninger og skat for den konto, du handler på.
- **Survivorship i tests.** Mange backtests bruger dagens aktieliste. Radarens eget univers (dagens S&P 500) har samme problem, hvis man bruger det bagud. `radar study longrun` tester derfor scorens regel på brancher siden 1926 og lande siden 1986, bygget af alle noterede aktier, og viser momentumfaktorens basisrater: hvor ofte den har tabt over 6 og 12 måneder, og hvor dybe og lange dens krak har været. Se [Testen over årtier](brugervejledning/scoretest#testen-over-årtier).

## Videre læsning

- Narasimhan Jegadeesh og Sheridan Titman: "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency", *Journal of Finance*, 48(1), 1993.
- Mark M. Carhart: "On Persistence in Mutual Fund Performance", *Journal of Finance*, 52(1), 1997.
- Clifford S. Asness, Tobias J. Moskowitz og Lasse Heje Pedersen: "Value and Momentum Everywhere", *Journal of Finance*, 68(3), 2013.
- Kent Daniel og Tobias J. Moskowitz: "Momentum Crashes", *Journal of Financial Economics*, 122(2), 2016.
- Tobias J. Moskowitz og Mark Grinblatt: "Do Industries Explain Momentum?", *Journal of Finance*, 54(4), 1999.
- Tobias J. Moskowitz, Yao Hua Ooi og Lasse Heje Pedersen: "Time Series Momentum", *Journal of Financial Economics*, 104(2), 2012.
- Narasimhan Jegadeesh: "Evidence of Predictable Behavior of Security Returns", *Journal of Finance*, 45(3), 1990.
- Nicholas Barberis, Andrei Shleifer og Robert Vishny: "A Model of Investor Sentiment", *Journal of Financial Economics*, 49(3), 1998.
- Harrison Hong og Jeremy C. Stein: "A Unified Theory of Underreaction, Momentum Trading, and Overreaction in Asset Markets", *Journal of Finance*, 54(6), 1999.
- Pedro Barroso og Pedro Santa-Clara: "Momentum Has Its Moments", *Journal of Financial Economics*, 116(1), 2015.
- Clifford S. Asness, Andrea Frazzini, Ronen Israel og Tobias J. Moskowitz: "Fact, Fiction, and Momentum Investing", *Journal of Portfolio Management*, 40(5), 2014 (en letlæst oversigt).
