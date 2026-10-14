# Rotationsgrafen (RRG)

## Intuition

En tabel med relative afkast fortæller, hvem der er stærk *nu*. Den fortæller ikke, hvor de er på vej hen. En sektor, der har slået markedet i et halvt år, men er begyndt at tabe pusten, ser stærk ud i tabellen længe efter, at toppen i den relative styrke er passeret. Og en sektor, der har været svag længe, men lige er begyndt at hente ind, ser stadig svag ud.

Rotationsgrafen (Relative Rotation Graph, RRG) løser det ved at vise to ting på én gang for hver sektor:

- **Hvor stærk** den relative trend mod benchmark er (vandret akse).
- **Om den bliver stærkere eller svagere** lige nu (lodret akse).

Hver sektor bliver et punkt med en hale, der viser de seneste ugers bane. Grafen deles i fire kvadranter: fører, svækkes, halter og forbedres. Det typiske forløb er, at en sektor bevæger sig rundt med uret: fra forbedres til fører, til svækkes, til halter og tilbage. Grafen gør det muligt at se mange sektorer samtidig og spotte dem, der er ved at skifte kvadrant.

Rotationsgrafen blev udviklet af den hollandske analytiker Julius de Kempenaer i begyndelsen af 2000'erne og blev kendt, da den kom på Bloomberg-terminalen. I dag er den udbredt i mange analyseplatforme.

## Teori

### RS-linjen som udgangspunkt

Grafen bygger på RS-linjen fra [Relativ styrke](laerebog/relativ-styrke):

$$
RS_i(t) = \frac{P_i(t)}{P_b(t)}
$$

RS-linjens niveau kan ikke sammenlignes på tværs af sektorer. Den skal derfor normaliseres, så alle sektorer kan stå i samme koordinatsystem omkring et fælles centrum på 100.

### RS-Ratio

RS-Ratio måler, **hvor stærk den relative trend er**. Ideen er at sammenligne RS-linjen med sit eget nylige niveau: ligger den over et glidende gennemsnit af sig selv, er sektoren i en relativ optrend. Tallet centreres på 100:

- Over 100: sektoren klarer sig bedre end benchmark, målt mod sin egen nylige norm.
- Under 100: den klarer sig dårligere.
- Afstanden fra 100 viser, hvor markant det er.

### RS-Momentum

RS-Momentum måler, **om den relative trend accelererer eller decelererer**. Det er momentum af RS-Ratio: ændringshastigheden, igen centreret på 100.

- Over 100: RS-Ratio stiger (den relative styrke tager til).
- Under 100: RS-Ratio falder (den relative styrke aftager).

RS-Momentum er en førende størrelse i forhold til RS-Ratio, ligesom hastighed går forud for position. Når en sektors relative styrke topper, falder RS-Momentum under 100, *før* RS-Ratio gør. Det er derfor, punkterne bevæger sig i cirkler.

### Kvadranterne

Med RS-Ratio på x-aksen og RS-Momentum på y-aksen giver de to 100-linjer fire kvadranter:

| Kvadrant (appen) | Dansk | RS-Ratio | RS-Momentum | Fortolkning |
|---|---|---|---|---|
| *Leading* | fører | > 100 | > 100 | Stærk relativ trend, der stadig tager til |
| *Weakening* | svækkes | > 100 | < 100 | Stadig stærk, men tempoet aftager |
| *Lagging* | halter | < 100 | < 100 | Svag relativ trend, der stadig forværres |
| *Improving* | forbedres | < 100 | > 100 | Stadig svag, men ved at hente ind |

### Rotationen med uret

Hvis den relative styrke svinger i bølger, giver det en bevægelse med uret: *Improving* → *Leading* → *Weakening* → *Lagging* → *Improving*. Matematisk er det samme fænomen som at tegne en sinusbølge mod dens egen afledte: positionen (RS-Ratio) halter en kvart periode efter hastigheden (RS-Momentum), og punktet kører rundt i en cirkel.

Men det er en tendens, ikke en lov. Almindelige undtagelser:

- **Krog tilbage.** En sektor i *Weakening* vender ofte op igen og går tilbage til *Leading* uden at passere *Lagging*. Det sker typisk i en stærk, vedvarende trend med en midlertidig pause. Tilsvarende kan en sektor i *Improving* falde tilbage til *Lagging*.
- **Lange ophold.** En sektor kan ligge i *Leading* eller *Lagging* i mange måneder, hvis den relative trend er stabil. Halen bliver så kort og samler sig.
- **Spring.** Et stort enkeltstående kursudsving (et opkøb, et resultat, et politisk chok) kan flytte et punkt diagonalt over grafen på en uge.
- **Støj tæt på centrum.** Punkter tæt på (100, 100) skifter kvadrant ofte uden at betyde noget. Afstanden fra centrum er lige så vigtig som kvadranten.

