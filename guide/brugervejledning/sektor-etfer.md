# Sektor-ETF'er

[Sektorrotationen](brugervejledning/sektorrotation) siger, hvilke sektorer der fører og halter, men den måler dem med amerikanske ETF'er (XLK, XLE …), som du som dansk privatinvestor ikke kan købe, fordi de ikke har et KID-dokument. Siden *Sector ETFs* svarer på det næste spørgsmål: **hvis jeg vil have eksponering mod en sektor, hvilken UCITS-ETF køber jeg så?**

For hver sektor viser siden én *go-to*-ETF og dens nærmeste alternativer, med hvad de koster, hvordan de beskattes i Danmark, og hvordan de har klaret sig i kroner. Listen laves af Claude med skillen `/sector-etfs` og opdateres af dig, når du synes (se nedenfor). Det er analyse, ikke rådgivning: go-to-fonden er den, der passer bedst til reglen nedenfor, ikke en anbefaling om at købe.

## Hvad siden viser

Sektorerne står i to lag:

- **De 11 GICS-sektorer** med de navne, Yahoo bruger: *Technology*, *Healthcare*, *Financial Services* osv.
- **Europæiske supersektorer** med en UCITS-ETF for sig selv, under deres GICS-sektor: fx *Banks* og *Insurance* under *Financial Services*, *Autos & Parts* under *Consumer Cyclical*.

Øverst står, hvornår `/sector-etfs` sidst kørte, og hvor mange sektorer den dækker. En sektor, der endnu ikke er dækket, er skjult; sæt hak i *Show sectors not covered yet* for at se dem alle. Linkene øverst springer til hver sektor.

### Et sektorkort

- **Overskriften** viser sektorens kvadrant i rotationen (fører, svækkes, halter, forbedres) for hver af dens rotations-ETF'er, fx XLK for USA og EXV3.DE for Europa.
- **In the rotation**: placeringen i gruppen og afkastet over 3 måneder mod ACWI, som på siden [Sector rotation](/rotation).
- **Go-to**: den valgte fond med omfang, TER og skattestatus, og Claudes begrundelse, når valget afviger fra reglen. Mærket *re-check* betyder, at reglen i dag sætter en anden fond først, og at optegnelsen ikke gav en grund til at beholde denne. Så er det tid til at køre `/sector-etfs` for sektoren igen.
- **Tabellen** med go-to-fonden og dens alternativer i reglens rækkefølge.

### Kolonnerne

| Kolonne | Betydning |
|---|---|
| *#* | Placeringen efter reglen nedenfor |
| *Fund* | Fondens navn og Yahoo-ticker; *go-to* markerer valget |
| *Scope* | Hvad fonden dækker: *World* (MSCI World-sektoren), *US* (S&P 500-sektoren) eller *Europe* (STOXX Europe 600-sektoren) |
| *TER* | De årlige omkostninger, som fondsudbyderen oplyser dem. Hold musen over for Yahoos tal; ≠ betyder, at de to afviger med mere end 0,05 procentpoint, så tjek udbyderens side |
| *Size* | Fondens størrelse i mio. USD |
| *Acc/Dist* | Akkumulerende (geninvesterer udbyttet) eller udbyttebetalende |
| *Tax* og året | Skattestatus for i år (se nedenfor) |
| *1m*, *3m*, *6m*, *1y* | Afkastet i kroner (valutakursen regnet med) |
| *vs ACWI 3m*, *vs ACWI 1y* | Afkastet minus ACWI's afkast i kroner, i procentpoint |
| *1 year* | Kursen det seneste år, uge for uge, i kroner |

Under *Columns* kan du også vise ISIN, domicil, *tracking difference* og afkastet år til dato. Et tal, radaren ikke kender, står som –, aldrig som 0.

## Rangordningsreglen

Koden rangordner fondene i hver sektor efter fem trin. Et trin bruges kun, når de foregående står lige:

1. **Skat:** på positivlisten for året før ukendt, før uden for listen.
2. **Størrelse:** en fond under {{settings:sector_etfs.min_aum_musd}} mio. USD kommer efter alle større fonde. En lille fond risikerer at lukke eller blive lagt sammen med en anden.
3. **TER**, laveste først.
4. ***Tracking difference***, højeste først, når den kendes: fondens afkast minus indeksets over det seneste hele år. Den viser, hvad fonden reelt koster, ud over TER.
5. **Akkumulerende før udbyttebetalende.** Lagerbeskatningen rammer begge ens, men en akkumulerende fond sparer dig for at geninvestere udbyttet.

