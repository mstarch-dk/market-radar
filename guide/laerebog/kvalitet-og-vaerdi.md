# Kvalitet og værdi: Graham, Buffett og Grantham

Momentum spørger, hvad markedet har gjort med en aktie. Kvalitet og værdi spørger om selve forretningen: tjener selskabet sine penge, kan det blive ved, og hvad koster det? Det er den tradition, der går fra Benjamin Graham over Warren Buffett til Jeremy Grantham, og den har sin egen forskning bag sig. Kapitlet forklarer ideerne og evidensen. [Radarens kvalitets- og værdiscore](laerebog/kvalitetsscore) viser, hvordan radaren gør dem til tal.

## Intuition

En aktie er en andel af en virksomhed. Over mange år følger aktiens afkast virksomhedens indtjening og de penge, den sender tilbage til ejerne. To spørgsmål afgør derfor meget:

- **Er det en god forretning?** Den tjener mange penge på den kapital, der er bundet i den. Den laver mere kontant overskud, end den bruger på at vedligeholde sig selv. Den har noget, konkurrenter ikke let kopierer (en *moat*, en voldgrav: brand, netværk, skift-omkostninger, lave omkostninger). Den kan klare en dårlig periode uden at skulle låne eller udstede aktier.
- **Er prisen rimelig?** Selv den bedste forretning er en dårlig investering, hvis man betaler for meget. Prisen måles i forhold til de penge, forretningen faktisk genererer.

Graham lagde vægten på prisen: køb med en sikkerhedsmargin, så der er plads til at tage fejl. Buffett flyttede vægten mod kvaliteten med sin kendte formulering om, at det er bedre at købe et fremragende selskab til en rimelig pris end et rimeligt selskab til en fremragende pris. Grantham og hans firma GMO har i årtier argumenteret for, at priser vender tilbage mod det, forretningen kan bære, og at kvalitetsselskaber historisk har givet mere afkast med mindre risiko, end teorien siger, de burde.

Momentum og værdi trækker ofte i hver sin retning: momentum køber det, der er steget, og værdi køber det, der er blevet billigt. Netop derfor kan de supplere hinanden i en portefølje.

## Teori

### Værdipræmien

Fama og French (1992) viste, at aktier med høj bogført værdi i forhold til kursen (*value*) over lange perioder gav mere afkast end aktier med lav (*growth*). Forskellen kaldes HML (*high minus low*). Andre mål for billighed, fx indtjening eller pengestrøm i forhold til kursen, giver et lignende billede.

Der er to forklaringer, som ikke udelukker hinanden: billige aktier er mere risikable (de er ofte billige, fordi noget er galt), eller investorer overreagerer og ekstrapolerer dårlige nyheder for langt. Fra omkring 2007 til 2020 klarede value-aktier sig markant dårligere end growth-aktier, den længste svage periode i dataene. Præmien er altså ikke noget, man kan regne med år for år.

En del af forklaringen på den svage periode er, at bogført værdi passer dårligt til moderne selskaber: udgifter til forskning, software og brands bogføres som omkostninger og står ikke som aktiver. Pengestrøm og indtjening i forhold til selskabets samlede værdi (EV) rammer bedre på tværs af brancher.

### Kvalitet og lønsomhed

Novy-Marx (2013) fandt, at bruttoavance i forhold til aktiver (*gross profitability*) forudsiger afkast næsten lige så godt som bogført værdi i forhold til kurs, og at de to virker bedst sammen: lønsomme selskaber er ofte dyre, så en strategi, der kræver både lønsomhed og en rimelig pris, får det bedste fra begge.

Fama og French (2015) føjede en lønsomhedsfaktor (RMW, *robust minus weak*) til deres model. Asness, Frazzini og Pedersen (2019) samlede kvalitet i ét mål, *Quality minus Junk* (QMJ), af lønsomhed, vækst, sikkerhed (lav gæld, stabil indtjening) og udbytte til aktionærerne, og fandt, at kvalitetsaktier gav højere risikojusteret afkast og især holdt bedre i dårlige markeder.

Et nøgletal for lønsomhed er afkastet på den investerede kapital:

$$
\text{ROIC} = \frac{\text{EBIT} \times (1 - \text{skattesats})}{\text{investeret kapital}}
$$