### Den kommercielle metode er ikke offentlig

De Kempenaers præcise formler for JdK RS-Ratio og JdK RS-Momentum er proprietære. Det, der er offentligt beskrevet, er princippet: RS-linjen normaliseres, så den kan sammenlignes på tværs af sektorer, centreres på 100, og momentum måles på den normaliserede serie. Den kommercielle version skalerer desuden akserne, så sektorer med forskellig volatilitet får sammenlignelige udsving. Alle gratis implementeringer, også radarens, er tilnærmelser, og tallene vil ikke stemme med dem, du ser på Bloomberg eller StockCharts. Kvadranten vil oftest stemme; de præcise koordinater gør det ikke.

## Sådan gør radaren

Rotationsgrafen beregnes i `rrg()` i `src/radar/signals/rotation.py`.

### Ugentlige data og udglatning

1. Udbyttejusterede dagslukkekurser samles til **ugentlige** kurser: den sidste lukkekurs i hver uge, med fredag som ugens dato (`W-FRI`). Uger uden benchmarkkurs droppes. Den igangværende uge bruger seneste lukkekurs og dateres højst til datoen for de nyeste data.
2. RS-linjen er ETF'ens ugekurs divideret med benchmarkens, **udglattet** med et eksponentielt glidende gennemsnit (EWM) med span 3, det vil sige vægt $\alpha = 2/(3+1) = 0.5$ på den nyeste uge. Det dæmper ugestøj.

### Formlerne i koden

Lad $W$ = `rotation.window` = {{settings:rotation.window}} uger. Med $\widetilde{RS}_t$ som den udglattede RS-linje:

$$
\text{RS-Ratio}_t = 100 \cdot \frac{\widetilde{RS}_t}{\frac{1}{W}\sum_{k=0}^{W-1} \widetilde{RS}_{t-k}}
$$

$$
\text{RS-Momentum}_t = 100 \cdot \frac{\text{RS-Ratio}_t}{\operatorname{EWM}_{\lfloor W/2 \rfloor}\left(\text{RS-Ratio}\right)_t}
$$

hvor $\operatorname{EWM}_s$ er et eksponentielt glidende gennemsnit med span $s$ og vægt $\alpha = 2/(s+1)$. Med $W$ = {{settings:rotation.window|raw}} er span'et halvdelen af vinduet, rundet ned.

Fortolket i ord:

- **RS-Ratio > 100** betyder præcis, at den udglattede RS-linje ligger over sit eget simple gennemsnit over de seneste $W$ uger.
- **RS-Momentum > 100** betyder præcis, at RS-Ratio ligger over sit eget eksponentielle gennemsnit.

Det er en **ratio til et glidende gennemsnit**, ikke en z-score. Kodens docstring beskriver akserne som "z-scored", men det gør beregningen ikke (docstringen er ved at blive rettet). Konsekvensen er vigtig: akserne er *ikke* skaleret efter volatilitet. En volatil temafond (fx uran eller halvledere) slår større cirkler i grafen end en rolig sektor som dagligvarer, og afstanden fra centrum kan ikke sammenlignes direkte på tværs af så forskellige fonde. Inden for en gruppe af ens instrumenter, fx de amerikanske sektorer, er det et mindre problem.

Grafen viser de seneste `rotation.tail` = {{settings:rotation.tail}} uger som hale. Kvadranten afgøres af det sidste punkt med `quadrant()`: begge værdier strengt over 100 for *Leading* osv. Mangler en af værdierne (for kort historik), bliver kvadranten *n/a*.

### Hjemmemarkedet som benchmark