Claude vælger normalt reglens første som go-to. Et andet valg kræver en grund, reglen ikke kan se, fx at en verdensfond giver en bredere sektor end en rent amerikansk, og begrundelsen står så på kortet. For en GICS-sektor foretrækkes en verdensfond som go-to, med de amerikanske og europæiske udgaver som alternativer.

## Skattestatus

Radaren slår hver fonds ISIN op på [positivlisten](laerebog/skat#positivlisten) for indeværende år:

- **PL · ASK ✓** (grøn): på listen. Fonden er aktiebaseret: gevinsten lagerbeskattes som aktieindkomst, og fonden må ligge på en aktiesparekonto.
- **PL · ASK ✓** (gul): på listen i år, men ikke på næste års ark, når SKAT har lagt det ud. Fra næste år beskattes den som kapitalindkomst og må ikke ligge på en aktiesparekonto.
- **off · ASK ✗** (rød): ikke på listen. En udenlandsk ETF uden for listen lagerbeskattes som kapitalindkomst, hvilket for de fleste er dyrere, og den må ikke ligge på en aktiesparekonto.
- **?**: SKAT har ikke lagt årets liste ud endnu, eller fonden har ingen ISIN.

Positivlisten afgør kun, om en fond er aktiebaseret. Den siger intet om, hvorvidt din bank eller dit depot tilbyder netop den notering. Se [Skat](laerebog/skat) for reglerne og [UCITS-tvillinger og positivlisten](laerebog/rotation-og-cyklus#ucits-tvillinger-og-positivlisten).

## Sådan opdaterer du listen

Skriv `/sector-etfs` i Claude Code i programmappen:

- `/sector-etfs`: de sektorer, der mangler, har mærket *re-check* eller er ældre end {{settings:sector_etfs.stale_days}} dage
- `/sector-etfs Technology Banks`: kun de nævnte sektorer
- `/sector-etfs --all`: alle sektorerne

Claude henter kandidaterne for hver sektor (`radar sector-etfs candidates`): de fonde, optegnelsen har i forvejen, kendte UCITS-fonde fra `config/sector_etfs.yaml` og fonde fra positivlisten, som [Discover](brugervejledning/discover) har koblet til Yahoo. Derefter læser Claude TER, størrelse, udbyttepolitik, domicil og *tracking difference* på udbydernes egne sider (iShares, Xtrackers, SPDR, Amundi, Invesco) og på justETF, med link og dato for hvert tal. Et tal, Claude ikke kan finde, gemmes som ukendt.

Du ser ét kort pr. sektor med go-to-fonden, alternativerne og hvad der har ændret sig siden sidst, og vælger *Gem* eller *Spring over* for hver. Kun de sektorer, du siger ja til, gemmes; de andre beholder deres tidligere valg og dato. Hver kørsel gemmes som en ny fil i `exports/sector_etfs/` i datamappen og overskriver aldrig en ældre, så `uv run radar sector-etfs history` kan vise, hvad hver kørsel valgte. Claudes notat ligger under fanen *Research* på [Notebook](/notebook).

Siden viser en advarsel, når listen er ældre end {{settings:sector_etfs.stale_days}} dage. Omkostninger ændrer sig, og nye fonde kommer til, så kør den igen et par gange om året. Kurserne, skattestatus og rotationen er altid dagens.

## Fra andre sider

- **[Sector rotation](/rotation)**: kolonnen *UCITS go-to* i grupperne med amerikanske og europæiske sektorer viser go-to-fonden for sektoren, og *peers →* fører til dens kort.
- **[Røntgen af porteføljen](brugervejledning/xray)**: hver sektor under *Exposure* har et link til sektorens go-to-fond.
- **[Tickerprofilen](brugervejledning/tickerprofil)**: under *Price development*, lige under tabellen, står go-to-fonden for aktiens sektor med et link til sektorens kort.

## Begrænsninger

- Go-to-fonden er den bedste efter en fast regel, ikke den bedste for dig. Tjek, at din bank tilbyder noteringen, og hvad handlen koster dér.
- TER, størrelse og *tracking difference* er skrevet af fra udbyderne den dag, der står på fonden. De kan have ændret sig siden.
- En verdens-, USA- og Europa-fond for samme sektor rummer forskellige aktier. En amerikansk teknologifond er fx domineret af ganske få selskaber.
- Afkastene er historiske og siger ikke, hvad sektoren gør fremover.
