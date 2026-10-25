# Formeloversigt

De vigtigste formler fra lærebogen samlet ét sted, med radarens egne valg af vinduer og tærskler. Hver formel har et link til kapitlet, der forklarer den. Notation: $P_t$ er (justeret) lukkekurs på dag eller uge $t$, $r_t$ et afkast, $B$ benchmarket (MSCI ACWI) og $n$ antal observationer. "Bar" er en række i radarens fælles kalender (i praksis hverdage).

## Afkast

Simpelt afkast og log-afkast ([Afkast og renters rente](laerebog/afkast)):

$$
r_t = \frac{P_t}{P_{t-1}} - 1, \qquad \ell_t = \ln\frac{P_t}{P_{t-1}} = \ln(1 + r_t)
$$

Afkast over et vindue på $k$ bars og radarens momentumhorisonter:

$$
r^{(k)} = \frac{P_t}{P_{t-k}} - 1, \quad k = 21,\ 63,\ 126 \quad (r_{1m},\ r_{3m},\ r_{6m})
$$

$$
r_{12\text{-}1} = \frac{P_{t-21}}{P_{t-252}} - 1
$$

Annualisering af et samlet afkast $R$ over $d$ dage (radaren viser først årlige tal med mindst ét års historik):

$$
r_{\text{år}} = (1 + R)^{365/d} - 1
$$

Relativt afkast mod ACWI, som radaren regner det (en forskel i procentpoint, ikke et forhold); se [Benchmark og relativt afkast](laerebog/benchmark) og [Relativ styrke](laerebog/relativ-styrke):

$$
\text{rel}^{(k)} = r_i^{(k)} - r_B^{(k)}
$$

## Trend og momentum

Simpelt glidende gennemsnit og radarens trendkrav ([Glidende gennemsnit og trend](laerebog/trend)):

$$
\text{SMA}_n(t) = \frac{1}{n}\sum_{j=0}^{n-1} P_{t-j}, \qquad \text{trend\_ok} \iff P_t > \text{SMA}_{200} \ \wedge\ \text{SMA}_{50} > \text{SMA}_{200}
$$

Momentumscore inden for en region, hvor $\operatorname{pct}(\cdot)$ er percentilrangen blandt regionens aktier ([Radarens momentumscore](laerebog/momentumscore)):

$$
\text{score} = 100 \cdot \frac{\operatorname{pct}(r_{12\text{-}1}) + \operatorname{pct}(r_{6m}) + \operatorname{pct}(r_{3m})}{3}
$$

Volumenstigning og afstand til 52-ugers toppen:

$$
\text{vol\_surge} = \frac{\overline{V}_{20}}{\overline{V}_{120}}, \qquad \text{from\_high} = \frac{P_t}{\max_{j<252} P_{t-j}} - 1
$$

## Tekniske indikatorer

Se [Tekniske indikatorer](laerebog/tekniske-indikatorer).

RSI med Wilders udjævning over 14 dage:

$$
\text{RSI} = 100 - \frac{100}{1 + \overline{U}/\overline{D}}
$$

MACD (12/26/9) og radarens måler:

$$
\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}, \quad \text{signal} = \text{EMA}_9(\text{MACD}), \quad \text{hist} = \text{MACD} - \text{signal}, \quad \frac{\text{hist}}{\text{ATR}}
$$

Bollinger-bånd (20 dage, 2σ) og %B:

$$
U, L = \text{SMA}_{20} \pm 2\sigma_{20}, \qquad \%B = \frac{P_t - L}{U - L}
$$

True range og ATR ($\alpha = 1/n$, $n$ = {{settings:stops.atr_days}} dage):

$$
\text{TR}_t = \max\big(H_t - L_t,\ |H_t - C_{t-1}|,\ |L_t - C_{t-1}|\big), \qquad \text{ATR}_t = \alpha\,\text{TR}_t + (1-\alpha)\,\text{ATR}_{t-1}
$$

Realiseret volatilitet (63 dages log-afkast, annualiseret):

$$
\sigma_{\text{år}} = \operatorname{sd}(\ell_{t-62..t}) \cdot \sqrt{252}
$$

## Rotation

Rotationsgrafen på ugentlige lukkekurser, vindue $w$ = {{settings:rotation.window}} uger ([Rotationsgrafen (RRG)](laerebog/rrg)):

