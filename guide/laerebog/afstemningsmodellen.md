# Radarens afstemningsmodel

## Intuition

De foregående kapitler i denne del har beskrevet hver sin indikator for markedets risikovilje: trend, markedsbredde, VIX, kredit, renter, dollar, råvarer, ledende indikatorer og indtjeningsrevisioner. Hver af dem fortæller en del af historien, og hver af dem tager fejl en gang imellem. Spørgsmålet er, hvordan man samler dem til én vurdering.

Radaren gør det på den mest gennemsigtige måde, der findes: en afstemning. Hver indikator får én stemme. Den stemmer risk-on, risk-off eller holder sig neutral efter faste, offentlige regler. Stemmerne tælles, og resultatet bliver *Risk-on*, *Risk-off* eller blandet (*Mixed*).

Det er bevidst simpelt. Der er ingen vægte, der er fundet ved at optimere på historiske data, ingen skjult model og ingen sandsynligheder. Du kan altid se præcis, hvilke indikatorer der trækker i hvilken retning, og hvorfor. Prisen for gennemsigtigheden er, at modellen er grov. Den er en strukturerer af information, ikke en forudsigelsesmaskine.

## Teori

### Afstemning som model

En afstemning er en særlig simpel lineær model. Lad hver indikator $k$ give et signal $v_k \in \{+1, 0, -1\}$ (risk-on, neutral, risk-off). Nettostemmen er gennemsnittet af de ikke-neutrale signaler:

$$
\text{net} = \frac{\sum_k v_k}{\sum_k |v_k|} = \frac{n_{\text{on}} - n_{\text{off}}}{n_{\text{on}} + n_{\text{off}}}
$$

Den ligger mellem −1 (alle stemmer risk-off) og +1 (alle stemmer risk-on). Neutrale stemmer indgår ikke i nævneren: de trækker hverken op eller ned, og de udvander heller ikke resultatet. Fem risk-on og ingen risk-off giver net = 1, uanset om der også er ti neutrale.

Hver indikator er reduceret til tre niveauer med faste tærskler. Det smider information væk (en VIX på 26 og en på 60 er begge bare risk-off), men gør modellen robust over for ekstreme værdier: ingen enkelt indikator kan dominere, uanset hvor ekstrem den er.

### Lige vægte

Hvorfor ikke vægte de bedste indikatorer højest? Fordi det er svært at vide, hvilke der er bedst. Historiske tests af regimeindikatorer bygger på få, meget forskellige kriser, og optimerede vægte tilpasser sig ofte den støj, der tilfældigvis var i testperioden. Dawes (1979) viste, at modeller med lige vægte ("improper linear models") ofte forudsiger næsten lige så godt som optimerede modeller uden for testperioden, og bedre end menneskelig vurdering. Harvey, Liu og Zhu (2016) viste, hvor let det er at finde tilsyneladende signifikante mønstre i finansielle data, når man tester mange muligheder.

Lige vægte er et valg om ydmyghed, ikke en påstand om, at alle indikatorer er lige gode.

### Styrker ved en simpel afstemning

- **Gennemsigtig.** Hver stemme kan forklares med én sætning og tjekkes mod data.
- **Robust.** Ingen enkelt indikator eller ekstremværdi kan vælte resultatet.
- **Bred.** Den kombinerer aktier, optioner, kredit, renter, valuta, råvarer, makro og indtjening.
- **Ærlig om manglende data.** En indikator uden data stemmer ikke, i stedet for at blive gættet.
- **Ingen optimering.** Der er ikke noget at overtilpasse.

