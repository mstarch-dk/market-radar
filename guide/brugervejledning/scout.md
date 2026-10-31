# Scout: hypoteser fra markedets snak

Radarens tal ser en trend, når den står i kurserne, estimaterne og regnskaberne. `/scout` kigger et skridt tidligere: på de historier, investorer, analytikere, politikere og medier er begyndt at fortælle. Det kan fx være kernekraft, sundhed i afrikanske lande eller elnettet. Claude søger på nettet, holder hver historie op mod radarens tal og giver dig en kort liste med 3–5 hypoteser, som du kan tage til dig, følge eller afvise.

Det er analyse, ikke rådgivning. En hypotese er en idé at undersøge, ikke en købsanbefaling. Hver kandidat fryses den dag, du ser den, og følges mod ACWI, så scoutens træfsikkerhed kan måles som alt andet i radaren.

## Sådan kører du den

Skriv `/scout` i Claude Code i programmappen. Med et stikord søger Claude snævrere:

- `/scout`: bredt, gennem alle søgevinklerne nedenfor
- `/scout kernekraft`: kun om ét tema
- `/scout forsvar --region europe --horizon 6m`: et tema, en region og en horisont

En kørsel tager typisk 5–15 minutter, fordi Claude søger bredt og slår hvert forslag op i radaren. Rapporten gemmes i `research/scout/ÅÅÅÅ-MM-DD.md` og kan læses under fanen *Research* på [Notebook](/notebook).

## Hvad Claude gør

