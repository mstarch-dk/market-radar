# Radarens kvalitets- og værdiscore

Kvalitetsscoren og værdiscoren er radarens bud på spørgsmålene fra [Kvalitet og værdi](laerebog/kvalitet-og-vaerdi): er det en god forretning, og er prisen rimelig? Begge er tal fra 0 til 100, regnet ud fra selskabernes regnskaber, og begge siger, hvor en aktie ligger blandt sammenlignelige aktier. K+V er gennemsnittet af de to. Kapitlet gennemgår præcis, hvad koden gør.

## Intuition

En aktie får ikke point for et højt tal i sig selv. En overskudsgrad på 20 % er meget for et supermarked og lidt for et softwarehus. Derfor sammenligner radaren hver aktie med aktier i samme sektor, på tværs af regionerne, og spørger: hvor stor en del af dem har et dårligere tal?

Kvalitetsscoren samler fire søjler:

- **Lønsomhed:** hvor meget frit cash flow selskabet laver pr. krone omsætning, og hvor meget overskud det tjener på den kapital, der er bundet i det.
- **Holdbarhed:** hvor stabil bruttoavancen er år for år, og hvor jævnt omsætningen er vokset. En moat efterlader spor i regnskabet: stabile marginer og jævn vækst.
- **Balance:** hvor tung gælden er i forhold til indtjeningen, og hvor let renterne betales.
- **Udbytterække:** hvor mange år i træk udbyttet ikke er sat ned.

Værdiscoren ser på prisen fire måder: frit cash flow og EBIT i forhold til, hvad selskabet koster, hvor meget der sendes tilbage til aktionærerne, og om prisen lige nu er høj eller lav i forhold til selskabets egne seneste år.

## Teori

### Percentiler blandt sammenlignelige

For hvert nøgletal $x$ og hver aktie $i$ er percentilen andelen af sammenlignelige aktier med et dårligere tal:

