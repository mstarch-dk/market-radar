# Volatilitet, drawdown, Sharpe og Sortino

## Intuition

To investeringer kan have samme gennemsnitlige afkast og alligevel føles vidt forskellige at eje. Den ene stiger roligt et par procent om året; den anden svinger 30 % op og ned undervejs. Risiko handler om den vej, du går for at nå målet, og om hvor langt nede du kan risikere at stå, når du har brug for pengene eller bare mister modet.

Dette kapitel samler fire mål, der hver beskriver en side af den vej:

- **Volatilitet**: hvor meget afkastet typisk svinger fra uge til uge, omregnet til et år.
- **Downside-risiko**: kun de svingninger, der gør ondt, altså afkast under en grænse.
- **Drawdown**: det største fald fra en top, og hvor længe du stod under toppen (tid under vand).
- **Sharpe og Sortino**: afkast pr. enhed risiko, så to investeringer med forskellig risiko kan sammenlignes.

Ingen af dem forudsiger fremtiden. De beskriver fortiden, og deres værdi ligger i at gøre risikoen konkret og sammenlignelig, før du beslutter, hvor stor en position skal være (se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse)).

## Teori

### Volatilitet

Volatilitet er standardafvigelsen af periodeafkast. Med $n$ ugentlige simple afkast $r_1, \dots, r_n$ og gennemsnittet $\bar r$:

$$
\sigma_{uge} = \sqrt{\frac{1}{n-1}\sum_{t=1}^{n} (r_t - \bar r)^2}
$$

For at kunne sammenligne mål fra forskellige frekvenser omregnes til årlig volatilitet. Hvis afkastene er uafhængige fra periode til periode, vokser variansen proportionalt med tiden, og standardafvigelsen med kvadratroden af tiden:

$$
\sigma_{år} = \sigma_{uge}\cdot\sqrt{52} \qquad \sigma_{år} = \sigma_{dag}\cdot\sqrt{252}
$$

52 er antal uger og 252 det typiske antal handelsdage om året. Kvadratrodsreglen er en tilnærmelse: hvis afkastene har positiv autokorrelation (trends), undervurderer den den langsigtede risiko, og ved negativ autokorrelation (mean reversion) overvurderer den den. Lo (2002) viser, hvordan det også påvirker Sharpe-tal. Grundbegreberne standardafvigelse og varians gennemgås i [Statistik for investorer](laerebog/statistik).

Ugentlige afkast har to fordele frem for daglige: de er mindre påvirket af, at børser i forskellige tidszoner lukker på forskellige tidspunkter (asynkron handel), og de er mindre støjfyldte for mindre likvide aktier. Prisen er færre observationer.

### Downside-risiko

Volatilitet straffer store stigninger lige så meget som store fald. Mange investorer bekymrer sig kun om faldene. **Downside deviation** (nedsidestandardafvigelse) måler kun afkast under et mindste acceptabelt afkast (MAR, *minimum acceptable return*), ofte 0 eller den risikofrie rente:

$$
\sigma_{ned} = \sqrt{\frac{1}{N}\sum_{t=1}^{N} \min(r_t - \text{MAR},\, 0)^2}
$$

Bemærk, at der divideres med alle $N$ perioder, ikke kun de negative. Perioder over MAR tæller som nul. Det er den definition, Sortino og Price (1994) bruger, og den giver et mål, der kan sammenlignes på tværs af investeringer med forskellig andel af dårlige uger.

### Drawdown og tid under vand

Lad $W_t = \prod_{s \le t}(1 + r_s)$ være formuen, når der startes med 1. Drawdown på tidspunkt $t$ er faldet fra den hidtil højeste formue:

$$
DD_t = \frac{W_t}{\max_{s \le t} W_s} - 1 \qquad \text{MaxDD} = \min_t DD_t
$$

