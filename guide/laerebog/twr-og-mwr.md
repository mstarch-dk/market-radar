# Tidsvægtet og pengevægtet afkast

## Intuition

"Hvor meget har min portefølje givet?" lyder som et simpelt spørgsmål, men det har to gode svar, og de kan pege i hver sin retning.

Det ene svar handler om **investeringerne**: hvor godt klarede de papirer, du valgte, sig, uanset hvornår du satte penge ind eller tog dem ud? Det er det **tidsvægtede afkast** (TWR, *time-weighted return*). Det er det rigtige mål for at sammenligne med ACWI, med en fond eller med en anden portefølje, fordi det ikke straffer eller belønner dig for tidspunkter, du måske ikke selv valgte (fx da lønnen gik ind).

Det andet svar handler om **dine penge**: hvad tjente de kroner, du faktisk havde investeret, når der tages højde for, at du havde flere penge inde i nogle perioder end i andre? Det er det **pengevægtede afkast** (MWR, *money-weighted return*), også kaldet den interne rente (IRR) eller XIRR. Det er dit faktiske udbytte, inklusive din timing.

Forskellen er timing. Satte du mange penge ind lige før et fald, er dit pengevægtede afkast lavere end det tidsvægtede: investeringerne klarede sig fint, men de fleste af dine penge var med i den dårlige periode.

- **TWR** svarer på: "Var mine valg gode?"
- **MWR** svarer på: "Hvad fik jeg ud af det?"

## Teori

### Tidsvægtet afkast

TWR deler perioden op ved hver ind- eller udbetaling og kæder delperiodernes afkast sammen geometrisk:

$$
1 + R_{TWR} = \prod_{k=1}^{K} (1 + r_k)
$$

Hvert delafkast $r_k$ måles på kapitalen i netop den delperiode, så størrelsen af ind- og udbetalinger påvirker ikke resultatet. Det svarer til at følge værdien af én investeret krone hele vejen.

Med daglige værdier skal man beslutte, hvornår på dagen en pengestrøm sker. En almindelig, forsigtig konvention er: indbetalinger tæller fra dagens start (de var med til at bære dagens risiko), udbetalinger ved dagens slutning (de bar dagens risiko, før de forlod porteføljen). Så er dagens afkast

$$
r_t = \frac{V_t + U_t}{V_{t-1} + I_t} - 1
$$

hvor $V_t$ er værdien ved lukketid, $I_t$ indbetalinger og $U_t$ udbetalinger på dagen. Kædet sammen bliver det et indeks, der starter i 100. Det er den metode, investeringsbranchens GIPS-standarder foreskriver til at præsentere forvaltningsresultater (CFA Institute, 2020).

### Pengevægtet afkast

MWR er den rente $r$, der får nutidsværdien af alle pengestrømme, set fra investorens side, til at gå i nul. Indbetalinger er negative (penge ud af lommen), udbetalinger og slutværdien positive:

$$
\sum_{j} \frac{CF_j}{(1 + r)^{(d_j - d_0)/365}} = 0
$$

med $d_j$ datoen for strøm $j$. Med uregelmæssige datoer kaldes det XIRR (efter regnearksfunktionen). Ligningen har ingen lukket løsning og løses numerisk. I sjældne tilfælde med skiftende fortegn i strømmene kan der være flere løsninger eller ingen.

Dichev (2007) beregnede pengevægtede afkast for hele aktiemarkeder og fandt, at investorernes faktiske, pengevægtede afkast har ligget klart under de tidsvægtede: investorer har samlet set sat penge ind efter gode perioder og trukket dem ud efter dårlige. Det samme mønster ses for fondsinvestorer. Forskellen kaldes ofte *behavior gap*.

### Hvorfor begge

| | TWR | MWR |
|---|---|---|
| Måler | investeringernes udvikling | dine pengens udvikling |
| Påvirkes af ind-/udbetalinger | nej | ja |
| Til sammenligning med benchmark | ja | kun mod benchmark med samme strømme |
| Kræver | værdi ved hver strøm | kun strømme og slutværdi |

TWR er det retfærdige mål for **evne**: det sammenligner papirvalg på lige fod. MWR er det ærlige mål for **oplevelse**: det er, hvad du faktisk fik. Den bedste sammenligning for MWR er derfor ikke ACWI's TWR, men hvad ACWI ville have givet med præcis dine ind- og udbetalinger.

### Annualisering

Et samlet afkast $R$ over $D$ dage svarer til en årlig rate $(1+R)^{365/D} - 1$. Over perioder kortere end et år giver annualisering urimeligt store tal, og mange standarder fraråder det. Se [Afkast og renters rente](laerebog/afkast).

