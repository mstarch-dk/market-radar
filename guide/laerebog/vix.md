# VIX og volatilitetens terminsstruktur

## Intuition

En option er en forsikring. Køber du en salgsoption (put) på S&P 500, er du forsikret mod et fald. Som al forsikring stiger præmien, når folk er bange. Optionspriserne indeholder derfor markedets egen vurdering af, hvor meget kurserne vil svinge fremover: den *implicitte volatilitet*.

VIX er et indeks, der samler den implicitte volatilitet i S&P 500-optioner til ét tal: den forventede årlige volatilitet over de næste 30 dage. Det kaldes ofte "frygtindekset". En VIX på 12–15 betyder et roligt marked. En VIX på 30 eller mere betyder uro, og under akutte kriser (2008, marts 2020) har den været over 80.

Lige så interessant som niveauet er *formen*: forventer markedet mere uro på kort sigt end på lidt længere sigt? Normalt er den kortsigtede volatilitet lavere end den langsigtede, fordi der kan ske mere på tre måneder end på én. Når det vender, så den kortsigtede frygt er størst, er markedet i akut stress. Det er terminsstrukturen.

## Teori

### Implicit og realiseret volatilitet

*Realiseret* volatilitet er standardafvigelsen af de faktiske afkast bagud (se [Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown)). *Implicit* volatilitet er den volatilitet, der får en optionsprisingsmodel til at give den observerede markedspris. Den er fremadskuende og indeholder både forventningen om udsving og en præmie for at bære volatilitetsrisiko.

Implicit volatilitet ligger i gennemsnit *over* den efterfølgende realiserede volatilitet. Forskellen kaldes volatilitetsrisikopræmien (variance risk premium): investorer betaler for forsikring, ligesom husejere betaler mere for brandforsikring end den forventede skade (Carr og Wu, 2009; Bekaert og Hoerova, 2014).

### Hvordan VIX beregnes

Siden 2003 har Cboe beregnet VIX modelfrit, uden Black-Scholes. Metoden bygger på, at en portefølje af optioner over mange strikekurser kan replikere en *variansswap*: en kontrakt, der betaler den realiserede varians. For én udløbsdato med løbetid $T$ (i år) er den implicitte varians

$$
\sigma^2 = \frac{2}{T} \sum_i \frac{\Delta K_i}{K_i^2}\, e^{RT}\, Q(K_i) \;-\; \frac{1}{T}\left(\frac{F}{K_0} - 1\right)^2
$$

hvor $K_i$ er strikekurserne for out-of-the-money puts og calls, $\Delta K_i$ afstanden mellem nabostrikes, $Q(K_i)$ midtprisen på optionen, $R$ den risikofrie rente, $F$ terminskursen på indekset og $K_0$ den første strike under $F$. Leddet $1/K_i^2$ giver de lave strikes (forsikring mod krak) stor vægt.

Beregningen laves for de to udløb, der ligger nærmest omkring 30 dage, og variansen interpoleres til præcis 30 dage. VIX er kvadratroden, annualiseret og ganget med 100:

$$
\text{VIX} = 100 \cdot \sqrt{\sigma^2_{30\text{d}}}
$$

### Fra VIX til forventede udsving

VIX er en *årlig* volatilitet. For at få den forventede standardafvigelse over en kortere periode skaleres med kvadratroden af tiden:

$$
\sigma_{\text{periode}} \approx \frac{\text{VIX}}{100} \cdot \sqrt{\frac{\text{dage}}{365}}
$$

En praktisk tommelfingerregel er "16-reglen": VIX divideret med 16 (cirka $\sqrt{256}$, antal handelsdage om året) er den forventede daglige bevægelse i procent. En VIX på 16 svarer til daglige udsving på omkring 1 %.

### Typiske niveauer

VIX har siden 1990 haft et langsigtet gennemsnit omkring 19–20 og en median lidt lavere, fordi fordelingen er skæv: lange rolige perioder afbrudt af korte, voldsomme spring. Som grov orientering:

| VIX | Karakter |
|---|---|
| Under 12 | Meget roligt; ofte sene, lange optrends |
| 12–20 | Normalt |
| 20–30 | Forhøjet uro |
| Over 30 | Stress |
| Over 40 | Krise (2008, 2011, 2020; i august 2024 kortvarigt inden for dagen) |

De højeste lukkeværdier er omkring 80 i november 2008 og over 82 i marts 2020. Fordelingen betyder, at VIX ikke kan falde meget under sit normale niveau, men kan stige mange gange over det på få dage.

VIX vender tilbage mod sit gennemsnit (mean reversion), og hurtigere ovenfra end nedefra: efter et spring falder den typisk igen over uger, mens lave niveauer kan holde i måneder. Det er en af grundene til, at en høj VIX historisk oftere har været tæt på en kortsigtet bund end på starten af yderligere store fald, og at en meget lav VIX kan vare længe uden at betyde, at et fald er nært forestående.

### VIX3M og terminsstrukturen

Cboe beregner samme indeks for andre løbetider. VIX3M (tidligere VXV) bruger samme metode for cirka tre måneder (93 dage). Forholdet mellem de to beskriver volatilitetens terminsstruktur:

$$
\text{Terminsratio} = \frac{\text{VIX}}{\text{VIX3M}}
$$

| Ratio | Navn | Tolkning |
|---|---|---|
| Under 1 (typisk 0,8–0,9) | **Contango** (normal, opadgående) | Markedet forventer mere usikkerhed på længere sigt end lige nu: normal tilstand |
| Omkring 1 | Flad | Den kortsigtede uro har indhentet den langsigtede |
| Over 1 | **Backwardation** (inverteret) | Akut stress: frygten er størst på kort sigt |

Contango er normaltilstanden, fordi volatilitet vender tilbage mod sit gennemsnit (mean reversion): er den lav nu, forventes den at stige over tid. Inversion sker under udsalg, når investorerne betaler hvad som helst for forsikring de næste uger. Historisk har inversioner været kortvarige, og de har ofte faldet sammen med perioder tæt på kortsigtede bunde. Men en inversion kan vare i uger under en egentlig bjørnemarkedsfase (2008, 2022 i perioder).

### Hvorfor VIX er et regimesignal

VIX er negativt korreleret med aktiemarkedet: når S&P 500 falder, stiger VIX typisk, ofte uforholdsmæssigt meget. Det skyldes bl.a., at volatilitet stiger, når kurserne falder (gearingseffekten), og at efterspørgslen efter puts stiger. Høj VIX er derfor både et symptom på risk-off og en årsag til mere risk-off: mange institutionelle investorer styrer deres eksponering efter volatilitet (risikoparitet, volatilitetsmål) og sælger, når den stiger.

Whaley (2000) kaldte VIX "investor fear gauge", og navnet har hængt ved. Han understregede senere (Whaley, 2009), at VIX er fremadskuende og ikke en forudsigelse af retningen, kun af størrelsen af udsvingene.

## Sådan gør radaren

Radaren henter VIX (`^VIX`) og VIX3M (`^VIX3M`) som daglige lukkekurser fra Yahoo (`macro.yahoo` i `config/universe.yaml`). To rækker i afstemningen (`src/radar/signals/regime.py`):

**Volatility (VIX):**

- **risk-on**, hvis VIX er under {{settings:regime.vix_calm}} (`regime.vix_calm`),
- **risk-off**, hvis VIX er over {{settings:regime.vix_stress}} (`regime.vix_stress`),
- **neutral** ellers (grænserne selv medregnet).

**VIX term structure (VIX/VIX3M):**

- **risk-off**, hvis ratioen er over 1 (inverteret). Grænsen 1 ligger fast i koden, fordi den er definitionen på inversion.
- **risk-on**, hvis ratioen er under {{settings:regime.vix_term_calm}} (`regime.vix_term_calm`): en tydelig contango.
- **neutral** ellers (flad struktur).

Mangler en af serierne, bliver rækken *n/a*. Begge rækker har kilden "prices" og bliver *stale*, hvis den seneste kurs er mere end {{settings:coverage.max_age.prices}} dage ældre end rapportens dato.