Maksimal drawdown er det værste fald fra top til bund i perioden. **Tid under vand** er antallet af perioder i træk, hvor formuen ligger under en tidligere top. Det er ofte det mål, der bedst forklarer, hvorfor investorer giver op: et fald på 30 % er slemt, men fire år uden at nå den gamle top igen er det, der tærer på tålmodigheden.

Husk asymmetrien: et fald på $d$ kræver en stigning på $\frac{1}{1-d} - 1$ for at komme tilbage. 20 % fald kræver 25 % stigning; 50 % fald kræver 100 %.

Maksimal drawdown afhænger kraftigt af periodens længde: jo længere du måler, jo dybere bliver den værste drawdown typisk (Magdon-Ismail og Atiya, 2004). To aktiers MaxDD kan derfor kun sammenlignes over samme periode.

### Sharpe og Sortino

**Sharpe-tallet** (Sharpe, 1966; 1994) er gennemsnitligt merafkast over den risikofrie rente $r_f$ divideret med standardafvigelsen af merafkastet:

$$
S = \frac{\overline{r - r_f}}{\sigma(r - r_f)}\cdot\sqrt{52}
$$

Faktoren $\sqrt{52}$ kommer af, at tælleren skaleres med 52 og nævneren med $\sqrt{52}$. Et Sharpe-tal på 0,5 over mange år er typisk for et bredt aktieindeks; over et enkelt år kan tallet være næsten hvad som helst.

**Sortino-tallet** erstatter nævneren med downside deviation, med den risikofrie rente som MAR:

$$
\text{Sortino} = \frac{\overline{r - r_f}\cdot 52}{\sigma_{ned}\cdot\sqrt{52}}
$$

Sortino belønner investeringer, hvis svingninger mest er opad. For et symmetrisk fordelt afkast er Sortino cirka $\sqrt{2}$ gange Sharpe, fordi kun den ene halvdel af svingningerne tæller i nævneren.

Sharpe-tallets statistiske usikkerhed er stor. Med uafhængige normalfordelte afkast er standardfejlen på det årlige Sharpe-tal omtrent $\sqrt{(1 + S^2/2)/T}$, hvor $T$ er antal år (Lo, 2002). Med ét års data er standardfejlen altså omkring 1, og et Sharpe-tal på 0,8 kan ikke skelnes fra 0.

### Annualiseret afkast

Det geometriske, annualiserede afkast over $n$ uger er:

$$
R_{år} = \left(\prod_{t=1}^{n}(1 + r_t)\right)^{52/n} - 1
$$

Det er den årlige rente, der ville have givet samme slutformue (se [Afkast og renters rente](laerebog/afkast)). Over korte perioder bliver tallet ekstremt, fordi et par gode uger opløftes til en hel årsrate.

## Sådan gør radaren

Risikotallene beregnes i `signals/risk.py` og vises på tickerprofilen i kortet *Risk vs ACWI (DKK, weekly)* (se [Tickerprofilen](brugervejledning/tickerprofil)).

**Data.** Radaren bruger ugentlige simple afkast fra fredagens lukkekurs, omregnet til danske kroner, fordi det er det afkast, en dansk investor faktisk oplever (se [Justerede kurser, udbytter og valuta](laerebog/justerede-kurser)). En uge, der stadig er i gang, udelades, fordi den dækker færre dage end de andre.

**Vinduer.** Tallene beregnes over de seneste {{settings:risk.windows.1y}} og {{settings:risk.windows.3y}} uger (cirka 1 og 3 år, `risk.windows` i `settings.yaml`). Hvert vindue oplyser, hvor mange uger det faktisk brugte. Med færre end {{settings:risk.min_weeks}} uger (`risk.min_weeks`) er der intet tal; radaren gætter aldrig.

**Risikofri rente.** Radaren bruger den 3-måneders amerikanske statsrente (FRED-serien DGS3MO, i procent om året) og omregner den til en ugentlig rente:

$$
r_{f,uge} = \left(1 + \frac{r_{\%}}{100}\right)^{1/52} - 1
$$

