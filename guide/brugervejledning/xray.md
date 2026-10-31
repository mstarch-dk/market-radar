# Røntgen af porteføljen

Siden [X-ray](/xray) viser, hvad dine porteføljer tilsammen er eksponeret mod, og hvor risikoen sidder, målt mod ACWI. Den svarer på spørgsmål, som afkasttallene ikke gør: Hvor meget mere teknologi har jeg end verdensindekset? Hvilken position bærer mest af udsvingene? Hvad ville min portefølje i dag have tabt i coronakrakket?

Alt regnes live i kroner ud fra dagens vægte, hver gang du åbner siden, og følger med, når du retter en handel. Det er en beskrivelse af porteføljen, ikke rådgivning.

## Vælg portefølje

Vælgeren *Portfolio* virker som på [Mine beholdninger og watchlist](brugervejledning/beholdninger#vælg-portefølje): som standard dine rigtige porteføljer lagt sammen, men du kan vælge én portefølje, alle virtuelle, et tag eller det hele. Valget står i adressen som `?pf=`. Du kan altså også røntgenfotografere et eksperiment, fx en A/B-kurv.

## Tallene øverst

| Felt | Betyder |
|---|---|
| *Invested (DKK)* | Værdien af beholdningerne i kroner. Står der *without a value*, mangler et eller flere papirer en kurs eller valutakurs; de er udeladt af alle vægte og står nævnt under felterne, aldrig regnet som 0 |
| *Cash share* | Kontanternes andel af den samlede værdi. Kun porteføljer med en kontantkonto (indskud og hævninger) har kendte kontanter; står der *no cash ledger*, er kontanterne ukendte. Se [Portefølje](brugervejledning/portefolje) |
| *Volatility (ex-ante)* | Hvor meget porteføljen med dagens vægte ville svinge på et år, beregnet på de seneste {{settings:risk.covariance.history_weeks}} ugers afkast |
| *Beta* | Hvor meget porteføljen plejer at bevæge sig, når ACWI bevæger sig 1 % |
| *Tracking error* | Hvor meget porteføljens afkast svinger omkring ACWI's på et år. Omkring 2 % er tæt på indekset; 8 % eller mere er en helt anden portefølje |
| *Effective N* | Det effektive antal positioner: hvor mange lige store positioner koncentrationen svarer til. *top 5* er de fem største positioners andel |
| *Risk model coverage* | Hvor stor en del af værdien risikomodellen dækker (se [Dækning](#dækning-hvad-tallene-hviler-på)) |
| *Score tilts* | Beholdningernes momentumscore og K+V, vægtet med værdien, mod medianen i radarens aktieunivers (se [Scorehældning](#scorehældning)) |

Felterne med risiko bliver gule, når dækningen er under {{settings:risk.xray.warn_coverage|pct}}.

## Eksponering mod ACWI

Under *Exposure vs ACWI* vælger du mellem fanerne *Sector*, *Region* og *Currency*. Hver række er en sektor, region eller valuta:

| Kolonne | Betyder |
|---|---|
| *Weight* | Din vægt, af den investerede værdi (uden kontanter) |
| *ACWI* | Verdensindeksets vægt, fra iShares' beholdningsfil for MSCI ACWI-fonden |
| *Active* | Den aktive vægt: din vægt minus ACWI's, i procentpoint. Søjlen til højre vokser mod højre for overvægt og mod venstre for undervægt |

Rækkerne står efter den største aktive vægt. Den aktive vægt er det væddemål, du har lavet mod verdensindekset, bevidst eller ej: +20 procentpoint i teknologi betyder, at din portefølje vil klare sig markant anderledes end ACWI, når teknologi går sin egen vej.

Under tabellen står dækningen for fanen, fx *Sector: 95% of the value placed.* Resten er fonde, der ikke kan gennemlyses, eller papirer uden kendt sektor. De står som grå rækker uden ACWI og aktiv vægt (*fund: not looked through* eller *unknown*). Linjen bliver gul under {{settings:risk.xray.warn_coverage|pct}}.

### Sådan placeres fondene

Fold *How each name is classified* ud for at se, hvordan hvert papir er placeret (kolonnen *Class*):

| Klasse | Hvornår | Sektor | Region og valuta |
|---|---|---|---|
| *world fund (ACWI's weights)* | En bred verdensfond fra listen `risk.world_funds` | ACWI's vægte | ACWI's vægte |
| *index fund (its index's weights)* | En indeksfond fra `config/index_funds.yaml`, fx en dansk investeringsforening | Indeksets vægte | Indeksets vægte; en valutasikret andelsklasse tæller i den valuta, den er sikret til |
| *sector fund* | En sektor-ETF fra radarens lister, eller en fond, hvor én sektor vejer mindst 50 % i Yahoos fonddata | Fondens sektor | Regionen, hvis radaren kender den; ellers ikke gennemlyst |
| *fund (Yahoo's sector weights)* | En anden fond med sektorvægte i Yahoos fonddata | Yahoos vægte | Ikke gennemlyst |
| *fund, not looked through* | En fond uden brugbare data | Ikke gennemlyst | Ikke gennemlyst |
| *stock* | En aktie | Aktiens sektor | Aktiens region og handelsvaluta |
| *unknown* | Hverken en kendt fond eller en aktie med en sektor | Ukendt | Ukendt |

En fond, der ikke kan gennemlyses, bliver aldrig lagt i den region, den er noteret i: en S&P 500-fond noteret i Amsterdam er ikke europæisk. Fonddata læses kun fra det, der allerede ligger i cachen. Kolonnen *Fund data* viser datoen. Åbner du en fonds [tickerprofil](brugervejledning/tickerprofil), hentes dens data, så den kan gennemlyses næste gang.

Danske investeringsforeninger viser Yahoo som aktier uden sektor og uden fonddata, så tickerprofilen hjælper ikke for dem. De står i stedet i `config/index_funds.yaml` med det indeks, de følger. Radaren tæller en sådan fond som sit indeks: ACWI's beholdning i indeksets lande, vægtet op til 100 %. Det giver fonden sektorer, regioner og valutaer, og kolonnen *Fund data* viser datoen for ACWI's beholdningsfil. En andelsklasse, der er valutasikret til kroner (fx *DKK h*), tæller som kroner under *Currency*, men med indeksets sektorer og regioner. Noterne siger for hver fond, hvilket indeks den er talt som. Står din fond ikke på listen, er den *unknown*.

> **Bemærk:** En indeksfond tælles som ACWI's udsnit af indekset, ikke som indekset selv. ACWI har kun store og mellemstore selskaber, så et indeks med små selskaber læses som sine store selskaber. Et S&P 500-indeks læses som MSCI USA, et ESG-indeks som det indeks, det bygger på, og et indeks med loft over den største aktie uden loftet. For emerging markets mangler Indien, Brasilien og Saudi-Arabien, fordi ACWI-fonden ejer dem gennem andre fonde. Noterne siger det.

> **Bemærk:** Verdensfonde, der følger MSCI World, tælles med ACWI's vægte, selv om MSCI World udelader emerging markets. Det er en tilnærmelse, og noterne siger det.

## Hvor risikoen sidder

Tabellen *Where the risk sits* viser hver position i risikomodellen:

| Kolonne | Betyder |
|---|---|
| *Weight* | Positionens vægt blandt papirerne i modellen |
| *Share of risk* | Positionens andel af porteføljens samlede risiko (variansen). Andelene summerer til 100 % |
| *Share of active risk* | Positionens andel af den aktive risiko, altså tracking error mod ACWI. Med ACWI-benet summerer de til 100 % |
| *MCTR* | Det marginale risikobidrag: hvor meget porteføljens volatilitet ændrer sig pr. ekstra vægtenhed i positionen |

Sammenlign *Share of risk* med *Weight*. En volatil aktie, der svinger med resten, kan bære langt mere risiko end sin vægt, og en bred fond langt mindre. En negativ andel af den aktive risiko får mærket *reduces TE*: positionen trækker porteføljen tættere på ACWI og udligner noget af de andre væddemål. Under tabellen står ACWI-benets andel. Er den negativ, sænker det, at du ejer mindre end hele indekset, den aktive risiko en smule.

Papirer med færre end {{settings:risk.covariance.min_weeks}} ugers kurser er ikke med i modellen. De står under tabellen med deres vægt (*Not in the risk model*).

Metoden står i [Diversifikation og korrelation](laerebog/diversifikation#risikobidrag-og-mctr) og [Beta, alfa og faktorer](laerebog/beta-og-alfa#tracking-error-og-aktiv-risiko).

### Ex ante og realiseret

Linjen *Ex-ante vs realised* stiller to tal side om side:

- **Ex ante**: dagens vægte lagt på fortidens afkast. Det er den risiko, porteføljen har, som den ser ud nu.
- **Realiseret**: volatiliteten og det dybeste fald for det, du faktisk ejede det seneste år, handler undervejs medregnet (det tidsvægtede indeks fra [Afkast over tid](brugervejledning/afkast)).

Er de meget forskellige, har porteføljen ændret sig: har du fx købt mere af de volatile aktier, er ex ante højere end det realiserede.

## Dækning: hvad tallene hviler på

Risikomodellen bruger ugentlige afkast i kroner over {{settings:risk.covariance.history_weeks}} uger med shrinkage ({{settings:risk.covariance.shrink|pct}} mod en fælles korrelation). Dækningen er den andel af den investerede værdi, der er med i modellen.

- Under {{settings:risk.xray.warn_coverage|pct}} vises risikotallene i gult: de beskriver kun den del af porteføljen, der er med.
- Under {{settings:risk.xray.min_coverage|pct}} vises ingen risikotal, kun en note.

Samme regel gælder eksponeringen: hver dimension har sin egen dækning. Ingen manglende værdi bliver gættet eller sat til 0.

## Koncentration

Kortet *Concentration* viser *Effective N*, de fem største positioners andel (*Top 5*), den største position (*Largest position*) og den position, der bærer mest af risikoen (*Largest share of risk*). *In world funds* er andelen i verdens- og indeksfonde. En sådan fond tæller som én position, så koncentrationen ser større ud, end den er; derfor står andelen der.

*Holdings that move together* lister par af beholdninger, hvis ugentlige afkast har haft en korrelation over {{settings:risk.xray.pair_corr}}, med deres samlede vægt. To sådanne papirer opfører sig næsten som én større position.

## Faktortilt

Kortet *Factor tilts* er den samme regression som på tickerprofilen, men for hele porteføljen: porteføljens ugentlige afkast mod ACWI og spændet mellem hver faktor-ETF ({{settings:risk.factors}}) og ACWI. Et tilt med $|t| \ge 2$ fremhæves. Faktor-ETF'erne er amerikanske, og tallene beskriver, hvordan porteføljen har opført sig; de er ikke en prognose. Se [Faktortilt med ETF'er](laerebog/beta-og-alfa#faktortilt-med-etfer).

## Stress

Tabellen *Stress: today's weights in past crises* lægger dagens vægte i kroner på kendte faldperioder (`risk.stress` i `settings.yaml`) og viser afkast og dybeste fald ved siden af ACWI's. En verdensfond uden kurser så langt tilbage regnes med ACWI's kurser.

Kolonnen *Coverage* er den del af værdien, der har kurser i perioden; papirer uden står i noten. Har under halvdelen af værdien kurser, genspilles perioden ikke (*not replayed*). En aktie, der blev børsnoteret efter krakket, kan derfor ikke sige noget om det.

## Scorehældning

Feltet *Score tilts* viser:

- **Momentum**: beholdningernes momentumscore mod hele aktieuniverset, den samme som i kolonnen *Score* på [Holdings & watchlist](/me), vægtet med værdien.
- **K+V**: kvalitets- og værdiscoren (se [Kvalitet og værdi](brugervejledning/kvalitet-og-vaerdi)), vægtet med værdien.

Under står medianen i radarens aktieunivers for hver. Ligger porteføljen over, hælder den mod stærkere momentum eller bedre og billigere selskaber end det typiske papir. Beholdninger uden en score (fonde uden regnskaber, kort historik) er udeladt af gennemsnittet, aldrig regnet som 0; feltet tæller dem, og noterne nævner dem.

## Noter

Nederst står alt det, der er værd at vide om tallene: porteføljer uden kontantkonto, papirer uden kurs, fonde, der ikke kunne gennemlyses, og de forbehold, der er nævnt ovenfor.

## På kommandolinjen

`uv run radar xray` viser det samme i terminalen, og `--json` giver hele røntgenbilledet som JSON. Se [Kommandolinjen](brugervejledning/kommandolinjen).

> **Tip:** Kig på røntgenbilledet, før du lægger penge i en ny aktie. Tilføjer den mest til en aktiv vægt, du allerede har, eller til et par, der bevæger sig sammen, øger den koncentrationen mere end diversifikationen.
