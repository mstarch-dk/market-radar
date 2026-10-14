# Temaer og faktorer

Siden [Themes & factors](/themes) viser rotation for investeringstemaer (halvledere, forsvar, uran, cybersikkerhed, guld osv.) og for faktorer og stilarter (momentum, kvalitet, value, lav volatilitet osv.). Den virker præcis som [Sektorrotation](brugervejledning/sektorrotation): en rotationsgraf og en tabel pr. gruppe, koblet sammen. Det særlige ved denne side er, at hver linje også fortæller, hvad du som dansk investor rent faktisk kan købe.

Siden har to grupper, med hurtiglinks øverst:

- **Themes:** tema-ETF'er, målt mod ACWI.
- **Factors & style:** faktor-ETF'er, som viser, hvilken slags aktier markedet betaler for lige nu.

Teorien står i [Sektorer, temaer, faktorer og konjunkturcyklussen](laerebog/rotation-og-cyklus) og [Beta, alfa og faktorer](laerebog/beta-og-alfa).

## Hvorfor amerikanske ETF'er?

Temaerne måles med likvide, amerikansk noterede ETF'er, fordi de har lang historik, stor omsætning og rene kurser. Det giver de mest pålidelige signaler.

Men amerikanske ETF'er sælges som udgangspunkt ikke til private investorer i EU, fordi de ikke har det dokument (KID), EU-reglerne kræver. Derfor har hver linje et **UCITS-alternativ**: en europæisk registreret fond, der følger samme tema, og som du kan købe hos en dansk eller europæisk broker. Signalet kommer fra den amerikanske ETF; handlen sker i UCITS-fonden.

> **Bemærk:** UCITS-alternativet følger samme tema, men ikke nødvendigvis samme indeks. Afkastet kan afvige, især for smalle temaer. Tjek fondens indeks, omkostninger og andelsklasse (fx akkumulerende eller udbyttebetalende) på justETF, før du handler.

## Rotationsgrafen

Grafen læses som på sektorsiden: x-aksen er den relative trend mod ACWI (RS-Ratio), y-aksen accelerationen (RS-Momentum), og kvadranterne er *Leading* (fører), *Weakening* (svækkes), *Lagging* (halter) og *Improving* (forbedres). Data er ugentlige, halen er {{settings:rotation.tail}} uger. Hold musen over en prik for detaljer, klik for at åbne ETF'en, og brug tabellens filtre til at vælge, hvilke haler der vises. En fuld gennemgang står i [Sektorrotation](brugervejledning/sektorrotation#rotationsgrafen).

Temaer roterer ofte hurtigere og kraftigere end sektorer, fordi de er smallere. Lange haler og store spring mellem kvadranter er derfor normale her.

## Tabellen

