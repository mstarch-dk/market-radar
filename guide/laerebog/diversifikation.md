# Diversifikation og korrelation

## Intuition

"Læg ikke alle æggene i én kurv" er den ældste investeringsregel, og den eneste gratis frokost i finans, som det ofte siges. Når to investeringer ikke bevæger sig helt ens, udligner deres udsving delvist hinanden. Porteføljen svinger mindre end gennemsnittet af dens dele, uden at det forventede afkast falder.

Hvor meget du vinder, afhænger af **korrelationen**: hvor tæt investeringerne følges ad. Ti teknologiaktier er ikke ti uafhængige væddemål; de er nærmest ét. Ti aktier fra forskellige sektorer og lande er tættere på ti.

Tre ting gør diversifikation sværere, end den ser ud:

- Korrelationer stiger ofte, netop når du har brug for diversifikationen: i krak.
- Du kan eje det samme mange gange uden at vide det, fordi flere ETF'er har de samme store selskaber i toppen.
- Mange investorer har en stor andel i deres hjemland (home bias), som er en lille del af verdensmarkedet.

## Teori

### Korrelation

Korrelationskoefficienten mellem to afkastserier er kovariansen skaleret med de to standardafvigelser:

$$
\rho_{ij} = \frac{\operatorname{cov}(r_i, r_j)}{\sigma_i\,\sigma_j}, \qquad -1 \le \rho_{ij} \le 1
$$

$\rho = 1$ betyder, at de bevæger sig i fuld takt; $\rho = 0$, at der ingen lineær sammenhæng er; $\rho = -1$, at de bevæger sig modsat. Aktier har næsten altid positiv korrelation med hinanden, typisk 0,3–0,7 for enkeltaktier i samme marked og 0,8–0,95 for brede indeks. Se [Statistik for investorer](laerebog/statistik) for grundbegreberne.

### Porteføljens varians

Markowitz (1952) viste, at porteføljens varians med vægte $w_i$ er

$$
\sigma_p^2 = \sum_i \sum_j w_i w_j \sigma_i \sigma_j \rho_{ij}
$$

For to aktiver:

$$
\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2 w_1 w_2 \sigma_1 \sigma_2 \rho_{12}
$$

Er $\rho < 1$, er $\sigma_p$ mindre end det vægtede gennemsnit $w_1\sigma_1 + w_2\sigma_2$. Forskellen er diversifikationsgevinsten.

For en ligevægtet portefølje af $n$ aktiver med samme volatilitet $\sigma$ og samme parvise korrelation $\rho$ gælder:

$$
\sigma_p^2 = \sigma^2\left(\frac{1}{n} + \left(1 - \frac{1}{n}\right)\rho\right) \;\xrightarrow{\;n\to\infty\;}\; \rho\,\sigma^2
$$

Den første del, den aktiespecifikke risiko, forsvinder med $1/n$. Den anden, den fælles risiko, bliver tilbage. Med $\rho = 0.3$ kan du aldrig komme under $\sqrt{0.3} \approx 55\,\%$ af enkeltaktiernes volatilitet, uanset hvor mange aktier du ejer. Statman (1987) fandt, at det meste af gevinsten er hentet med 30–40 aktier; senere studier peger på flere, fordi den aktiespecifikke risiko er steget.

Det hænger sammen med opdelingen i [Beta, alfa og faktorer](laerebog/beta-og-alfa): idiosynkratisk risiko diversificeres væk, markedsrisikoen gør ikke.

### Diversifikationsratio

Choueifaty og Coignard (2008) definerer **diversifikationsratioen** som det vægtede gennemsnit af volatiliteterne divideret med porteføljens volatilitet:

$$
DR = \frac{\sum_i w_i \sigma_i}{\sigma_p} \ge 1
$$

$DR = 1$ betyder ingen diversifikation (alt korrelerer fuldt). Jo højere, jo mere af den enkelte risiko udligner hinanden. $DR^2$ kan tolkes som et omtrentligt "antal uafhængige væddemål".

### Koncentration