Renten er en dollarrente, mens afkastene er i kroner. Det er en bevidst forenkling: det giver et fast, gennemsigtigt nulpunkt, men en dansk investor ville i praksis have en anden kontantrente. Mangler serien, beregnes Sharpe og Sortino ikke (de vises som tomme), og alfa i [Beta, alfa og faktorer](laerebog/beta-og-alfa) beregnes på rå afkast.

**Formlerne, som koden bruger dem:**

- Volatilitet: $\sigma_{år} = \text{std}(r)\cdot\sqrt{52}$ (stikprøvestandardafvigelse, $n-1$ i nævneren).
- Annualiseret afkast: $\prod(1+r_t)^{52/n} - 1$.
- Sharpe: $\overline{r - r_f} \,/\, \text{std}(r) \cdot \sqrt{52}$.
- Sortino: $\overline{r - r_f}\cdot 52 \,/\, \left(\sqrt{\sum \min(r_t - r_{f,t}, 0)^2 / N}\cdot\sqrt{52}\right)$, med alle $N$ uger i nævneren.
- Drawdown: $\min_t\left(W_t / \max_{s\le t} W_s - 1\right)$ på ugeformuen, og den længste række uger i træk under en top.

> **Bemærk:** Lærebogens Sharpe-tal dividerer med standardafvigelsen af *merafkastet* $r - r_f$. Radaren dividerer med standardafvigelsen af det *rå* afkast $r$. Forskellen er alene variationen i den risikofrie rente fra uge til uge. Med en 3-måneders statsrente, der kun bevæger sig langsomt, er den næsten konstant inden for et vindue, og forskellen ligger typisk i tredje decimal. Hvis renten var helt konstant, ville de to være identiske.

Kortet viser også *Max drawdown (weeks under)*: den dybeste drawdown og i parentes den længste periode under vand i uger. Drawdown er her beregnet på ugelukkekurser, så et fald, der startede og sluttede midt i en uge, ses ikke fuldt ud.

**Andre steder i appen.** Kortet med tekniske indikatorer viser en 3-måneders volatilitet (*vol_3m*) fra daglige log-afkast over 63 handelsdage, annualiseret med $\sqrt{252}$, og en 1-års drawdown fra daglige kurser i lokal valuta. Siden [Returns](/returns) viser volatilitet og maksimal drawdown for hele porteføljer, beregnet på det daglige tidsvægtede indeks og annualiseret med $\sqrt{252}$ (se [Tidsvægtet og pengevægtet afkast](laerebog/twr-og-mwr)). Tallene kan derfor afvige fra risikokortets ugentlige tal for samme papir; de måler det samme med forskellig opløsning og valuta.

## Regneeksempel

Otte ugers afkast i kroner (alt for få til at radaren ville vise et tal, men nok til at regne i hånden):

| Uge | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Afkast | +2 % | −1 % | +3 % | −4 % | +1 % | +2 % | −2 % | +1 % |
| Formue | 1,0200 | 1,0098 | 1,0401 | 0,9985 | 1,0085 | 1,0286 | 1,0081 | 1,0182 |
| Drawdown | 0 | −1,0 % | 0 | −4,0 % | −3,0 % | −1,1 % | −3,1 % | −2,1 % |

**Volatilitet.** Gennemsnittet er 0,25 % om ugen. Stikprøvestandardafvigelsen er 2,375 %. Årlig volatilitet: $0.02375 \cdot \sqrt{52} = 0.02375 \cdot 7.211 \approx 17.1\,\%$.

**Annualiseret afkast.** Formuen ender i 1,0182, altså +1,82 % på otte uger. Annualiseret: $1.0182^{52/8} - 1 \approx 12.4\,\%$. Det er et godt eksempel på, hvorfor korte vinduer er farlige: otte uger ophøjes til et helt år.