$$
\text{RS}_t = \text{EWM}_{3}\!\left(\frac{P^i_t}{P^B_t}\right), \qquad
\text{RS-Ratio}_t = 100 \cdot \frac{\text{RS}_t}{\overline{\text{RS}}_{w}(t)}, \qquad
\text{RS-Momentum}_t = 100 \cdot \frac{\text{RS-Ratio}_t}{\text{EWM}_{\lfloor w/2 \rfloor}(\text{RS-Ratio})_t}
$$

Radarens rangering af ETF'er inden for en gruppe ([Relativ styrke](laerebog/relativ-styrke)):

$$
\text{rs\_score} = 0.2\,\text{rel}_{1m} + 0.4\,\text{rel}_{3m} + 0.4\,\text{rel}_{6m}
$$

## Regime

Nettoafstemning over de rækker, der stemmer ([Radarens afstemningsmodel](laerebog/afstemningsmodellen)):

$$
\text{net} = \frac{n_{\text{on}} - n_{\text{off}}}{n_{\text{on}} + n_{\text{off}}}, \qquad
\text{Risk-on} \iff \text{net} > 0.33, \quad \text{Risk-off} \iff \text{net} < -0.33
$$

Markedsbredde og nye højder minus nye bunde ([Markedsbredde](laerebog/markedsbredde)):