## Sådan gør radaren

Afkast over tid beregnes i `performance.py` og vises på siden [Returns](/returns) (se [Afkast over tid](brugervejledning/afkast)).

### Værdi hver dag

- Kalenderen er benchmarkens (ACWI's) handelsdage. En handel på en dag uden handel tæller på næste handelsdag.
- Porteføljen værdisættes i kroner ved hver lukkekurs: beholdninger gange kurs gange kronekurs, plus kontanter hvis porteføljen har en kassebog.
- **Huller, aldrig nuller.** Mangler en kurs (ud over højst 5 dages fremskrivning) eller en kronekurs for et papir, du ejer, er dagens værdi ukendt. Den dag vises som et hul, og afkastet kædes over hullet fra den sidste kendte værdi. En manglende kurs tolkes aldrig som et fald til nul.

### Finansiering: ledger eller implicit

Radaren skal vide, hvad der er nye penge, og hvad der er porteføljens egne bevægelser:

- **ledger** (kassebog): porteføljen har indbetalinger (DEPOSIT) eller udbetalinger (WITHDRAW). Værdien er beholdninger plus kontanter, og kun ind- og udbetalinger er eksterne strømme. Køb og salg flytter blot penge mellem kontanter og papirer.
- **implicit**: ingen kontantrækker. Hvert køb tælles som nye penge ind, og hvert salg eller hver indtægt som penge taget ud. Det er den eneste mulighed, når du kun har registreret handler.

### Udbytte

- **reinvested** (standard): værdien beregnes på udbyttejusterede kurser, og hver købt post skaleres med forholdet mellem justeret og handlet kurs på handelsdagen. Udbytte tæller dermed som geninvesteret. Udbytterækker (DIVIDEND) gemmes, men tælles ikke, ellers ville udbyttet tælle to gange.
- **cash**: værdien beregnes på handlede kurser, og udbytterækker lægges i kassen. Uden kassebog (implicit) tæller et udbytte som penge taget ud.

Se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser) for, hvordan justerede kurser virker.

### Tidsvægtet indeks

Dagens afkast er $r = (V + U)/(V_{forrige} + I) - 1$ med indbetalinger fra dagens start og udbetalinger ved dagens slutning, kædet sammen til et indeks, der starter i 100. Konsekvensen er, at penge, der indbetales og først investeres ved lukketid, står stille den dag: én dags kontantslæb, ikke en fejl. En dag uden kapital har intet afkast. En handel, hvis kroneværdi er ukendt, bryder kæden på dagen (dagens afkast udelades, og det siges).

Siden viser samlet afkast og afkast over 1, 3 og 6 måneder (21, 63 og 126 handelsdage), 1 år (252), år til dato og siden start, hver med ACWI ved siden af. Et årligt tal vises kun med mindst 365 dages historik. Volatilitet og maksimal drawdown beregnes på det daglige indeks (se [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown)).

### XIRR ved halvering

MWR er XIRR af de eksterne strømme og slutværdien med 365-dages år, som formlen ovenfor. Radaren løser ligningen ved halvering (bisektion): den starter med et interval fra −99,99 % til 100 % (udvidet opad efter behov), og halverer, indtil nutidsværdien er praktisk talt nul. Har strømmene ikke både et negativt og et positivt led, eller skifter funktionen ikke fortegn i intervallet, er der intet tal.

MWR vises kun med mindst 365 dages historik (fast i koden): en årsrate fra få uger er mest støj. Er en strøms kroneværdi ukendt, vises intet MWR.

### ACWI med samme pengestrømme

Benchmarken er ACWI i kroner, startet i 100 ved første dags lukkekurs. Desuden beregner radaren "ACWI med samme pengestrømme": hver ekstern strøm køber eller sælger ACWI-andele til dagens lukkekurs. Det giver både en værdikurve og et MWR for ACWI, der kan sammenlignes direkte med dit eget MWR. Er en udbetaling større end ACWI-beholdningen på det tidspunkt, stopper serien med en note.

Ved sammenligning af flere porteføljer (A/B-test) startes alle på en fælles dato, hver fra sin værdi den dag, og alle indeks sættes til 100 dér (se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags)).

## Regneeksempel

En portefølje med kassebog og to store indbetalinger:

| Dato | Hændelse | Værdi efter |
|---|---|---|
| 3. jan. 2022 | Indbetaling 10.000 kr., investeret | 10.000 |
| 3. jan. 2023 | Værdien er steget 50 % | 15.000 |
| 3. jan. 2023 | Indbetaling 100.000 kr. | 115.000 |
| 3. jan. 2024 | Værdien er faldet 20 % | 92.000 |

