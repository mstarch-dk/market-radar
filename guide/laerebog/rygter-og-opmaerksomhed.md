# Rygter, opmærksomhed og fortællinger

## Intuition

"Køb på rygtet, sælg på nyheden" er et af de ældste ordsprog på markedet. Kurser bevæger sig, når forventninger ændrer sig, ikke når begivenheder sker. Når en historie begynder at sprede sig, fx at elnettet skal udbygges, at små atomreaktorer bliver godkendt eller at et land åbner sit kapitalmarked, flytter de første penge sig, længe før tallene viser noget. Når begivenheden så indtræffer, er den ofte allerede i kursen, og de tidlige købere sælger til de sene.

Det giver en livscyklus for en investeringsfortælling:

1. **Hvisken:** få taler om den, og kursen har ikke reageret.
2. **Bekræftelse:** flere taler om den, kurserne og estimaterne begynder at følge med.
3. **Konsensus:** alle taler om den, der lanceres ETF'er, og forventningerne er høje.
4. **Faktum:** begivenheden indtræffer, og den efterfølgende skuffelse eller "sell the news" kommer.

Radarens momentum- og rotationsmål ser fortællingen i fase 2 og 3. [Scouten](brugervejledning/scout) forsøger at se den i fase 1, og især at advare, når den er i fase 3.

## Teori

### Opmærksomhed flytter kurser, kortvarigt

Investorer kan ikke følge alt, så de køber det, der fanger deres opmærksomhed. Barber og Odean (2008) viser, at private investorer er nettokøbere af aktier, der er i nyhederne, har usædvanlig handel eller ekstreme afkast. De sælger derimod det, de i forvejen ejer. Da, Engelberg og Gao (2011) måler opmærksomhed med søgninger på Google: mere søgning efter en aktie giver højere kurs de næste to uger, men den løft vender delvist igen inden for et år. Opmærksomhed skubber kursen, men skubbet er ikke værdi.

### Medier og stemning

Tetlock (2007) finder, at en usædvanlig negativ tone i en daglig spalte i *Wall Street Journal* trykker markedet den næste dag, og at faldet vender tilbage inden for en uge. Det tyder på stemning, ikke ny information. Tonen i medierne er altså et signal om, hvad andre tror, ikke om hvad der er sandt.

### Fortællinger spreder sig som epidemier

Shiller (2019) beskriver økonomiske fortællinger, der spreder sig som smitte: en historie vokser, når den bliver genfortalt, topper og dør ud, ofte uafhængigt af, om den var rigtig. Det er grunden til, at det giver mening at spørge, om omtalen *accelererer*, og ikke kun hvor stor den er.

### Temaer ved toppen af opmærksomheden

Fondsselskaber lancerer tema-ETF'er, når et tema er populært, fordi det er der, investorerne vil have dem. Ben-David, Franzoni, Kim og Moussawi (2023) viser, at specialiserede ETF'er typisk lanceres med aktier, der har steget meget og fået meget omtale, og at de derefter i gennemsnit klarer sig dårligere end markedet. Underpræstationen er i størrelsesordenen 6 % om året, justeret for risiko, i de første fem år. En bølge af nye tema-ETF'er er derfor et tegn på konsensus, ikke på en tidlig fase.

### Basisrater