Et simpelt mål for, hvor koncentreret en portefølje er, er Herfindahl-indekset $HHI = \sum w_i^2$, og det **effektive antal positioner**:

$$
N_{eff} = \frac{1}{\sum_i w_i^2}
$$

Ti lige store positioner giver $N_{eff} = 10$. Har den største 40 %, falder tallet hurtigt. $N_{eff}$ ser kun på vægte, ikke på korrelationer, så ti energiaktier tæller som ti.

### Risikobidrag og MCTR

Vægten siger, hvor mange penge der står i en position, ikke hvor meget af udsvingene den står for. Med kovariansmatricen $\Sigma$ og vægtene $w$ er porteføljens varians $\sigma_p^2 = w^\top \Sigma w$, og den kan deles op i ét bidrag pr. position:

$$
\sigma_p^2 = \sum_i w_i (\Sigma w)_i, \qquad \text{andel}_i = \frac{w_i (\Sigma w)_i}{w^\top \Sigma w}
$$

$(\Sigma w)_i$ er positionens kovarians med hele porteføljen. Andelene summerer til 100 %. En volatil position, der svinger i takt med resten, får en andel langt over sin vægt; en position, der svinger mod resten, kan få en negativ andel.

Det **marginale risikobidrag** (MCTR, *marginal contribution to total risk*) er, hvor meget porteføljens volatilitet ændrer sig pr. ekstra vægtenhed i positionen:

$$
\text{MCTR}_i = \frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sigma_p}, \qquad \sum_i w_i\,\text{MCTR}_i = \sigma_p
$$

Den sidste ligning (Eulers sætning) siger, at bidragene lægger op til hele volatiliteten. En position med MCTR over $\sigma_p$ øger risikoen, hvis du køber mere af den; en position under sænker den. Ideen bag risikoparitet (Qian, 2005) er at give positionerne lige store risikobidrag i stedet for lige store vægte.

### Korrelationer i krise

Korrelationer er ikke konstante. Longin og Solnik (2001) viser, at korrelationen mellem internationale aktiemarkeder stiger markant i store fald, men ikke i store stigninger. Ang og Chen (2002) finder det samme for amerikanske aktieporteføljer. Det betyder, at en korrelation målt i rolige perioder overvurderer diversifikationen i netop de perioder, hvor den betyder mest. Downside beta (se [Beta, alfa og faktorer](laerebog/beta-og-alfa)) er en anden side af samme fænomen.

### Home bias

French og Poterba (1991) dokumenterede, at investorer i alle lande ejer langt flere hjemlige aktier, end deres vægt i verdensmarkedet tilsiger. Danmark udgør under 1 % af MSCI ACWI. En portefølje med halvdelen i danske aktier er derfor et meget stort, ofte ubevidst, væddemål på få selskaber og én sektorsammensætning. Det samme gælder sektor: en dansk portefølje er ofte tungt vægtet i sundhed og industri.

### Overlap mellem ETF'er

Flere ETF'er kan indeholde de samme selskaber. En global ETF, en amerikansk ETF og en teknologi-ETF har alle de største amerikanske teknologiselskaber i toppen. **Look-through** betyder at se igennem fondene til de underliggende beholdninger og lægge eksponeringen sammen:

$$
\text{eksponering}_{aktie} = w_{direkte} + \sum_{f} w_f \cdot h_{f,aktie}
$$

hvor $w_f$ er din vægt i fond $f$, og $h_{f,aktie}$ er aktiens vægt i fonden.

## Sådan gør radaren

### Korrelationsmatrix i sammenligninger

Skillen `/compare` (og `radar info T1 T2 …`) viser en korrelationsmatrix over de sammenlignede tickers og ACWI, med `--personal` også dine nuværende beholdninger. Den beregnes i `signals/risk.py` (`correlation`):

- Ugentlige afkast fra fredag til fredag, omregnet til kroner (uafsluttet uge udeladt).
- Vinduet er de seneste {{settings:risk.windows.1y}} uger.
- Hvert par beregnes på de uger, hvor begge har data (parvis komplet). Med færre end {{settings:risk.min_weeks}} fælles uger er feltet tomt; radaren gætter ikke.