1. **Læser din sammenhæng:** din investorprofil, dine [markedssyn](brugervejledning/markedssyn), rotationen, momentumlederne og deres klynger, estimatrevisionerne, positioneringen, [Discover](brugervejledning/discover) og de tidligere scout-rapporter. En kandidat, du har afvist før, kommer kun igen med nye argumenter, og Claude siger hvilke.
2. **Søger gennem faste vinkler**, så listen ikke bare bliver ugens højeste overskrift:
   - pengestrømme og nye ETF'er
   - fondsforvalterundersøgelser (BofA's *Fund Manager Survey*)
   - politik og offentlige penge
   - investeringsplaner og flaskehalse i forsyningskæder
   - bankers og kapitalforvalteres udsigter
   - godkendelser og teknologiske milepæle
   - vækst- og frontiermarkeder
   - råvarer
   - en kontrær vinkel: det upopulære, hvor tonen er ved at vende
3. **Laver en lang liste** med 8–12 historier. Hver får en vurdering af, hvem der fortæller den, hvor uafhængige kilderne er, om omtalen tager til, og hvad "faktum" er: den begivenhed, der vil bekræfte eller afslutte historien.
4. **Kobler hver historie til papirer:**
   - en eller to proxy-ETF'er, helst med en UCITS-udgave og med status på positivlisten, når den er kendt
   - 3–8 repræsentative aktier, slået op i radaren side om side med ACWI

   Claude tjekker også, om kurven i virkeligheden bare følger et tema, radaren allerede har, eller et af dine markedssyn.
5. **Giver point** og et stadie (se nedenfor), og lader en *red team* angribe hver kandidat.
6. **Viser dig den korte liste** og spørger, hvad du vil gøre med hver.

## Stadierne: købe på rygtet, sælge på nyheden

Det vigtigste, scouten fortæller, er ikke historien, men hvor langt den er i sit liv:

| Stadie | Kendetegn | Hvad det betyder |
|---|---|---|
| **Hvisken** | Omtalen vokser, men kursen og estimaterne har ikke fulgt med. Den relative styrke mod ACWI er flad eller svag, og temaet fører ikke. | Det interessante stadie, og det stadie, hvor man oftest tager fejl |
| **Bekræftes** | Historien, den relative styrke (forbedres eller fører) og estimatrevisionerne peger samme vej | Mindre at hente på rygtet, men mere evidens |
| **Konsensus** | Overalt i overskrifterne, nye tema-ETF'er, trængsel i positioneringen, en høj værdiansættelse, og katalysatoren er overstået eller kendt af alle | Et advarselsflag, ikke et køb |

Hvorfor konsensus er et advarselsflag, står i lærebogens kapitel [Rygter, opmærksomhed og fortællinger](laerebog/rygter-og-opmaerksomhed).

## Pointene

Hver kandidat får 1–5 point på syv akser, hver med en kort begrundelse. Mangler der data, står der n/a, aldrig et lavt tal.

| Akse | Spørgsmålet |
|---|---|
| Fortælling | Hvor stærk og bred er omtalen, og tager den til? |
| Kursbekræftelse | Er det allerede sket i kurserne? |
| Fundamental bekræftelse | Følger estimaterne og kursmålene med? |
| Trængsel | Er handlen allerede fuld (positionering, undersøgelser, værdiansættelse, ETF-lanceringer)? |
| Investerbarhed | Kan en dansk investor eje den (UCITS, positivlisten, likviditet)? |
| Katalysator | Kommer der et "faktum" med dato inden for horisonten? |
| Nyhed | Har du den ikke allerede gennem dine markedssyn eller beholdninger? |

Stadiet bestemmes af fortællingen holdt op mod kurser og revisioner, ikke af summen af pointene.

## Dine valg

For hver kandidat vælger du én af tre ting og skriver gerne en begrundelse med dine egne ord:

- **Adoptér:** kandidaten bliver et af dine [markedssyn](brugervejledning/markedssyn), med udsagn, overbevisning, horisont, hvad den hjælper og skader, indikatorer og hvad der ville få dig til at skifte mening. Claude viser først synet præcis, som det vil blive gemt, sammen med radarens evidens og eventuelle overlap med dine andre syn. Det gemmes først, når du siger ja. På siden *My market views* står det med mærket *from scout* og datoen.
- **Følg:** ikke noget markedssyn, men kandidaten fryses og følges.
- **Afvis:** kandidaten fryses og følges alligevel.

> **Bemærk:** De afviste følges med vilje. De er kontrolgruppen: kun ved at sammenligne dem med dem, du tog til dig, kan du se, om dine valg tilfører noget.

Til sidst spørger Claude, om beslutningerne skal skrives i journalen. Siger du ja, kommer der en post i `journal/ÅÅÅÅ-MM-DD-scout.md` med typen *hypotheses*, katalysatorerne og hvad der ville modbevise hver hypotese. `/journal review` gennemgår den ved næste månedlige gennemgang: er faktum indtruffet, er hypotesen modbevist, og hvordan har kurven klaret sig mod ACWI?

## Resultaterne

Hver frossen kandidat ligger i `exports/scout/` i din datamappe og bliver aldrig overskrevet eller tilbagedateret. Dens papirer kommer med i den daglige opdatering, så de altid har kurser.

- **Evidens-siden:** tabellen *Scout candidates* under [Resultaterne fremad](brugervejledning/scoretest#resultaterne-fremad) viser hver kandidats proxy-kurv mod ACWI fra dens dag.
- **Kommandolinjen:** `uv run radar scout review` viser det samme med gennemsnittet pr. valg (adopteret, fulgt, afvist) og pr. stadie (hvisken, bekræftes, konsensus).

Et gennemsnit vises først, når der er {{settings:evidence.scout_min}} kandidater i gruppen, der er mindst {{settings:evidence.cohort_age_months}} måneder gamle. Før det siger tallene intet.

## Månedsbriefen

[Månedsbriefen](brugervejledning/maanedsbrief) har en linje om scouten: hvornår den sidst kørte, kandidaterne og hvordan de frosne kandidater har klaret sig. Er det mere end en måned siden, foreslår den at køre `/scout` igen.

## Kilder og ophavsret

Claude læser kun overskrifter og gratis resuméer og går aldrig uden om en betalingsmur. Rapporten gemmer links og Claudes egne sammenfatninger, ikke artiklerne. Se [Datakilder og licenser](brugervejledning/datalicenser).

## Tips

- Kør den en gang om måneden, eller når et tema dukker op i briefen, og brug et stikord, når du har en mistanke, du vil have prøvet af.
- Tag hellere en hypotese til dig med lav overbevisning (2–3) og en skarp falsifikator end med høj overbevisning. Et markedssyn er en tese at holde øje med, ikke en handel.
- Vil du handle på en kandidat, så gå videre med `/research <ticker>`, `/compare` eller `/propose-portfolio`, og tjek dine [handelsregler](brugervejledning/handelsregler) først.