**TWR.** To delperioder: +50 % og −20 %. $1.5 \cdot 0.8 - 1 = +20\,\%$ i alt, eller $1.2^{1/2} - 1 \approx 9.5\,\%$ om året. Papirerne klarede sig godt over de to år.

**MWR.** Du har sat 110.000 kr. ind og har 92.000 kr. Strømmene set fra din side: −10.000 (dag 0), −100.000 (dag 365), +92.000 (dag 730). Med $x = 1/(1+r)$:

$$
-10000 - 100000\,x + 92000\,x^2 = 0 \;\Rightarrow\; x = \frac{100000 + \sqrt{100000^2 + 4\cdot 92000\cdot 10000}}{2\cdot 92000} \approx 1.1791
$$

$r = 1/1.1791 - 1 \approx -15.2\,\%$ om året. Dine penge tabte, fordi langt de fleste af dem kom ind lige før faldet.

TWR og MWR har altså modsat fortegn: +9,5 % og −15,2 % om året. Begge er korrekte; de svarer på forskellige spørgsmål.

**ACWI med samme strømme.** Antag, at ACWI i kroner steg 10 % det første år og 5 % det andet. ACWI's TWR er $1.10 \cdot 1.05 - 1 = 15.5\,\%$, mod porteføljens 20 %: porteføljens papirvalg slog ACWI. Med samme strømme: $10000 \cdot 1.10 = 11000$, plus 100.000 giver 111.000, gange 1,05 giver 116.550 kr. ACWI's MWR løses som før: $-10000 - 100000\,x + 116550\,x^2 = 0$ giver $r \approx 5.4\,\%$ om året.

Konklusionen er nuanceret: dine valg slog ACWI (TWR 20 % mod 15,5 %), men med dine pengestrømme ville ACWI have efterladt dig med 24.550 kr. mere, fordi ACWI ikke faldt i det år, hvor de fleste penge var inde. Det er præcis den forskel, siden *Returns* viser ved at stille *TWR*, *MWR* og *ACWI with the same cash flows* ved siden af hinanden.

**En enkelt dag.** På indbetalingsdagen var værdien dagen før 15.000 kr. Lad os sige, at de 100.000 kr. først investeres ved lukketid, og at de gamle papirer steg 1 % den dag, så værdien ved lukketid er $15150 + 100000 = 115150$ kr. Radaren regner $115150 / (15000 + 100000) - 1 \approx 0.13\,\%$, ikke 1 %, fordi de 100.000 kr. regnes med fra dagens start, men stod som kontanter. Det er det kontantslæb, konventionen giver.

## Faldgruber og begrænsninger

- **TWR kræver værdier ved hver strøm.** Mangler en kurs på en dag med en strøm, kan dagens afkast ikke beregnes korrekt. Radaren udelader den dag og siger det, i stedet for at gætte.
- **Implicit finansiering har en pris.** Uden kassebog tæller hvert køb som nye penge og hvert salg som penge ud. Det er fint for TWR, men MWR og "ACWI med samme strømme" måler så dine handler, ikke dine reelle ind- og udbetalinger.
- **MWR er følsomt over for korte perioder og store sene strømme.** En stor indbetaling kort før slutdatoen dominerer resultatet. Derfor kræver radaren et års historik.
- **XIRR kan mangle eller være flertydig.** Med skiftende fortegn i strømmene kan der være flere renter, der opfylder ligningen. Radaren viser intet, når den ikke kan finde én.
- **Puljede porteføljer.** En puljet tag-gruppe lægger værdier og strømme sammen. Det er korrekt for afkast mod ACWI, men ikke for skat, hvor fx en aktiesparekonto opgøres for sig (se [Dansk skat for investorer](laerebog/skat)).
- **Skat og omkostninger.** Afkastet er før skat. Kurtage er med i handelsprisen via gebyret, men løbende omkostninger i fonde er kun med, i det omfang de er trukket i kursen.
- **Valuta.** Alt er i kroner. En del af forskellen til en udenlandsk benchmark i dollar er valuta, ikke papirvalg.

## Videre læsning

- CFA Institute, *Global Investment Performance Standards (GIPS) for Firms*, 2020.
- Carl R. Bacon, *Practical Portfolio Performance Measurement and Attribution*, 2. udg., Wiley, 2008.
- Ilia D. Dichev, "What Are Stock Investors' Actual Historical Returns? Evidence from Dollar-Weighted Returns", *American Economic Review* 97(1), 2007.
- Zvi Bodie, Alex Kane og Alan J. Marcus, *Investments*, McGraw-Hill (afsnittet om måling af porteføljeafkast).