Et selskab med en ROIC langt over sine kapitalomkostninger skaber værdi med hver krone, det investerer. En ROIC, der holder sig høj år efter år, er et af de bedste tegn på en moat.

### Frit cash flow og pris

Frit cash flow (FCF) er de penge, forretningen laver, efter den har betalt for at vedligeholde og udbygge sig selv:

$$
\text{FCF} = \text{pengestrøm fra driften} - \text{anlægsinvesteringer}
$$

Det er sværere at pynte på end regnskabets overskud, fordi det er faktiske penge. FCF i forhold til markedsværdien (*FCF yield*) er en nøgtern pris: hvor stor en del af det, du betaler, kommer tilbage som kontanter hvert år?

Greenblatts *magic formula* (2005) rangerer aktier på to tal, ROIC og EBIT i forhold til selskabets samlede værdi (EV = markedsværdi + gæld − kontanter), og tager dem, der samlet set ligger bedst. Det er Buffetts idé i sin enkleste form: en god forretning til en rimelig pris.

### Penge tilbage til ejerne

Udbytte og opkøb af egne aktier er to måder at sende penge tilbage på. *Shareholder yield* lægger dem sammen og trækker nyudstedte aktier fra. En lang række år uden udbyttenedsættelse siger noget om både forretningens stabilitet og ledelsens disciplin.

### Værdi og momentum sammen

Asness, Moskowitz og Pedersen (2013) fandt værdi- og momentumpræmier i otte forskellige markeder og aktivklasser, og at de to er klart negativt korrelerede med hinanden, omkring −0,5. En portefølje med begge svinger derfor mindre end hver for sig. Det er hovedgrunden til, at radaren har en kvalitets- og værdiscore ved siden af momentumscoren: ikke fordi den ene er bedre, men fordi de ser forskellige ting.

## Sådan gør radaren

Radaren regner to scorer fra 0 til 100 ud fra selskabernes regnskaber: en kvalitetsscore (lønsomhed, holdbarhed, balance og udbytterække) og en værdiscore (FCF yield, EBIT/EV, shareholder yield og prisen mod selskabets egen historik). Banker og forsikringsselskaber måles på deres egne nøgletal. Alt om metoden, data og tærskler står i [Radarens kvalitets- og værdiscore](laerebog/kvalitetsscore).

## Faldgruber og begrænsninger

- **Værdifælden.** En aktie kan være billig, fordi forretningen er ved at gå i stykker. Lav pris alene er ikke en sikkerhedsmargin. Derfor kombinerer radaren pris med kvalitet.
- **Lange svage perioder.** Både værdi og kvalitet kan halte efter markedet i mange år. En faktor, der har virket i 50 år, kan have et svagt årti.
- **Regnskaber er bagudskuende.** De beskriver det seneste år, ikke det næste. Et selskab med en stærk historik kan miste sin moat.
- **Forskellige regnskabsregler.** Amerikanske selskaber følger US GAAP, europæiske IFRS. Leasing, forskning og engangsposter behandles forskelligt, så de samme tal betyder ikke altid det samme.
- **Opkøb af egne aktier** kan finansieres med gæld. En høj shareholder yield er ikke altid et sundhedstegn.

## Videre læsning

- Benjamin Graham, *The Intelligent Investor* (1949, revideret 1973).
- Warren Buffett, brevene til Berkshire Hathaways aktionærer (særligt 1977–1992), berkshirehathaway.com.
- Eugene Fama og Kenneth French, "The Cross-Section of Expected Stock Returns", *Journal of Finance* (1992).
- Robert Novy-Marx, "The Other Side of Value: The Gross Profitability Premium", *Journal of Financial Economics* (2013).
- Clifford Asness, Andrea Frazzini og Lasse Heje Pedersen, "Quality Minus Junk", *Review of Accounting Studies* (2019).
- Clifford Asness, Tobias Moskowitz og Lasse Heje Pedersen, "Value and Momentum Everywhere", *Journal of Finance* (2013).
- Joel Greenblatt, *The Little Book That Beats the Market* (2005).
- Jeremy Grantham, GMO's kvartalsbreve, gmo.com.