Formålet er at se, om en ny kandidat faktisk tilføjer noget, eller bare er mere af det, du allerede ejer. En korrelation på 0,9 med en eksisterende beholdning betyder, at kandidaten mest øger koncentrationen.

### Markedssyn: hvem bevæger sig med hvem

Siden [My market views](/views) forbinder dine markedssyn med konkrete navne (se [Mine markedssyn](brugervejledning/markedssyn)). Et markedssyn kan have en eksponering mod en ETF, fx en halvleder-ETF. Et navn regnes for at "bevæge sig med" ETF'en, hvis korrelationen mellem deres ugentlige afkast *relativt til ACWI* er mindst 0,5 (`theme_corr` i `config/views.yaml`).

Detaljerne (`signals/views.py`):

- Ugentlige lukkekurser divideres med ACWI, og den ugentlige ændring i det forhold er det relative afkast. Der bruges kurser i hvert papirs egen noteringsvaluta, ikke kroner.
- Vinduet er de seneste 52 uger (fast i koden), og der kræves mindst 26 fælles uger (`min_weeks` i `config/views.yaml`, en anden indstilling end `risk.min_weeks`).
- Korrelationen på relative afkast fjerner den fælles markedsbevægelse. Ellers ville næsten alle aktier korrelere med næsten alle ETF'er, bare fordi markedet bevæger dem alle.
- Matcher et navn, vægtes eksponeringen med korrelationen (fx 0,7), og begrundelsen viser ρ. Er der for få fælles uger, er korrelationen ukendt, ikke "uden sammenhæng".

### Look-through på tickerprofilen

For en fond viser tickerprofilen kortet *Fund look-through* med fondens største beholdninger og sektorvægte fra Yahoo Finance. Beholdninger, du også ejer direkte, får mærket *you hold*. Det er den simpleste form for overlap-kontrol: ejer du både en ETF og dens største positioner, er din reelle eksponering mod dem større end din direkte vægt.

Profilen gennemlyser én fond ad gangen. For hele porteføljen gør røntgenbilledet det efter sektor, region og valuta (se nedenfor), men ikke ned til de enkelte aktier i fondene. Overlap mellem to fonde i den samme aktie må du stadig regne selv, fx som i eksemplet nedenfor.

### Porteføljens røntgen

Siden [X-ray](/xray) (se [Røntgen af porteføljen](brugervejledning/xray)) bruger teorien ovenfor på dine valgte porteføljer, i kroner og med dagens vægte (`xray.py`, med motoren i `portfolios/riskmodel.py`, den samme som porteføljeforslagene bruger):

