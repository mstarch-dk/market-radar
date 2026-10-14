# Momentum

Siden [Momentum](/momentum) (sidehovedet hedder *Momentum leaders*) viser de stærkeste aktier i hver region målt på momentum: de aktier, der er steget mest over de seneste 3–12 måneder i forhold til de andre aktier i samme region. Det er tredje trin i det ugentlige overblik: efter vejret (regimet) og strømmen (rotationen) kommer de konkrete navne.

Momentumeffekten, altså at aktier, der er steget mest, har en tendens til at fortsætte en tid, er en af de bedst dokumenterede effekter i finansforskningen. Den er også kendt for pludselige, kraftige vendinger. Læs [Momentumeffekten](laerebog/momentumeffekten) og [Radarens momentumscore](laerebog/momentumscore) for baggrunden.

> **Bemærk:** Momentumlisten er et udgangspunkt for research, ikke en købsliste. Tjek altid historien bag en kursbevægelse.

## Regionerne

Siden har én sektion pr. region, med hurtiglinks øverst:

- *US (S&P 500)*: dagens S&P 500-selskaber
- *Europe large caps*: et udvalg af store europæiske selskaber
- *Nordic (C25 + large caps)*: C25 og store nordiske selskaber
- *Asia (semis & leaders)*: et udvalg af asiatiske ledere, med vægt på halvledere

Hver region viser sine top {{settings:momentum.top_n}} navne. Aktierne konkurrerer kun med andre aktier i samme region, så en nordisk aktie rangeres blandt nordiske aktier, ikke mod Nvidia.

## Momentumscoren

Kolonnen *Score* (0–100) er radarens samlede momentummål. Den regnes sådan:

1. For hver aktie i regionen beregnes tre afkast: **12-1 måneder** (de seneste 12 måneder, men uden den seneste måned), **6 måneder** og **3 måneder**.
2. For hvert af de tre afkast findes aktiens **percentil** i regionen: 100 er regionens højeste, 0 den laveste.
3. Scoren er **gennemsnittet** af de tre percentiler.

En score på 90 betyder altså, at aktien i gennemsnit ligger i toppen 10 % af sin region på de tre horisonter. Den seneste måned springes over i 12-månedersmålet, fordi meget kortsigtede bevægelser har en tendens til at vende (kortsigtet reversal).

Scoren kræver alle tre afkast. En aktie med under {{settings:momentum.min_history_days}} handelsdages historik har intet 12-1-afkast og dermed ingen score; den kommer ikke på listen. Afkastene regnes på udbyttejusterede lukkekurser i aktiens handelsvaluta.

Tallet er farvet efter niveau: under 25 *weak*, 25–40 *below average*, 40–60 *average*, 60–80 *strong* og over 80 *leader*.

## Kolonnerne

| Kolonne | Indhold |
|---|---|
| *Company* | Navn og ticker; *NEW* hvis navnet er nyt i top {{settings:momentum.top_n}} |
| *Industry* | Branche (fra Yahoo) |
| *Score* | Momentumscoren 0–100 |
| *1m*, *3m*, *6m* | Totalafkast over 1, 3 og 6 måneder |
| *12-1m* | 12-månedersafkast uden den seneste måned |
| *From 52w high* | Afstand under den højeste lukkekurs de seneste 52 uger (0 % = på toppen) |
| *Vol 20d/120d* | Gennemsnitlig volumen de seneste 20 dage divideret med de seneste 120 dage; over 1× er mere handel end normalt |
| *Trend* | ✓ når kursen er over 200-dages snit, og 50-dages snit er over 200-dages snit: en intakt optrend |
| *P/E next yr* | P/E på analytikernes indtjeningsskøn for næste regnskabsår, farvet i forhold til sektoren |
| *Signals* | Prikker for score, afstand til 52-ugers top og volumen |

Du kan slå flere kolonner til under *Columns*:

- *Sector* og *New* (som filter).
- *vs sector*: P/E divideret med medianen for samme sektor i regionen. 0,8× er 20 % billigere end sektoren. Kræver mindst {{settings:valuation.min_peers}} sammenlignelige selskaber med en P/E.
- *P/E this yr* og *P/E ttm*: P/E på indeværende års skøn og på de seneste 12 måneders faktiske indtjening.
- *EPS rev 4w* og *EPS rev 12w*: ændringen i analytikernes indtjeningsskøn for næste år over 4 og 12 uger. Ændringer inden for ±{{settings:valuation.revision_band|pct}} regnes som uændrede.
- *Div yield* og *Earnings*: udbytteafkast og næste regnskabsdato.