Alle grupper måles mod ACWI. Europæiske sektorer måles **også** mod deres hjemmemarked, STOXX 600 (iShares-ETF'en EXSA.DE), fordi `eu_sectors` i `config/universe.yaml` har et eget `benchmark`. Det giver en ekstra graf og kolonnen *vs home mkt* (feltet `quadrant_local`).

Hvorfor begge? Mod ACWI blandes to ting sammen: om Europa som helhed klarer sig godt mod verden (inklusive valutaen, da EXSA.DE handles i euro og ACWI i dollar), og om netop denne sektor er stærk *inden for* Europa. Mod STOXX 600 er begge dele i euro, og du ser den rene sektoreffekt. Står europæiske banker i *Leading* mod STOXX 600 men i *Lagging* mod ACWI, er bankerne stærke i Europa, men Europa er svagt mod verden.

### I appen

Graferne ligger på [Sektorrotation](/rotation) (amerikanske og europæiske sektorer, regioner) og [Temaer og faktorer](/themes). Kolonnerne *RS-Ratio* og *RS-Mom* er skjult som standard i tabellen, men kan slås til; farverne i *Signals* graderes efter afstanden fra 100. Se [brugervejledningen til sektorrotation](brugervejledning/sektorrotation).

## Regneeksempel

Et forenklet eksempel med $W = 14$ uger, så RS-Momentum bruger span 7, altså α = 2/8 = 0,25.

**Uge 1: udglatning.** Sidste uges udglattede RS var 0,5180. Denne uges rå RS (ETF-kurs / ACWI-kurs) er 0,5300. Med $\alpha$ = 0,5:

$$
\widetilde{RS} = 0.5 \cdot 0.5300 + 0.5 \cdot 0.5180 = 0.5240
$$

**RS-Ratio.** Gennemsnittet af de seneste 14 ugers udglattede RS er 0,5150:

$$
\text{RS-Ratio} = 100 \cdot \frac{0.5240}{0.5150} = 101.75
$$

RS-linjen ligger 1,75 % over sit 14-ugers gennemsnit.

**RS-Momentum.** Sidste uges EWM af RS-Ratio var 100,88. Den opdateres:

$$
\operatorname{EWM} = 0.25 \cdot 101.75 + 0.75 \cdot 100.88 = 101.10
$$

$$
\text{RS-Momentum} = 100 \cdot \frac{101.75}{101.10} = 100.64
$$

Begge over 100: kvadranten er *Leading* (fører).

**Uge 2: et tilbageslag.** Den rå RS falder til 0,5150. Udglattet: 0,5 · 0,5150 + 0,5 · 0,5240 = 0,5195. Det 14-ugers gennemsnit er steget lidt til 0,5160 (en svag uge fra for 14 uger siden er faldet ud). Så:

- RS-Ratio = 100 · 0,5195 / 0,5160 = 100,68
- EWM = 0,25 · 100,68 + 0,75 · 101,10 = 100,995
- RS-Momentum = 100 · 100,68 / 100,995 = 99,69

RS-Ratio er stadig over 100, men RS-Momentum er faldet under: sektoren er gået fra *Leading* til *Weakening*. Bemærk, at ETF'en stadig klarer sig bedre end sin egen relative norm; det er tempoet, der er faldet. Om den fortsætter mod *Lagging* eller kroger tilbage til *Leading*, afhænger af de næste uger.

(I pandas beregnes EWM med `adjust=True`, som vægter alle tidligere observationer eksplicit. Efter nogle få spans er resultatet praktisk talt det samme som rekursionen ovenfor.)

## Faldgruber og begrænsninger

- **Det er en tilnærmelse.** Formlen er radarens egen, ikke JdK's. Sammenlign ikke koordinater med kommercielle RRG'er; kvadranter og retning er det, der kan overføres.
- **Ingen volatilitetsskalering.** Akserne er ratioer, ikke z-scorer. Volatile fonde fylder mere i grafen; tolk afstanden fra centrum inden for sammenlignelige instrumenter.
- **Forsinkelse.** Ugedata, EWM-udglatning og et gennemsnit over {{settings:rotation.window}} uger betyder, at et skift i relativ styrke først ses efter et par uger. Grafen er bygget til 1–6-måneders rotation, ikke til dagshandel.
- **Kvadranten er ikke et signal alene.** Overgangen fra *Improving* til *Leading* nævnes ofte som et tidligt tegn, men mange punkter kroger tilbage. Kombinér med de relative afkast, *Abs 3m*, trenden og [regimet](laerebog/risk-on-risk-off).
- **Benchmark bestemmer alt.** En sektor er kun "førende" i forhold til det, den måles mod. Skift benchmark, og kvadranten kan skifte. Derfor de to grafer for Europa.
- **Valuta.** Mod ACWI indgår valutabevægelser for alle fonde, der ikke handles i dollar. En stigende euro trækker europæiske fonde mod højre i ACWI-grafen, selv om intet er sket lokalt.
- **Relativ, ikke absolut.** Hele grafen kan være i et faldende marked. En sektor i *Leading* kan falde; den falder bare mindre end ACWI.
- **Startperiode.** RS-Ratio kræver {{settings:rotation.window}} ugers data, før den har en værdi. Nye fonde har ingen hale i starten.

## Videre læsning

- De Kempenaer, J.: RRG Research, https://relativerotationgraphs.com (metodens ophavsmand; forklaringer af kvadranter og rotation).
- StockCharts ChartSchool: "Relative Rotation Graphs (RRG Charts)", https://chartschool.stockcharts.com (gennemgang af læsning og typiske mønstre).
- Murphy, J. J. (1999): *Technical Analysis of the Financial Markets*, New York Institute of Finance (kapitlet om relativ styrke og intermarket-analyse).
- Moskowitz, T. J. og Grinblatt, M. (1999): "Do Industries Explain Momentum?", *Journal of Finance* 54(4).