De fleste fortællinger bliver aldrig til en varig meroverskud. Mange lyder overbevisende og er rigtige om den virkelige verden, men er allerede i kursen, eller gevinsten tilfalder kunderne frem for aktionærerne. Uden en basisrate overvurderer man let sin egen historie; se [Beslutninger, bias og falsifikation](laerebog/adfaerd#basisrater).

## Sådan gør radaren

Radaren har ingen nyhedsfeed og måler ikke omtale med tal. `/scout` er en Claude-skill, der søger på nettet og bedømmer fortællingerne kvalitativt. Bagefter holder den dem op mod radarens egne tal og fryser dem, så de kan måles:

- **Stadiet** bestemmes ved at holde fortællingen op mod kursen og revisionerne:
  - *hvisken*: omtalen vokser, men det relative afkast mod ACWI over 3–6 måneder er fladt eller negativt, og temaet er ikke i [rotationsgrafens](laerebog/rrg) *fører*-kvadrant
  - *bekræftes*: forbedres eller fører, med opadgående [estimatrevisioner](laerebog/estimatrevisioner)
  - *konsensus*: trængsel i [positioneringen](laerebog/cot), en høj [værdiansættelse mod sektoren](laerebog/relativ-vaerdiansaettelse), nye tema-ETF'er og en kendt eller overstået katalysator
- **Nyhed:** en proxy-kurv, der følger et tema, radaren allerede har, eller et af dine markedssyn, er ikke en ny idé.
- **Fremadrettet test:** hver kandidat på den korte liste fryses med sin proxy-kurv og dit valg (adopteret, fulgt, afvist), uanset valget. På [Evidens-siden](brugervejledning/scoretest#resultaterne-fremad) står hver kurv mod ACWI fra sin dag. Et gennemsnit pr. valg og pr. stadie vises fra {{settings:evidence.scout_min}} kandidater, der er mindst {{settings:evidence.cohort_age_months}} måneder gamle.

Kurven er de frosne proxy-ETF'er i lige vægte i kroner, købt ved lukkekursen på dagen. Har kandidaten ingen ETF, bruges aktierne. Det er samme beregning som for de frosne [porteføljeforslag](laerebog/portefoeljeforslag).

## Regneeksempel

> **Eksempel:** Scouten finder i oktober en historie om små modulære atomreaktorer.
>
> - Omtalen er tredoblet på tre måneder, med flere uafhængige kilder: en regeringsbeslutning, to forsyningsselskabers kontrakter og presseomtale af en fondsundersøgelse.
> - Proxy-ETF'en ligger 2 % under ACWI over 3 måneder og 1 % over over 6 måneder. Den er i kvadranten *forbedres*.
> - Estimaterne for de fire største navne er hævet med 3 % på 12 uger.
>
> Omtale op, kurs fladt og estimater op: stadiet sættes til *bekræftes*, tæt på *hvisken*. Du adopterer den med overbevisning 2.
>
> Seks måneder senere er kurven steget 14 %, mens ACWI er steget 5 %. Meroverskuddet er 14 − 5 = 9 procentpoint. En anden kandidat i samme kørsel, en tema-ETF i *konsensus*, som du afviste, er steget 2 %, altså −3 procentpoint mod ACWI.
>
> To kandidater beviser intet. Først med {{settings:evidence.scout_min}} i hver gruppe viser radaren et gennemsnit, og selv da overlapper perioderne og der er få af dem, så der er intet t-tal.

## Faldgruber og begrænsninger

- **Ekkokammeret:** én pressemeddelelse, gentaget af ti medier, er én kilde. Scouten vurderer kildernes uafhængighed, men kan tage fejl.
- **Promovering:** ETF-udbydere, børsnoterede småselskaber og betalte artikler har interesse i, at en historie spreder sig.
- **Overlevelsesbias:** man husker de fortællinger, der gik i opfyldelse. Derfor fryses også de afviste kandidater.
- **Søgning er ikke måling:** Claudes vurdering af, om omtalen tager til, er kvalitativ og kan ikke genskabes præcis. Rapporten gemmer sine links, så du kan efterprøve den.
- **Claudes vidensgrænse:** Claude kender verden frem til en bestemt dato og søger for at nå resten. Ældre viden kan farve vurderingen.
- **Rigtig historie, forkert aktie:** en teknologi kan vinde, uden at aktionærerne i de børsnoterede navne gør det.

## Videre læsning

- Brad M. Barber og Terrance Odean: "All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors", *Review of Financial Studies* 21(2), 2008.
- Zhi Da, Joseph Engelberg og Pengjie Gao: "In Search of Attention", *Journal of Finance* 66(5), 2011.
- Paul C. Tetlock: "Giving Content to Investor Sentiment: The Role of Media in the Stock Market", *Journal of Finance* 62(3), 2007.
- Robert J. Shiller: *Narrative Economics: How Stories Go Viral and Drive Major Economic Events*, Princeton University Press, 2019.
- Itzhak Ben-David, Francesco Franzoni, Byungwook Kim og Rabih Moussawi: "Competition for Attention in the ETF Space", *Review of Financial Studies* 36(3), 2023.