Svaghederne står i [Faldgruber og begrænsninger](laerebog/afstemningsmodellen#faldgruber-og-begrænsninger).

## Sådan gør radaren

Afstemningen beregnes i `src/radar/signals/regime.py`: `indicators()` laver rækkerne, `apply_freshness()` markerer gamle data, `apply_votes()` slår grupper til og fra, og `overall()` tæller stemmerne.

### Alle rækker

Tærskler med en værdi i `config/settings.yaml` vises med den værdi, du har i dag. Tærskler uden indstilling ligger fast i koden.

| Række (appen) | Risk-on | Risk-off | Kilde | Kapitel |
|---|---|---|---|---|
| *Global trend (ACWI)* | Kurs > 200d-snit og 50d-snit > 200d-snit | Kurs < 200d-snit og 50d-snit < 200d-snit | prices | [Risk-on og risk-off](laerebog/risk-on-risk-off) |
| *Breadth – US (S&P 500)* | ≥ {{settings:regime.breadth_strong}} % over 200d | ≤ {{settings:regime.breadth_weak}} % | prices | [Markedsbredde](laerebog/markedsbredde) |
| *Breadth – Europe large caps* | samme | samme | prices | [Markedsbredde](laerebog/markedsbredde) |
| *Breadth – Nordic* | samme | samme | prices | [Markedsbredde](laerebog/markedsbredde) |
| *Breadth – Asia* | samme | samme | prices | [Markedsbredde](laerebog/markedsbredde) |
| *New highs – new lows* | ≥ +{{settings:regime.highs_lows_band}} | ≤ −{{settings:regime.highs_lows_band}} | prices | [Markedsbredde](laerebog/markedsbredde) |
| *Equal vs cap weight (RSP/SPY)* | stemmer aldrig | stemmer aldrig | prices | [Markedsbredde](laerebog/markedsbredde) |
| *Volatility (VIX)* | < {{settings:regime.vix_calm}} | > {{settings:regime.vix_stress}} | prices | [VIX](laerebog/vix) |
| *VIX term structure* | VIX/VIX3M < {{settings:regime.vix_term_calm}} | > 1 (kode) | prices | [VIX](laerebog/vix) |
| *Credit (US HY spread)* | < 0,97 × 126-obs.-snit (kode) | > 1,03 × snit (kode) | fred | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| *Euro credit (HY spread)* | samme | samme | fred | gruppe `credit_eu` |
| *Yield curve (10Y-2Y)* | aldrig | < 0 (kode) | fred | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| *US 10Y yield* | aldrig | stigning over 63 obs. > {{settings:regime.rates_shock}} pp | fred | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| *US dollar (broad)* | < −3 % over 63 obs. (kode) | > +3 % (kode) | fred | [Kredit, renter og dollar](laerebog/kredit-renter-dollar) |
| *Copper/gold ratio* | > +{{settings:regime.copper_gold_band|pct}} over 63 dage | < −{{settings:regime.copper_gold_band|pct}} | prices | [Kobber, guld og olie](laerebog/raavarer) |
| *Oil (WTI)* | aldrig | > +{{settings:regime.oil_shock|pct}} over 63 dage | prices | [Kobber, guld og olie](laerebog/raavarer) |
| *Leading indicators (OECD CLI, G20)* | Expansion | Contraction | oecd | [Ledende indikatorer](laerebog/ledende-indikatorer) |
| *Earnings revisions (S&P 500)* | > +{{settings:regime.revisions_band}} pp | < −{{settings:regime.revisions_band}} pp | factset | [Ledende indikatorer](laerebog/ledende-indikatorer) |
| *Valuation (Shiller CAPE, US)* | ≤ {{settings:regime.cape_cheap_pct}}. percentil | ≥ {{settings:regime.cape_rich_pct}}. percentil | cape | gruppe `valuation` |
| *Equity risk premium (Damodaran)* | ≥ {{settings:regime.erp_high_pct}}. percentil | ≤ {{settings:regime.erp_low_pct}}. percentil | erp | gruppe `valuation` |

Alt, der ikke rammer risk-on eller risk-off, er neutral. Det giver 20 rækker. RSP/SPY stemmer aldrig, og tre rækker er **envejsrækker**, der kun kan stemme risk-off: rentekurven, den 10-årige rente og olien. Deres modsatte tilstand (positiv kurve, rolige renter, rolig olie) er normaltilstanden og ikke et særligt risk-on-tegn. Værdiansættelsens teori står i [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie).

### Status for en række

Hver række har én af fem statusser (kolonnen *Vote* på [Regime](/regime)):

| Status | Betydning | Tæller i nettostemmen |
|---|---|---|
| *risk-on* | Indikatoren peger på risikovilje | Ja, +1 |
| *risk-off* | Indikatoren peger på risikoaversion | Ja, −1 |
| *neutral* | Mellem tærsklerne; informerer | Nej (hverken i tæller eller nævner) |
| *n/a* | Ingen data, eller for kort historik | Nej |
| *stale* | Data er for gamle | Nej |

En række uden data forsvinder ikke; den står som *n/a*, så du kan se, hvad vurderingen *ikke* bygger på. Det følger radarens grundregel om, at manglende data vises som manglende og aldrig som 0.

### Friskhed

Hver række har en kilde, og hver kilde har en maksimal alder i `coverage.max_age` i `config/settings.yaml`. Er rækkens seneste datapunkt mere end så mange dage ældre end rapportens dato (ACWI's seneste lukkekurs), bliver status *stale*. Aflæsningen bliver stående, men noten får tilføjet datoen og "not counted", og rækken stemmer ikke.

| Kilde | Rækker | Maksimal alder |
|---|---|---|
| prices | Trend, bredde, VIX, kobber/guld, olie | {{settings:coverage.max_age.prices}} dage |
| fred | Kredit, kurve, 10Y, dollar | {{settings:coverage.max_age.fred}} dage |
| oecd | CLI | {{settings:coverage.max_age.oecd}} dage |
| factset | Revisioner | {{settings:coverage.max_age.factset}} dage |
| cape | CAPE | {{settings:coverage.max_age.cape}} dage |
| erp | Risikopræmie | {{settings:coverage.max_age.erp}} dage |

Grænserne afspejler, hvor ofte og hvor sent hver kilde opdateres. Se [Data og dækning](brugervejledning/data-og-daekning).

### Grupper der kan slås fra

Nogle rækker tilhører en gruppe, der kan slås til og fra. Standarden står under `regime.votes` i `config/settings.yaml`, og du kan ændre den for dig selv med kontakterne på [Regime](/regime) (dit valg gemmes lokalt og går forud for standarden). En række i en gruppe, der er slået fra, vises stadig med sin aflæsning, men stemmer ikke.

- **`credit_eu`** (euro-HY-spændet), standard: {{settings:regime.votes.credit_eu}}. Giver et europæisk kreditperspektiv ved siden af det amerikanske, men har kort historik på FRED og er tæt korreleret med det amerikanske spænd.
- **`valuation`** (CAPE og risikopræmien), standard: {{settings:regime.votes.valuation}}. Værdiansættelse bevæger sig langsomt og siger meget om de næste 10 års afkast, men lidt om de næste 1–6 måneder. Et dyrt marked kan blive dyrere i årevis. Derfor er gruppen som udgangspunkt ikke en del af en afstemning, der skal beskrive det kortsigtede regime.

Rækker uden gruppe stemmer altid.

### Fra stemmer til etiket

Blandt de stemmende rækker tælles $n_{\text{on}}$ og $n_{\text{off}}$, og

$$
\text{net} = \frac{n_{\text{on}} - n_{\text{off}}}{n_{\text{on}} + n_{\text{off}}}
$$

(er der ingen risk-on- eller risk-off-stemmer, er net = 0). Etiketten:

- **Risk-on**, hvis net > 0,33,
- **Risk-off**, hvis net < −0,33,
- **Mixed** (blandet) ellers.

Grænsen ±0,33 ligger fast i koden. Den svarer til, at den ene side skal have mindst dobbelt så mange stemmer som den anden: med net = 1/3 er forholdet præcis 2:1. Uligheden er streng, men nettostemmen *vises* afrundet til to decimaler, så et net på 0,333 vises som 0,33 og giver alligevel *Risk-on* (se regneeksemplet).

### Hvor du ser det

[Regime](/regime) viser etiketten, antallet af stemmer i hver kategori, kontakterne for grupperne, alle rækker med aflæsning, note, kilde og dato, samt graferne. Etiketten bruges også andre steder i radaren, fx når stopniveauet for dine beholdninger justeres (se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse)). Se [brugervejledningen til regimet](brugervejledning/regime).

### Sådan bruger du den

- **Som kontekst, ikke som timing.** Etiketten beskriver det nuværende miljø. Den skifter efter markedet, ikke før. Brug den til at kalibrere forventninger, positionsstørrelser og stop, ikke til at gå ind og ud af markedet.
- **Læs rækkerne, ikke kun etiketten.** *Risk-on* med 6 mod 2 er noget andet end *Risk-on* med 12 mod 0. Hvilke rækker er skiftet for nylig? Er det kreditmarkedet eller kun aktiemarkedet, der er bekymret?
- **Hold øje med uenighed.** Det mest informative er ofte, når forskellige markeder siger forskellige ting: stigende aktier, men udvidede kreditspænd; et indeks på toppen, men svag bredde.
- **Tjek friskheden.** Mange *stale*- eller *n/a*-rækker betyder, at vurderingen bygger på færre ben end normalt.

## Regneeksempel

Et tænkt øjebliksbillede. Antag, at gruppen `valuation` er slået fra og `credit_eu` slået til (standarderne er i dag {{settings:regime.votes.valuation}} og {{settings:regime.votes.credit_eu}}).

| Række | Aflæsning | Status |
|---|---|---|
| Global trend (ACWI) | +4,2 % over 200d, 50d over 200d | risk-on |
| Breadth – US | 64 % | risk-on |
| Breadth – Europe | 55 % | neutral |
| Breadth – Nordic | 38 % | risk-off |
| Breadth – Asia | 70 % | risk-on |
| New highs – new lows | +2,1 | neutral |
| RSP/SPY | −2,0 % over 3m | neutral (stemmer aldrig) |
| VIX | 16,5 | risk-on |
| VIX/VIX3M | 0,86 | risk-on |
| US HY | 0,99 × snit | neutral |
| Euro HY | 1,01 × snit | neutral |
| Yield curve | +0,45 | neutral |
| US 10Y | +0,57 pp over 3m | risk-off |
| US dollar | −3,25 % over 3m | risk-on |
| Copper/gold | +2,0 % over 3m | neutral |
| Oil | +12 % over 3m | neutral |
| OECD CLI, G20 | Slowdown | neutral |
| Earnings revisions | rapport 20 dage gammel | stale |
| CAPE | 96. percentil | (risk-off, stemmer ikke: gruppe fra) |
| ERP | ingen data | (n/a, stemmer ikke: gruppe fra) |

**Optælling** (tærskler som standardindstillingerne): 6 risk-on (trend, bredde USA, bredde Asien, VIX, VIX-struktur, dollar), 2 risk-off (bredde Norden, 10Y), 9 neutrale, 1 stale, 2 rækker uden stemme. I alt 20.

$$
\text{net} = \frac{6 - 2}{6 + 2} = \frac{4}{8} = 0.50
$$

0,50 > 0,33 → **Risk-on**.

**Slå `valuation` til.** CAPE stemmer nu risk-off; ERP tæller som *n/a* og stemmer ikke. Nu er der 6 mod 3:

$$
\text{net} = \frac{6 - 3}{6 + 3} = \frac{3}{9} = 0.333\ldots
$$

Vist som 0,33, men 0,333… er strengt større end 0,33 → stadig **Risk-on**, lige på kanten.

**Og et olieshock oveni.** Stiger olien over grænsen, stemmer den risk-off: 6 mod 4 giver net = 2/10 = 0,20 → **Mixed**.

Eksemplet viser to ting. For det første kan få stemmer flytte etiketten, når det samlede antal ikke-neutrale stemmer er lille: her vippede to ekstra risk-off-stemmer resultatet fra klar *Risk-on* til *Mixed*. For det andet er det værd at se, *hvilke* stemmer der flyttede sig. En dyr værdiansættelse og en oliepris, der stiger, er to meget forskellige historier.

## Faldgruber og begrænsninger

- **Korrelerede indikatorer tæller dobbelt.** Fire bredderækker, to VIX-rækker og to HY-rækker måler i høj grad det samme. I en global krise kan 8–10 rækker gå i risk-off på grund af én begivenhed. Det ligner stor enighed, men er færre uafhængige signaler. Se regneeksemplet i [Risk-on og risk-off](laerebog/risk-on-risk-off#regneeksempel).
- **USA-tung.** VIX, kurven, 10Y, dollaren, FactSet, CAPE og ERP er amerikanske, og den amerikanske bredde og nettonye højder bygger på cirka 500 aktier. En europæisk eller nordisk krise, der ikke smitter, ses kun delvist.
- **Ingen optimering, ingen validering.** Tærsklerne er rimelige tommelfingerregler, ikke estimerede optimale værdier. Modellen er ikke backtestet som en handelsstrategi, og den bør ikke bruges som en.
- **Tærskeleffekter.** En VIX på 17,9 og en på 18,1 kan give forskellige stemmer. Gauge-farverne på [Regime](/regime) viser, hvor tæt en aflæsning er på sin tærskel.
- **Envejsrækker giver en skævhed.** Tre rækker kan kun stemme risk-off. I rolige tider er de neutrale; i stressede tider trækker de ned. Det gør modellen lidt hurtigere til at advare end til at give grønt lys, hvilket er bevidst, men værd at kende.
- **Neutral er ikke ingenting.** Mange neutrale rækker betyder, at markedet ligger mellem tærsklerne, ofte en overgangsfase. Nettostemmen ignorerer dem.
- **Få stemmer, stor følsomhed.** Når kun 6–8 rækker stemmer, kan én række flytte net med 0,2–0,3.
- **Forsinkelse.** OECD-data er måneder gamle, FactSet ugentlig, FRED-dollaren 1–2 uger forsinket. Afstemningen blander hurtige og langsomme signaler.
- **Regimet er ikke en prognose.** Se [Risk-on og risk-off](laerebog/risk-on-risk-off#faldgruber-og-begrænsninger).

## Videre læsning

- Dawes, R. M. (1979): "The Robust Beauty of Improper Linear Models in Decision Making", *American Psychologist* 34(7).
- Harvey, C. R., Liu, Y. og Zhu, H. (2016): "… and the Cross-Section of Expected Returns", *Review of Financial Studies* 29(1).
- Kritzman, M., Page, S. og Turkington, D. (2012): "Regime Shifts: Implications for Dynamic Strategies", *Financial Analysts Journal* 68(3).
- Ang, A. og Timmermann, A. (2012): "Regime Changes and Financial Markets", *Annual Review of Financial Economics* 4.