På [Regime](/regime) ses VIX-grafen med linjer ved {{settings:regime.vix_calm}} og {{settings:regime.vix_stress}}, og terminsratioen med en linje ved 1. Se [brugervejledningen til regimet](brugervejledning/regime).

## Regneeksempel

**Hvad betyder en VIX på 20?** Den forventede årlige volatilitet er 20 %. Over 30 dage:

$$
0.20 \cdot \sqrt{\frac{30}{365}} = 0.20 \cdot 0.2867 = 0.0573
$$

altså en standardafvigelse på cirka 5,7 % over en måned. Under en normalfordeling ville S&P 500 med cirka 68 % sandsynlighed ligge inden for ±5,7 % om 30 dage. Pr. handelsdag: 20 / √252 = 20 / 15,87 ≈ 1,26 %. (Husk volatilitetsrisikopræmien: de realiserede udsving har i gennemsnit været lidt mindre.)

I eksemplerne nedenfor antages grænserne 18 og 25 for VIX og 0,9 for terminsratioen (din opsætning bruger i dag {{settings:regime.vix_calm}}, {{settings:regime.vix_stress}} og {{settings:regime.vix_term_calm}}).

**Situation A: uro, der bygger op.** VIX = 22, VIX3M = 20.

- VIX: 22 ligger mellem 18 og 25 → **neutral**.
- Ratio: 22 / 20 = 1,10 > 1 → **risk-off** (inverteret).

Niveauet er ikke alarmerende, men formen er: markedet betaler mere for forsikring den næste måned end for de næste tre. Terminsstrukturen fanger stress, før niveauet gør.

**Situation B: roligt marked.** VIX = 14, VIX3M = 17.

- VIX: 14 < 18 → **risk-on**.
- Ratio: 14 / 17 = 0,82 < 0,9 → **risk-on**.

**Situation C: efter chokket.** VIX = 27, VIX3M = 28. VIX er over 25 → **risk-off**, men ratioen 27 / 28 = 0,96 er under 1 og over 0,9 → **neutral**. Den akutte panik har lagt sig (strukturen er normaliseret), men niveauet er stadig højt. Det er typisk i dagene efter et udsalg.

## Faldgruber og begrænsninger

- **VIX er amerikansk.** Den måler S&P 500-optioner. Europæisk uro, der ikke smitter til USA, ses ikke. (Det europæiske modstykke, VSTOXX, er ikke i radaren.)
- **Lav VIX er ikke ufarlig.** Meget lav volatilitet kan bygge selvtilfredshed og gearing op. Februar 2018 ("Volmageddon") startede fra en VIX omkring 10–13. Radaren tæller lav VIX som risk-on, fordi det i gennemsnit er korrekt, ikke fordi det er sikkert.
- **VIX kan ikke købes.** Indekset kan ikke handles direkte. VIX-futures og ETP'er, der bygger på dem, taber typisk værdi over tid på grund af contango (de ruller dyrere kontrakter). Brug VIX som måler, ikke som investering.
- **Daglige spring.** VIX kan stige 50 % på én dag og falde igen. Ét dagstal kan vippe rækken frem og tilbage.
- **Implicit, ikke realiseret.** VIX indeholder en risikopræmie; den overvurderer i gennemsnit de faktiske udsving.
- **To rækker, samme kilde.** VIX og VIX/VIX3M er stærkt korrelerede: i stress stemmer de typisk begge risk-off. Det er to stemmer fra samme marked. Se [Radarens afstemningsmodel](laerebog/afstemningsmodellen).

## Videre læsning

- Cboe Global Markets: "Cboe Volatility Index (VIX) White Paper", https://www.cboe.com (metoden og formlerne).
- Whaley, R. E. (2000): "The Investor Fear Gauge", *Journal of Portfolio Management* 26(3).
- Whaley, R. E. (2009): "Understanding the VIX", *Journal of Portfolio Management* 35(3).
- Carr, P. og Wu, L. (2009): "Variance Risk Premiums", *Review of Financial Studies* 22(3).
- Bekaert, G. og Hoerova, M. (2014): "The VIX, the Variance Premium and Stock Market Volatility", *Journal of Econometrics* 183(2).