Tabellen har de samme kolonner som på sektorsiden (*Name*, *#*, *Δ rank*, *Quadrant*, *Rel 1m*, *Rel 3m*, *Rel 6m*, *>200d*, *P/E*, *Signals*), plus tre kolonner til sidst:

| Kolonne | Indhold |
|---|---|
| *UCITS alternative* | Navnet og tickeren på en UCITS-fond, der følger samme tema (link med hover-kort) |
| *ISIN* | UCITS-fondens ISIN-kode |
| *Positive list 2026* (årstallet følger listen) | Om UCITS-fonden står på SKATs positivliste |

### UCITS-alternativet
En streg (–) betyder, at radaren ikke har en Yahoo-ticker for et alternativ registreret, **ikke** at der ikke findes et. For nogle linjer kender radaren fondens navn og ISIN, men ikke en ticker; så står der en streg her, mens *ISIN* og positivliste-status er udfyldt. Filteret på kolonnen (*✓ Yes* / *✗ No*) viser kun linjer med eller uden en ticker.

### ISIN
ISIN-koden er den sikreste måde at finde præcis den rigtige fond hos din broker, fordi samme fond ofte findes i flere andelsklasser og på flere børser med forskellige tickers. Søg på ISIN hos din broker og på justETF. Kolonnen kan også søges i med tabellens *Search…*.

### Positivlisten: yes, no og ?
Kolonnen viser, om fondens ISIN står på det nyeste års ark i SKATs positivliste over aktiebaserede investeringsselskaber:

| Mærke | Betydning |
|---|---|
| *yes* (grøn) | Fonden står på listen. I frie midler beskattes den som aktieindkomst efter lagerprincippet, og den kan ligge på en aktiesparekonto. |
| *no* (rød) | Fonden står ikke på listen. I frie midler beskattes gevinsten som kapitalindkomst, hvilket som regel er mindre gunstigt, og den kan ikke ligge på en aktiesparekonto. |
| ? (grå) | Ikke tjekket: radaren har ingen ISIN for linjen, eller positivlisten er ikke indlæst. |

Sidehovedet siger, hvilket års liste der er tjekket mod. Er listen ikke indlæst, står der i stedet, at du skal lægge SKATs liste i `imports/positivliste.xlsx`; se [Installation og første start](brugervejledning/installation#skats-positivliste).

Når du kan vælge, er en fond på positivlisten som regel det mest enkle valg for en dansk privatinvestor. Baggrunden for reglerne står i [Dansk skat for investorer](laerebog/skat).

> **Bemærk:** Positivliste-status er en hjælp til at finde rundt, ikke skatterådgivning. Reglerne og listen ændrer sig. Tjek de aktuelle regler på skat.dk.

### Værdiansættelse
Kolonnen *P/E* viser fondens P/E fra Yahoos fonddata, farvet i forhold til ACWI's P/E: grøn er billigere end verdensindekset, orange og rød dyrere. Under *Columns* kan du slå *vs ACWI* (P/E divideret med ACWI's) og *P/E pct* (hvor fondens P/E ligger i sin egen historik) til. Percentilen kræver {{settings:valuation.etf_history_weeks}} ugers øjebliksbilleder, så den mangler de første måneder. Et tema kan være dyrt af gode grunde; se [Relativ værdiansættelse](laerebog/relativ-vaerdiansaettelse).

## Faktorer og stil

Gruppen *Factors & style* indeholder ETF'er for momentum, kvalitet, minimumsvolatilitet og value samt nogle par, der er bygget til at blive læst sammen:

- **Growth mod Value** (Russell 1000): betaler markedet for vækst eller for lave nøgletal?
- **High beta mod Low volatility:** søger markedet risiko eller sikkerhed?

Når et par går hver sin vej på grafen, fx *High beta* i *Leading* og *Low volatility* i *Lagging*, er det et tegn på risikovillighed, som du kan sammenholde med [Regime](/regime). Faktorgruppen er målt på amerikanske aktier.

Faktorerne bruges også på tickerprofilen til at forklare, hvilken slags aktie et navn opfører sig som; se [Tickerprofilen](brugervejledning/tickerprofil).

## Sådan bruger du siden

1. **Find temaer i bevægelse.** Filtrer *Quadrant* til *Improving* og *Leading*, og se, hvilke haler der peger op mod højre.
2. **Tjek styrken.** Er *Rel 3m* og *Rel 6m* positive, og er *>200d* ✓? Et tema i *Improving* under sit 200-dages snit er stadig i en nedtrend.
3. **Find det, du kan købe.** Se på *UCITS alternative*, *ISIN* og positivlisten. Filtrer evt. *Positive list* til *yes*.
4. **Undersøg fonden.** Åbn UCITS-fondens profil via linket, og sammenlign dens kurs med den amerikanske ETF's. Følger de hinanden tæt?
5. **Se på værdiansættelsen.** Et tema, der er steget meget, er ofte også blevet dyrt. Det er ikke en grund til at lade være, men det er en risiko at kende.

> **Tip:** Vil du lede bredere end radarens faste liste af temaer, har [Discover](/discover) et marked for alle UCITS-ETF'er på positivlisten, grupperet efter kategori. Se [Discover](brugervejledning/discover).