- **Kovariansen** er beregnet på ugentlige afkast i kroner over {{settings:risk.covariance.history_weeks}} uger af beholdningerne og ACWI, med shrinkage ({{settings:risk.covariance.shrink|pct}} mod en fælles korrelation; se [Porteføljeforslag](laerebog/portefoeljeforslag#risiko-kovarians-med-shrinkage)). Papirer med færre end {{settings:risk.covariance.min_weeks}} uger er udeladt og vises med deres vægt.
- **Risikobidrag og MCTR** er formlerne ovenfor på vægtene blandt papirerne i modellen, annualiseret med $\sqrt{52}$. Ligger under {{settings:risk.xray.min_coverage|pct}} af værdien i modellen, vises ingen risikotal.
- **Diversifikationsratioen** er $DR$ ovenfor.
- **Koncentrationen** er $N_{eff}$ på positionernes vægte, de fem største positioners andel og den position, der har det største risikobidrag. En verdensfond tæller som én position, så $N_{eff}$ undervurderer spredningen; derfor vises andelen i verdensfonde.
- **Par, der bevæger sig sammen**, er beholdninger med en ugentlig korrelation over {{settings:risk.xray.pair_corr}} i samme vindue (`signals/risk.py`, `correlation`, parvis komplet), med deres samlede vægt.
- **Eksponeringen** efter sektor, region og valuta gennemlyser fondene, hvor data tillader det, og viser for hver dimension, hvor stor en del af værdien der kunne placeres. En fond, der ikke kan gennemlyses, bliver aldrig fordelt efter gæt.

### Lofter pr. navn og tema

Et loft ("ingen aktie over 10 %", "AI-chips højst 25 %") er den enkleste form for diversifikation: det sætter en grænse for, hvor meget ét selskab eller ét tema kan trække porteføljen ned. Det tager ikke højde for korrelation, så to navne under hvert sit loft kan stadig bevæge sig som ét; temaloftet tæller derfor også de aktier, der bevæger sig med temaets ETF i forhold til ACWI. Dine egne lofter skriver du på [Trading rules](/rules), og radaren viser, hvad et køb gør ved vægten, og det største beløb, der er plads til: med beholdning $h$, samlet investeret værdi $V$ og loft $p$ er det $(pV - h)/(1-p)$. Se [Mine handelsregler](brugervejledning/handelsregler).

### Værdi og momentum side om side

Asness, Moskowitz og Pedersen (2013) fandt, at værdi- og momentumstrategier er negativt korrelerede, omkring −0,5, i mange markeder: når den ene halter, klarer den anden sig ofte godt. Radarens [A/B-test](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum) undersøger det fremad i tid med tre virtuelle kurve (kvalitet+værdi, momentum og 50/50) og viser korrelationen mellem deres ugentlige afkast i DKK, når der er mindst {{settings:risk.min_weeks}} uger. Den viser også, om blandingen svinger mindre end hver kurv alene. Begge kurve er lange aktiekurve, så de vil være positivt korrelerede med markedet og med hinanden. Spørgsmålet er, hvor meget mindre end 1 korrelationen er.

## Regneeksempel

### To aktiver

Aktie A har en årlig volatilitet på 20 %, aktie B 30 %. Du har 50 % i hver.

**Med $\rho = 0.3$:**

$$
\sigma_p^2 = 0.25\cdot 0.04 + 0.25\cdot 0.09 + 2\cdot 0.25\cdot 0.3\cdot 0.2\cdot 0.3 = 0.0100 + 0.0225 + 0.0090 = 0.0415
$$

$\sigma_p = \sqrt{0.0415} \approx 20.4\,\%$. Det vægtede gennemsnit er 25 %, så diversifikationsratioen er $25/20.4 \approx 1.23$. Porteføljen svinger næsten ikke mere end den roligste aktie alene.

**Med $\rho = 0.9$:** krydsleddet bliver $2\cdot 0.25\cdot 0.9\cdot 0.06 = 0.027$, $\sigma_p^2 = 0.0595$, $\sigma_p \approx 24.4\,\%$ og $DR \approx 1.03$. Næsten ingen gevinst.

### Mange aktiver

Ligevægtede aktier, hver med 30 % volatilitet og parvis korrelation 0,3:

| Antal | $\sigma_p$ |
|---|---|
| 1 | 30,0 % |
| 10 | $30\,\% \cdot \sqrt{0.1 + 0.9\cdot 0.3} = 30\,\% \cdot \sqrt{0.37} \approx 18.2\,\%$ |
| 30 | $30\,\% \cdot \sqrt{0.0333 + 0.9667\cdot 0.3} \approx 17.1\,\%$ |
| ∞ | $30\,\% \cdot \sqrt{0.3} \approx 16.4\,\%$ |

Fra 10 til uendeligt mange aktier vinder du kun 1,8 procentpoint. Hvis korrelationen i et krak stiger til 0,7, bliver grænsen $30\,\% \cdot \sqrt{0.7} \approx 25.1\,\%$.

### En lille position med stor risiko

En portefølje har 95 % i en bred fond med volatilitet $\sigma_f = 15\,\%$ og 5 % i én aktie med $\sigma_a = 60\,\%$. Korrelationen er $\rho = 0.6$. Positionernes kovarians med porteføljen:

$$
(\Sigma w)_a = 0.05 \cdot 0.36 + 0.95 \cdot 0.6 \cdot 0.60 \cdot 0.15 = 0.0180 + 0.0513 = 0.0693
$$

$$
(\Sigma w)_f = 0.95 \cdot 0.0225 + 0.05 \cdot 0.6 \cdot 0.60 \cdot 0.15 = 0.0214 + 0.0027 = 0.0241
$$

Variansen er $0.05 \cdot 0.0693 + 0.95 \cdot 0.0241 = 0.00347 + 0.02287 = 0.02634$, så $\sigma_p \approx 16.2\,\%$. Aktiens andel af risikoen er $0.00347 / 0.02634 \approx 13\,\%$: 5 % af pengene, 13 % af udsvingene. Dens MCTR er $0.0693 / 0.162 \approx 43\,\%$, langt over porteføljens 16,2 %. Hver procentpoint mere i aktien øger porteføljens volatilitet med omkring 0,43 procentpoint, mens fondens MCTR på $0.0241 / 0.162 \approx 15\,\%$ ligger under.

### Koncentration og overlap

En portefølje har vægtene 40 %, 30 %, 20 % og 10 %. $HHI = 0.16 + 0.09 + 0.04 + 0.01 = 0.30$, så $N_{eff} = 1/0.30 \approx 3.3$. Fire positioner, men koncentrationen svarer til lidt over tre lige store.

Antag, at positionen på 40 % er en global ETF, hvor en stor teknologiaktie vejer 5 %, positionen på 20 % er en teknologi-ETF, hvor samme aktie vejer 12 %, og du ejer aktien direkte med 10 %. Look-through:

$$
0.10 + 0.40\cdot 0.05 + 0.20\cdot 0.12 = 0.10 + 0.020 + 0.024 = 0.144
$$

Din reelle eksponering mod den ene aktie er 14,4 %, ikke de 10 %, du ser i oversigten.

## Faldgruber og begrænsninger

- **Korrelation er ikke stabil.** Et års ugentlige data giver et estimat med betydelig usikkerhed (med 52 observationer er standardfejlen på en korrelation omkring 0,1–0,14), og den skifter med regimet. I krak stiger den.
- **Korrelation måler kun lineær samvariation.** To aktiver kan have lav korrelation i normale uger og alligevel falde sammen i ekstreme uger.
- **Valuta.** Radarens korrelationsmatrix er i kroner, mens markedssynets korrelationer er i lokal valuta relativt til ACWI. De besvarer forskellige spørgsmål: den første "svinger min formue sammen?", den anden "har de samme relative drivkræfter?".
- **Look-through er ufuldstændig.** Yahoo viser kun fondens største beholdninger. Den lange hale af små positioner ses ikke, og data kan være flere måneder gamle.
- **Mange positioner er ikke det samme som diversifikation.** Ti positioner i samme tema eller samme faktor (fx momentum, som ofte samler sig i få sektorer) er reelt få væddemål.
- **Diversifikation koster også.** Mere diversifikation betyder et afkast tættere på markedet. Den, der vil slå ACWI, må acceptere en vis koncentration; spørgsmålet er, om den er bevidst og dimensioneret (se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse)).

## Videre læsning

- Harry Markowitz, "Portfolio Selection", *Journal of Finance* 7(1), 1952.
- Meir Statman, "How Many Stocks Make a Diversified Portfolio?", *Journal of Financial and Quantitative Analysis* 22(3), 1987.
- Kenneth R. French og James M. Poterba, "Investor Diversification and International Equity Markets", *American Economic Review* 81(2), 1991.
- François Longin og Bruno Solnik, "Extreme Correlation of International Equity Markets", *Journal of Finance* 56(2), 2001.
- Andrew Ang og Joseph Chen, "Asymmetric Correlations of Equity Portfolios", *Journal of Financial Economics* 63(3), 2002.
- Yves Choueifaty og Yves Coignard, "Toward Maximum Diversification", *Journal of Portfolio Management* 35(1), 2008.
- Clifford Asness, Tobias Moskowitz og Lasse Heje Pedersen, "Value and Momentum Everywhere", *Journal of Finance* 68(3), 2013.