$$
p_i = 100 \cdot \frac{\#\{j : x_j < x_i\}}{n}
$$

hvor $n$ er antallet af sammenlignelige aktier med tallet (aktien selv medregnet). Det er samme regel som i [momentumscoren](laerebog/momentumscore). For nøgletal, hvor lavt er godt (gæld, udsving), vendes fortegnet først.

### Fra percentiler til score

En søjle er gennemsnittet af percentilerne for dens nøgletal. Kvalitetsscoren er det vægtede gennemsnit af de søjler, der kan regnes:

$$
K = \frac{\sum_s w_s \, \bar p_s}{\sum_s w_s}
$$

med vægtene {{settings:fundamentals.quality.weights.profitability|pct}} (lønsomhed), {{settings:fundamentals.quality.weights.durability|pct}} (holdbarhed), {{settings:fundamentals.quality.weights.balance|pct}} (balance) og {{settings:fundamentals.quality.weights.record|pct}} (udbytterække). Værdiscoren er på samme måde det vægtede gennemsnit af værdinøgletallene: FCF yield {{settings:fundamentals.value.weights.fcf_yield|pct}}, EBIT/EV {{settings:fundamentals.value.weights.ebit_ev|pct}}, shareholder yield {{settings:fundamentals.value.weights.shareholder_yield|pct}} og EBIT/EV mod egen historik {{settings:fundamentals.value.weights.ey_vs_history|pct}}.

Ligesom momentumscoren klumper scorerne sig om midten: et gennemsnit af percentiler er sjældent tæt på 0 eller 100.

## Sådan gør radaren

### Data

Regnskaberne kommer fra SEC EDGAR for amerikanske selskaber og fra Yahoo for alle de aktier, radaren følger (se [Regnskaber](brugervejledning/data-og-daekning#regnskaber)). Et selskab regnes på én kilde, aldrig en blanding: EDGAR, når det har omsætning, driftsresultat, pengestrøm fra driften, anlægsinvesteringer og aktiver, ellers Yahoo. Scorerne regnes, når rapporten bygges, og uden at hente noget fra nettet.

**De seneste 12 måneder (TTM).** Pengestrømme og resultater tages over de seneste 12 måneder: regnskabsåret, når det netop er afsluttet; ellers året til dato plus det seneste regnskabsår minus samme periode året før (EDGAR); ellers fire kvartaler lagt sammen, Yahoos egen 12-månederskolonne (selskaber, der aflægger halvårsregnskab) eller regnskabsåret (Yahoo). Ender de seneste tal for mere end {{settings:fundamentals.ttm_max_age_days}} dage siden, bruges de ikke.

**Markedsværdi.** Seneste antal aktier gange seneste lukkekurs, regnet om til regnskabsvalutaen med radarens egne valutakurser (Shell handles i pence og aflægger regnskab i dollar). Afviger det rapporterede antal aktier meget fra det udvandede antal (under {{settings:fundamentals.shares_low}} eller over {{settings:fundamentals.shares_high}} gange), bruges det udvandede; det sker for selskaber med flere aktieklasser. Ligger resultatet mere end {{settings:fundamentals.mcap_check|pct}} fra Yahoos markedsværdi, bruges Yahoos, og det noteres. Uden kurs, aktieantal eller valutakurs regnes værdinøgletallene ikke.

### Nøgletallene

| Søjle | Nøgletal | Sådan |
|---|---|---|
| Lønsomhed | FCF-margin | (pengestrøm fra driften − anlægsinvesteringer) / omsætning |
| | ROIC | EBIT × (1 − skattesats) / gennemsnitlig investeret kapital |
| Holdbarhed | Spredning i bruttoavance | standardafvigelsen af den årlige bruttoavance (procentpoint) over de seneste {{settings:fundamentals.stability_years}} regnskabsår; lavere er bedre |
| | Jævn vækst | fortegnet på trenden gange $R^2$ for log(omsætning) mod tid over de samme år |
| Balance | Nettogæld / EBITDA | lavere er bedre; nettokontanter er bedst |
| | Rentedækning | EBIT / renteudgifter, højst {{settings:fundamentals.interest_cover_cap}} |
| Udbytterække | År uden nedsættelse | år i træk med et udbytte pr. aktie på mindst 95 % af året før |
| Værdi | FCF yield | frit cash flow / markedsværdi |
| | EBIT/EV | EBIT / (markedsværdi + gæld − kontanter + minoritetsinteresser + præferenceaktier) |
| | Shareholder yield | (udbytte + aktieopkøb − nyudstedelser) / markedsværdi |
| | EBIT/EV mod egen historik | dagens EBIT/EV som percentil blandt selskabets egne regnskabsår de seneste {{settings:fundamentals.ey_history_years}} år |

Detaljer, der ligger fast i koden:

- **Skattesatsen** er skat / resultat før skat, mellem 0 og 40 %; med underskud før skat bruges 25 %.
- **Investeret kapital** er aktiver − kontanter − (kortfristede forpligtelser − kortfristet gæld). Den virker også for selskaber med negativ egenkapital (efter store aktieopkøb). Gennemsnittet er af i dag og et år før.
- **Uden en linje for vareforbrug** måles holdbarheden på driftsmarginen i stedet, og det noteres.
- **Med underskud** er rentedækningen 0, og EBIT/EV bliver negativ og rangerer lavt i stedet for at falde ud. Ingen renteudgift og næsten ingen gæld (højst 5 % af aktiverne) giver loftet.
- **Udbyttet** læses af kurserne: på en ex-dag falder forholdet mellem justeret og handlet kurs med udbyttet. Kun hele kalenderår tæller. En aktie, der ikke betaler udbytte, får 0, som er et rigtigt tal; uden kurshistorik er rækken ukendt.
- **Holdbarhed og egen historik** kræver mindst {{settings:fundamentals.min_fy_points}} regnskabsår og mindst {{settings:fundamentals.ey_history_min_points}} punkter (dagen i dag medregnet). Det seneste regnskabsår må højst være {{settings:fundamentals.annual_max_age_days}} dage gammelt.
- **Urimelige tal** (uden for intervallerne i `fundamentals.ranges`, fx en FCF-margin over 100 %) er en enhedsfejl eller en datafejl. De udelades med en note, aldrig erstattet af 0.

### Banker og forsikringsselskaber

Pengestrøm, EV og EBIT giver ikke mening for en bank, hvor gæld er råvaren. Selskaber i bankernes, forsikringsselskabernes og realkreditinstitutternes brancher (`fundamentals.financial_industries`) måles derfor på:

- **Kvalitet:** egenkapitalforrentning (ROE), spredningen i ROE over årene, egenkapital / aktiver og udbytterækken.
- **Værdi:** bogført værdi / kurs, indtjening / kurs, shareholder yield og indtjening / kurs mod egen historik.

De rangeres kun mod hinanden. Visa, Mastercard, børser og kapitalforvaltere er i sektoren *Financial Services*, men har ikke en banks balance, og måles som alle andre.

### Sammenlignelige aktier

Peers er aktierne på radarens fire regionale lister med samme sæt nøgletal (almindeligt eller finansielt). For hvert nøgletal bruges sektoren, når mindst {{settings:fundamentals.min_sector_peers}} aktier i den har tallet, ellers hele sættet. En aktie uden for listerne (en beholdning eller en på watchlisten) rangeres mod listerne uden at flytte deres percentiler.

### Hvornår der er en score

- **Kvalitetsscore:** mindst {{settings:fundamentals.quality.min_pillars}} af de fire søjler, og lønsomheden skal være blandt dem.
- **Værdiscore:** mindst {{settings:fundamentals.value.min_components}} af de fire værdinøgletal, og FCF yield eller EBIT/EV skal være blandt dem.
- **K+V:** kun når begge findes.

Ved siden af scoren står, hvor mange søjler og værdinøgletal den bygger på. Det adskiller sig bevidst fra momentumscoren, hvor et manglende afkast betyder ingen score: regnskaber har flere huller end kurser, og det er bedre at se et tal med færre dele end slet intet. En manglende værdi er aldrig 0.

### Hvor du ser det

I denne version ligger scorerne i rapporten (`dashboard.json`) og i de rækker, appen henter til momentum og dine beholdninger, i afsnittet `quality` i `uv run radar info TICKER` og i `summary.json`, som Claude-skills læser (`quality_top10` pr. region). Hver uge gemmes scorerne også som historik.

## Regneeksempel

Et selskab har de seneste fire kvartaler en omsætning på 1.000, EBIT 200, resultat før skat 200, skat 40, pengestrøm fra driften 200, anlægsinvesteringer 50, afskrivninger 50 og renteudgifter 20. Balancen: aktiver 1.000, kontanter 100, kortfristede forpligtelser 200, kortfristet gæld 50, langfristet gæld 300. Markedsværdien er 2.000.

- FCF = 200 − 50 = 150, så FCF-marginen er 150 / 1.000 = 15 %.
- Skattesatsen er 40 / 200 = 20 %. Investeret kapital = 1.000 − 100 − (200 − 50) = 750. ROIC = 200 × 0,8 / 750 ≈ 21,3 %.
- Nettogæld = 50 + 300 − 100 = 250, EBITDA = 200 + 50 = 250, så nettogæld / EBITDA = 1,0.
- Rentedækning = 200 / 20 = 10.
- FCF yield = 150 / 2.000 = 7,5 %. EV = 2.000 + 350 − 100 = 2.250, så EBIT/EV ≈ 8,9 % (EV/EBIT = 11,25).

Er ROIC'en bedre end 6 af 8 andre softwareselskabers, er dens percentil 75 (6 af 8 sammenlignelige, selskabet selv medregnet, har et lavere tal). Har lønsomhedens to nøgletal percentil 75 og 55, er lønsomhedssøjlen 65. Med holdbarhed 50, balance 70 og en ukendt udbytterække (kort kurshistorik) bliver kvalitetsscoren

$$
K = \frac{0.35 \cdot 65 + 0.25 \cdot 50 + 0.25 \cdot 70}{0.35 + 0.25 + 0.25} = \frac{52.75}{0.85} \approx 62
$$

på tre af fire søjler.

## Faldgruber og begrænsninger

- **Regnskabsregler.** Under IFRS 16 (Europa) står leasing som gæld, og leasingudgiften ligger under afskrivninger og renter. Det gør EBITDA højere og nettogælden større end for et tilsvarende amerikansk selskab. Sammenligning inden for sektoren dæmper det, men fjerner det ikke.
- **Yahoo viser omkring fire år.** For selskaber uden EDGAR bygger holdbarhed og egen historik på få år i starten. Antallet af søjler ved scoren viser det.
- **Halvårsregnskaber.** Mange europæiske selskaber aflægger kun regnskab hvert halve år, så deres tal er op til et halvt år ældre end amerikanernes.
- **Engangsposter** (nedskrivninger, salg af forretninger) indgår i EBIT og pengestrøm, som de er rapporteret. Et enkelt år kan trække et nøgletal skævt.
- **Udbytterækken** er kort, fordi kurshistorikken er det: højst så mange år, som radaren har kurser for.
- **Negativ egenkapital** giver ingen ROE for en bank. For andre selskaber bruger ROIC aktiverne, så tallet findes stadig.
- **Overlevelsesbias.** Listerne er dagens selskaber. Et regnskab, der så godt ud, før selskabet gik ned, er ikke med.
- **Scoren er en sammenligning, ikke en vurdering.** En værdiscore på 80 betyder billig i forhold til sektoren, ikke billig i sig selv. Er hele sektoren dyr, er dens billigste aktie det også.

## Videre læsning

- Robert Novy-Marx, "The Other Side of Value: The Gross Profitability Premium" (2013).
- Clifford Asness, Andrea Frazzini og Lasse Heje Pedersen, "Quality Minus Junk" (2019).
- Joel Greenblatt, *The Little Book That Beats the Market* (2005).
- Aswath Damodaran, "Return on Capital (ROC), Return on Invested Capital (ROIC) and Return on Equity (ROE): Measurement and Implications" (2007).