**Drawdown.** Toppen efter uge 3 (1,0401) nås ikke igen. Det dybeste punkt er uge 4: $0.9985/1.0401 - 1 = -4.0\,\%$. Fra uge 4 til uge 8 står formuen under toppen, så den længste tid under vand er 5 uger (uge 2 er et enkelt ugelangt dyk).

**Risikofri rente.** Antag en statsrente på 4 % om året: $1.04^{1/52} - 1 \approx 0.0755\,\%$ om ugen. Gennemsnitligt merafkast: $0.25\,\% - 0.0755\,\% = 0.1745\,\%$ om ugen.

**Sharpe.** $0.001745 / 0.02375 \cdot 7.211 \approx 0.53$. Fordi renten her er konstant, er standardafvigelsen af merafkastet præcis den samme som af det rå afkast, og lærebogens og radarens Sharpe giver samme tal.

**Sortino.** Merafkastene under nul er uge 2, 4 og 7: −1,075 %, −4,075 % og −2,075 %. Kvadratsummen er $0.000116 + 0.001661 + 0.000431 = 0.002207$. Divideret med alle 8 uger: $0.000276$, kvadratrod $1.661\,\%$. Annualiseret: $1.661\,\% \cdot 7.211 = 11.98\,\%$. Årligt merafkast: $0.1745\,\% \cdot 52 = 9.08\,\%$. Sortino $= 9.08 / 11.98 \approx 0.76$.

Sortino er højere end Sharpe, fordi de store positive uger ikke tæller som risiko. Men med otte uger er begge tal uden statistisk værdi: standardfejlen på Sharpe er her flere gange større end tallet selv.

## Faldgruber og begrænsninger

- **Korte vinduer.** Et års Sharpe-tal har en standardfejl omkring 1. Sammenlign altid 1- og 3-årsvinduet, før du lægger vægt på et af dem.
- **Volatilitet er ikke det samme som risiko for permanent tab.** En aktie med lav historisk volatilitet kan falde 80 % på en enkelt nyhed (konkurs, regnskabsskandale). Historiske tal fanger ikke risici, der ikke har vist sig endnu.
- **Fede haler.** Aktieafkast har flere ekstreme uger end normalfordelingen forudsiger. Volatilitet og Sharpe undervurderer derfor halerisikoen; drawdown fanger den bedre, men kun hvis den faktisk skete i perioden.
- **Udjævnede priser.** Illikvide aktier og fonde med sjældne handler ser roligere ud, end de er, fordi kursen halter efter. Ugentlige afkast mindsker problemet, men fjerner det ikke.
- **Valuta.** Tallene er i kroner. En amerikansk aktie har både aktierisiko og dollarrisiko; i perioder, hvor dollaren falder, når aktier falder, kan kronevolatiliteten være lavere end dollarvolatiliteten.
- **Sharpe-tal kan manipuleres.** Strategier, der sælger forsikring (fx skrevne optioner), kan vise høje Sharpe-tal i årevis indtil et stort tab. Sortino og drawdown er værd at se sammen med Sharpe.
- **Sammenlign over samme periode.** MaxDD og Sharpe fra forskellige perioder kan ikke sammenlignes; et vindue, der rammer et krak, ligner et helt andet papir.

## Videre læsning

- William F. Sharpe, "Mutual Fund Performance", *Journal of Business* 39(1), 1966.
- William F. Sharpe, "The Sharpe Ratio", *Journal of Portfolio Management* 21(1), 1994.
- Frank A. Sortino og Lee N. Price, "Performance Measurement in a Downside Risk Framework", *Journal of Investing* 3(3), 1994.
- Andrew W. Lo, "The Statistics of Sharpe Ratios", *Financial Analysts Journal* 58(4), 2002.
- Malik Magdon-Ismail og Amir F. Atiya, "Maximum Drawdown", *Risk* 17(10), 2004.
- Zvi Bodie, Alex Kane og Alan J. Marcus, *Investments*, McGraw-Hill (kapitlerne om risiko og afkast).