$$
\text{bredde} = 100 \cdot \frac{\#\{P > \text{SMA}_{200}\}}{\#\text{gyldige}}, \qquad
\text{NH-NL} = 100 \cdot \frac{\#\text{højder}_{252} - \#\text{bunde}_{252}}{\#\text{gyldige}} \ \text{(10 dages gennemsnit)}
$$

## Værdiansættelse

Se [P/E og indtjening pr. aktie](laerebog/pe-og-eps), [Relativ værdiansættelse](laerebog/relativ-vaerdiansaettelse) og [CAPE, risikopræmie og yield gap](laerebog/cape-og-risikopraemie).

$$
\text{P/E} = \frac{P}{\text{EPS}}, \qquad
\text{P/E mod sektor} = \frac{\text{P/E}_{fy1}}{\operatorname{median}_{\text{sektor}}(\text{P/E}_{fy1})}, \qquad
\text{P/E mod ACWI} = \frac{\text{P/E}_{\text{fond}}}{\text{P/E}_{\text{ACWI}}}
$$

$$
\text{yield gap} = \frac{100}{\text{P/E}_{\text{fremad}}} - r_{\text{real, 10 år}}
$$

Percentil af den seneste værdi $x_T$ mod historikken (CAPE, ERP, AAII, put/call; den seneste værdi selv tæller ikke med):

$$
\text{percentil} = 100 \cdot \frac{\#\{x_s < x_T : s < T\}}{\#\{s < T\}}
$$

EPS-revision og revisionsbredde ([Estimatrevisioner](laerebog/estimatrevisioner)):

$$
\Delta\text{EPS} = \frac{\text{EPS}^{fy1}_t}{\text{EPS}^{fy1}_{t-4\text{ uger}}} - 1, \qquad
\text{bredde} = \text{andel op} - \text{andel ned}
$$

## Positionering og sentiment

Nettoposition i procent af open interest ([Futurespositionering (CFTC COT)](laerebog/cot)):

$$
\text{netto \%OI} = 100 \cdot \frac{\text{long} - \text{short}}{\text{OI}}
$$

AAII's spænd og put/call ([Put/call og AAII: kontrær sentiment](laerebog/sentiment)):

$$
\text{spænd} = \%\text{bull} - \%\text{bear}, \qquad \text{P/C} = \frac{\text{put-volumen}}{\text{call-volumen}}
$$

## Risiko

Ugentlige DKK-afkast, overskudsafkast $x_t = r_t - r_f$ og annualisering med $\sqrt{52}$ ([Volatilitet, drawdown, Sharpe og Sortino](laerebog/volatilitet-og-drawdown)):

$$
\sigma_{\text{år}} = \operatorname{sd}(r)\sqrt{52}, \qquad
\text{Sharpe} = \frac{\bar{x}}{\operatorname{sd}(r)}\sqrt{52}, \qquad
\text{Sortino} = \frac{52\,\bar{x}}{\sqrt{\tfrac{1}{n}\sum \min(x_t, 0)^2}\ \sqrt{52}}
$$

Drawdown fra den hidtidige top:

$$
\text{DD}_t = \frac{W_t}{\max_{s \le t} W_s} - 1, \qquad \text{max drawdown} = \min_t \text{DD}_t
$$

Regression mod markedet ([Beta, alfa og faktorer](laerebog/beta-og-alfa)):

$$
x_{i,t} = \alpha + \beta\, x_{B,t} + \varepsilon_t, \qquad
\beta = \frac{\operatorname{cov}(x_i, x_B)}{\operatorname{var}(x_B)}, \qquad
\alpha_{\text{år}} = 52\,\alpha
$$

Porteføljens varians for to aktiver ([Diversifikation og korrelation](laerebog/diversifikation)):

$$
\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2 w_1 w_2 \rho_{12}\sigma_1\sigma_2
$$

Porteføljens risiko med dagens vægte ([Porteføljeforslag](laerebog/portefoeljeforslag#risiko-kovarians-med-shrinkage), [Røntgen af porteføljen](brugervejledning/xray)); $S$ er den målte ugentlige kovarians, $F$ samme volatiliteter med én fælles korrelation, $b$ ACWI:

$$
\hat\Sigma = \delta F + (1-\delta) S, \qquad
\sigma_p = \sqrt{52\, w^\top \hat\Sigma w}, \qquad
\beta_p = \frac{w^\top \hat\Sigma_{\cdot b}}{\hat\sigma_b^2}, \qquad
TE = \sqrt{52\,(w^\top \hat\Sigma w - 2\,w^\top \hat\Sigma_{\cdot b} + \hat\sigma_b^2)}
$$

Risikobidrag, marginalt risikobidrag og andel af den aktive risiko med $a = (w, -1)$ ([Diversifikation og korrelation](laerebog/diversifikation#risikobidrag-og-mctr), [Beta, alfa og faktorer](laerebog/beta-og-alfa#tracking-error-og-aktiv-risiko)):

$$
\text{andel}_i = \frac{w_i (\hat\Sigma w)_i}{w^\top \hat\Sigma w}, \qquad
\text{MCTR}_i = \frac{(\hat\Sigma w)_i}{\sqrt{w^\top \hat\Sigma w}}\sqrt{52}, \qquad
\text{aktiv andel}_i = \frac{a_i (\hat\Sigma a)_i}{a^\top \hat\Sigma a}
$$

Diversifikationsratio og effektivt antal positioner:

$$
DR = \frac{\sum_i w_i \sigma_i}{\sigma_p}, \qquad N_{\text{eff}} = \frac{1}{\sum_i w_i^2}
$$

## Stop og positionsstørrelse

Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse). Stop og take-profit med bredden $k$ (start {{settings:stops.k_base}}, mellem {{settings:stops.k_min}} og {{settings:stops.k_max}}):

$$
\text{stop} = \text{anker} - k \cdot \text{ATR}, \qquad
\text{take-profit} = \min\!\big(P_t + {{settings:stops.reward_risk|raw}}\,k\cdot\text{ATR},\ \text{gns. analytikerkursmål}\big)
$$

Positionsstørrelse efter risikobudget $b$ ({{settings:risk.budget|pct}} af porteføljen) og stopafstand $s$:

$$
\text{andel} = \frac{b}{s}, \qquad s = \frac{P_t - \text{stop}}{P_t}
$$

## Skat

Gennemsnitsmetoden i kroner, med kurs $p$, antal $q$, kurtage $k$ og valutakurs $x$ på handelsdagen ([Dansk skat for investorer](laerebog/skat#sådan-gør-radaren)):

$$
\text{anskaffelsessum} = \sum_{\text{køb}} (q\,p + k)\,x, \qquad \text{gevinst} = (q\,p - k)\,x - \frac{\text{anskaffelsessum}}{\text{beholdning}}\,q
$$

Lager pr. fond og år, og afkastet på en aktiesparekonto eller pensionskonto:

$$
\text{lager} = V_{slut} + \text{salg} - V_{start} - \text{køb}, \qquad \text{afkast} = V_{slut} - V_{start} - \text{indbetalt} + \text{udbetalt}
$$

Skat på aktieindkomst $S$ med progressionsgrænse $G$, og på kontoens afkast $A$ med sats $s$ og fremført negativ skat $N$:

$$
\text{skat} = {{tax:2026.share_income.low_rate|raw}} \min(S, G) + {{tax:2026.share_income.high_rate|raw}} \max(0, S - G), \qquad \text{skat}_{\text{konto}} = \max(0, s\,A - N)
$$

## Afkastmåling

Tidsvægtet afkast med indskud $I$ ved dagens start og udtræk $U$ ved dagens slutning, og pengevægtet afkast (XIRR) ([Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr)):

$$
1 + r_t = \frac{V_t + U_t}{V_{t-1} + I_t}, \qquad \text{TWR} = \prod_t (1 + r_t) - 1
$$

$$
\sum_j \frac{CF_j}{(1 + \text{XIRR})^{d_j/365}} = 0
$$