Har du skrevet markedssyn på siden *Market views*, får tabellen også en kolonne *Views*, der viser, om navnet passer med dine syn (*fits your views*), går imod dem (*against your views*) eller begge dele (*mixed*). Hold musen over mærket for at se begrundelserne. Se [Mine markedssyn](brugervejledning/markedssyn).

Værdiansættelsestallene kommer fra ugentlige øjebliksbilleder af Yahoos konsensus. De mangler, når selskabet har underskud, når skønnet ser inkonsistent ud, eller når Yahoo ikke har noget. Revisionerne mangler, indtil øjebliksbillederne går langt nok tilbage. Se [Estimatrevisioner](laerebog/estimatrevisioner).

## Nye navne og navne, der er faldet ud

Radaren sammenligner hver regions top {{settings:momentum.top_n}} med det seneste øjebliksbillede, der er mindst {{settings:snapshot_min_gap_days}} dage gammelt. Datoen står i sidehovedet.

- **NEW** ved et navn betyder, at det ikke var i top {{settings:momentum.top_n}} ved det tidligere øjebliksbillede. Nye navne er ofte de mest interessante, fordi de lige er begyndt at bevæge sig.
- **Dropped out of top {{settings:momentum.top_n}}** under regionens overskrift lister de navne, der var med sidst, men ikke er det længere. Ejer du et af dem, er det værd at se på.

Er der endnu intet tidligere øjebliksbillede (fx lige efter installation), bliver ingen navne markeret som nye.

## Klynger

Over hver regions tabel kan der stå en boks, *Clusters in the top {{settings:momentum.top_n}}*. En klynge er en branche eller sektor, der er overrepræsenteret blandt momentumlederne, fx:

> Semiconductors (industry) 5 names vs ~1.4 expected, 2 NEW: …

"Expected" er det antal, man ville vente, hvis brancheandelen i top {{settings:momentum.top_n}} svarede til dens andel af hele regionen. En branche bliver markeret som klynge, når den har:

- mindst {{settings:sectors.cluster_min}} navne i top {{settings:momentum.top_n}}, **og**
- mindst {{settings:sectors.cluster_ratio}} gange det forventede antal.

Radaren ser først på brancher og derefter på sektorer. En sektor, hvis navne allerede alle er dækket af en brancheklynge, vises ikke igen. Klyngerne er sorteret efter, hvor meget de overstiger det forventede.

En klynge er et tegn på, at momentum ikke kun handler om enkeltselskaber, men om en hel branche, der bliver købt. Det hænger ofte sammen med det, du ser på [Sector rotation](/rotation) og [Themes & factors](/themes). En klynge med mange nye navne er en branche, hvor bevægelsen breder sig.

## Fælles værktøjslinje

Alle regioner deler én værktøjslinje, som bliver hængende øverst, når du scroller. Søgning, filtre og kolonnevalg gælder for alle regioner på én gang. Nyttige filtre:

- *Score* med minimum 80 for kun at se lederne.
- *Trend* på *✓ Yes* for kun at se navne i en intakt optrend.
- *From 52w high* med maksimum, fx −10 %, for at finde navne, der er trukket tilbage fra toppen.
- *Industry* for at følge én branche på tværs af regioner.

*Export CSV* henter alle regioners synlige rækker i én fil. Se [Sådan finder du rundt](brugervejledning/navigation#tabellerne).

## Sådan bruger du siden

1. **Start med de nye navne.** Hvem er rykket ind i top {{settings:momentum.top_n}}, og hvorfor? Hold musen over navnet for et hurtigt overblik, eller åbn profilen.
2. **Kig efter klynger.** Passer de med rotationen? En klynge i halvledere samtidig med, at halvleder-temaet er i *Leading*, er en bekræftelse.
3. **Tjek trend og afstand til toppen.** Et navn med høj score uden *Trend* ✓ er ofte i en ustabil fase. Et navn langt over sit 50-dages snit er strakt.
4. **Tjek volumen.** En høj *Vol 20d/120d* sammen med en ny top kan betyde, at nogen køber stort; den kan også skyldes en enkelt nyhed.
5. **Se på værdiansættelsen.** Høj momentum og høj P/E i forhold til sektoren er en almindelig kombination, men den øger faldhøjden, hvis historien skuffer.
6. **Gå videre.** Sæt interessante navne på watchlist (☆), og skriv evt. et researchnotat med Claude Code; se [Claude Code-skills](brugervejledning/claude-code).

> **Tip:** Vil du finde navne, før de når radarens egne lister, så brug [Discover](/discover). Den scorer med samme formel, men på flere tusinde nordiske og europæiske aktier.
