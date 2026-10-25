# Indstillinger

Radarens tærskler, vinduer og grænser står i tekstfiler i mappen `config/`. Dette kapitel gennemgår dem blok for blok. Tallene i teksten er hentet direkte fra din `config/settings.yaml`, så de altid passer med den udgave, du kører.

Du behøver ikke ændre noget. Standardværdierne er valgt med omhu, og de fleste har en forklaring i lærebogen. Men vil du justere, er det her, det sker.

## Sådan ændrer du en indstilling

1. Luk appen (luk det sorte vindue eller tryk Ctrl+C i terminalen).
2. Åbn filen i en teksteditor, fx Notesblok. Filerne er i formatet YAML: indrykning med mellemrum betyder noget, og alt efter `#` er en kommentar.
3. Ret værdien, og gem.
4. Start appen igen, og kør *Update data* (eller `uv run radar run`), så rapporten bygges med de nye værdier.

Appen læser indstillingerne, når den starter. En ændring slår derfor først igennem efter en genstart, og tal, der står i den færdige rapport (regime, rotation, momentum), først efter næste opdatering.

> **Bemærk:** Tag en kopi af filen, før du ændrer den. En fejl i YAML-formatet får appen og kommandoerne til at stoppe med en besked om, hvilken fil der er galt; `uv run radar doctor` fanger det også.

Procenter skrives i filen som brøker: 0.05 betyder 5 %.

> **Bemærk:** `config/` ligger i programmappen, ikke i din datamappe, og kommer ikke med i backuppen. En ny version har sine egne filer med sine standardværdier, så har du ændret noget, skal du gøre det igen efter en opdatering.

## settings.yaml: generelt

| Nøgle | Værdi | Betyder |
|---|---|---|
| `history_years` | {{settings:history_years}} | År med kurshistorik, der mindst hentes (mere, hvis din første handel kræver det; se `backtest`) |
| `constituents_max_age_days` | {{settings:constituents_max_age_days}} | Dage før listen over S&P 500-aktier hentes igen |
| `snapshot_min_gap_days` | {{settings:snapshot_min_gap_days}} | Mindste alder på det snapshot, rangændringer ("Δ rank", "new") sammenlignes med, regnet fra datoen for dataene |

Kurser fra før historikkens start findes ikke i radaren, så porteføljerækker fra før kan ikke værdisættes på deres dato. Se [Afkast over tid](brugervejledning/afkast).

## `rotation`: rotationsgrafen

| Nøgle | Værdi | Betyder |
|---|---|---|
| `rotation.window` | {{settings:rotation.window}} uger | Vinduet, RS-Ratio og RS-Momentum normaliseres over |
| `rotation.tail` | {{settings:rotation.tail}} uger | Længden af halen på rotationsgrafen |

Et kortere vindue gør grafen hurtigere, men mere urolig. Se [Rotationsgrafen (RRG)](laerebog/rrg) og [Sektorrotation](brugervejledning/sektorrotation).

## `momentum`: momentumledere

| Nøgle | Værdi | Betyder |
|---|---|---|
| `momentum.top_n` | {{settings:momentum.top_n}} | Antal ledere pr. region på siden *Momentum* |
| `momentum.min_history_days` | {{settings:momentum.min_history_days}} | Handelsdage med historik, en aktie skal have for at få en score |

Se [Radarens momentumscore](laerebog/momentumscore).

## `regime`: risk-on/risk-off-afstemningen

Hver indikator i regimet stemmer risk-on, risk-off eller neutralt efter disse tærskler. Selve reglen for den samlede afstemning (netto over +0,33 er risk-on, under −0,33 risk-off) ligger i koden.

| Nøgle | Værdi | Betyder |
|---|---|---|
| `regime.vix_calm` | {{settings:regime.vix_calm}} | VIX under dette stemmer risk-on |
| `regime.vix_stress` | {{settings:regime.vix_stress}} | VIX over dette stemmer risk-off |
| `regime.breadth_strong` | {{settings:regime.breadth_strong}} | Procent af aktierne over 200-dages gennemsnittet, der stemmer risk-on |
| `regime.breadth_weak` | {{settings:regime.breadth_weak}} | … og under dette risk-off |
| `regime.highs_lows_band` | {{settings:regime.highs_lows_band}} | Netto procent af aktierne ved 52-ugers høj: mindst +bånd er risk-on, højst −bånd risk-off |
| `regime.vix_term_calm` | {{settings:regime.vix_term_calm}} | VIX/VIX3M under dette er roligt; over 1 er terminsstrukturen inverteret (stress) |
| `regime.rates_shock` | {{settings:regime.rates_shock}} | Stigning i den amerikanske 10-årige rente over 3 måneder, i procentpoint, der stemmer risk-off |
| `regime.copper_gold_band` | {{settings:regime.copper_gold_band|pct}} | Ændring i kobber/guld over 3 måneder, der skal til for at stemme |
| `regime.oil_shock` | {{settings:regime.oil_shock|pct}} | Stigning i olieprisen (WTI) over 3 måneder, der stemmer risk-off |
| `regime.revisions_band` | {{settings:regime.revisions_band}} | Ændring i FactSets vækstestimat for kvartalet, i procentpoint, der skal til for at stemme |
| `regime.cape_rich_pct` / `cape_cheap_pct` | {{settings:regime.cape_rich_pct}} / {{settings:regime.cape_cheap_pct}} | Shiller CAPE-percentil siden 1871: højt er dyrt (risk-off), lavt billigt (risk-on) |
| `regime.erp_low_pct` / `erp_high_pct` | {{settings:regime.erp_low_pct}} / {{settings:regime.erp_high_pct}} | Percentil for Damodarans risikopræmie: lav er en tynd præmie (risk-off), høj en rigelig (risk-on) |

### Hvilke grupper stemmer

`regime.votes` slår to grupper af indikatorer til eller fra:

| Nøgle | Standard | Gruppe |
|---|---|---|
| `regime.votes.credit_eu` | {{settings:regime.votes.credit_eu}} | Kreditspændet på europæisk high yield (HY) ved siden af det amerikanske |
| `regime.votes.valuation` | {{settings:regime.votes.valuation}} | CAPE og risikopræmien: langsomme mål, ikke et timingsignal på 1–6 måneder |

Dette er kun standarden. På siden [Regime](/regime) kan du slå grupperne til og fra; dit valg gemmes i `radar.db` i datamappen og går forud for filen. En slået-fra indikator vises stadig med sin aflæsning, men stemmer ikke. Se [Regime](brugervejledning/regime) og [Radarens afstemningsmodel](laerebog/afstemningsmodellen).

## `positioning`: futurespositionering

| Nøgle | Værdi | Betyder |
|---|---|---|
| `positioning.lookback_weeks` | {{settings:positioning.lookback_weeks}} | Uger, CFTC-positioneringen rangeres over |
| `positioning.extreme_pct` | {{settings:positioning.extreme_pct}} | Øverste/nederste procent af vinduet, der regnes for trængt |

Se [Futurespositionering (CFTC COT)](laerebog/cot).

## `sectors`: klynger blandt lederne

En sektor eller branche markeres som en klynge i en regions top {{settings:momentum.top_n}}, når den har mindst `sectors.cluster_min` = {{settings:sectors.cluster_min}} navne og mindst `sectors.cluster_ratio` = {{settings:sectors.cluster_ratio}} gange sin andel af regionen. Se [Momentum](brugervejledning/momentum).

## `stops`: stop og kursmål

Reglen bag gennemgangsniveau, stop og kursmål for beholdninger, tema-ETF'er og tickerprofiler.

| Nøgle | Værdi | Betyder |
|---|---|---|
| `stops.mode` | {{settings:stops.mode}} | `trend`: niveauet er et glidende gennemsnit; `atr`: det glidende ATR-stop (reglen indtil oktober 2026) |
| `stops.trend_sma` | {{settings:stops.trend_sma}} | Dage i gennemsnittet, når `mode` er `trend` |
| `stops.action` | {{settings:stops.action}} | `review`: en lukkekurs under niveauet er en anledning til at gennemgå positionen, ikke et salgssignal |
| `stops.take_profit` | `false` | `true` slår kursmålet til igen (i radarens test kostede det mest afkast) |
| `stops.atr_days` | {{settings:stops.atr_days}} | Dage i ATR (det typiske daglige udsving) |
| `stops.k_base` | {{settings:stops.k_base}} | Startværdi for k: stop = højeste lukkekurs siden køb − k × ATR |
| `stops.k_min` / `k_max` | {{settings:stops.k_min}} / {{settings:stops.k_max}} | Grænser for k |
| `stops.k_step` | {{settings:stops.k_step}} | Hvor meget hvert signal flytter k (blandet regime og faldende kursmål flytter det halve) |
| `stops.strong_score` | {{settings:stops.strong_score}} | Momentumscore, der giver mere plads |
| `stops.extended_vs_sma50` | {{settings:stops.extended_vs_sma50|pct}} | Så langt over 50-dages gennemsnittet er kursen strakt, og stoppet strammes |
| `stops.reward_risk` | {{settings:stops.reward_risk}} | Kursmål = kurs + dette × stopbredden (eller analytikernes middelkursmål, hvis det er lavere) |
| `stops.near_atr` | {{settings:stops.near_atr}} | "near stop" / "near target" inden for så mange ATR |
| `stops.min_analysts` | {{settings:stops.min_analysts}} | Mindste antal analytikere, før kursmålene bruges |
| `stops.target_cut` | {{settings:stops.target_cut|pct}} | Ændring i middelkursmålet over 30 dage, der tæller som et signal |
| `stops.info_anchor_days` | {{settings:stops.info_anchor_days}} | For et navn, du ikke ejer: stoppet regnes fra højeste lukkekurs i så mange handelsdage |
| `stops.include` | (liste) | Tema-fonde uden for radarens ETF-grupper, der også skal have niveauer |

Brede indeksfonde får aldrig niveauer. Se [Stop-loss, take-profit og positionsstørrelse](laerebog/stop-og-storrelse).

## `backtest`: stop-simulering og test af scoren

| Nøgle | Værdi | Betyder |
|---|---|---|
| `backtest.warmup_days` | {{settings:backtest.warmup_days}} | Dage med kurser før din første handel (200-dages gennemsnit, 12-måneders momentum, ATR) |
| `backtest.max_years` | {{settings:backtest.max_years}} | Kurser hentes aldrig længere tilbage end dette |
| `backtest.fill` | {{settings:backtest.fill}} | `next`: et udløst salg handles til næste dags lukkekurs; `same`: samme dags |
| `backtest.park` | {{settings:backtest.park}} | Hvor pengene fra et salg står, indtil dit næste køb |
| `backtest.fred_lag_days` | {{settings:backtest.fred_lag_days}} | Dage før en FRED-værdi regnes som kendt |
| `backtest.oecd_lag_days` | {{settings:backtest.oecd_lag_days}} | Dage før en OECD-indikator regnes som kendt |
| `backtest.valuation_lag_days` | {{settings:backtest.valuation_lag_days}} | Dage før CAPE og risikopræmie regnes som kendt |
| `backtest.fee_bps` | {{settings:backtest.fee_bps}} | Kurtage pr. simuleret handel (reglens salg, parkering og kurve) i basispoint af handlens værdi |
| `backtest.study_holdout_from` | {{settings:backtest.study_holdout_from}} | `radar study score`: datoer fra denne dag er holdout-perioden, som varianter ikke vælges på |
| `backtest.study_min_names` | {{settings:backtest.study_min_names}} | Mindste antal aktier med score og afkast, før en dato tæller i testen |
| `backtest.random_baskets` | {{settings:backtest.random_baskets}} | `radar sim picks`: antal tilfældige kurve, en kurv sammenlignes med |

Se [Simulér stop og take-profit på dine handler](brugervejledning/stop-simulering) og [Test momentumscoren på historikken](brugervejledning/scoretest).

## `risk`: risikostatistik

| Nøgle | Værdi | Betyder |
|---|---|---|
| `risk.windows` | {{settings:risk.windows.1y}} og {{settings:risk.windows.3y}} uger | Vinduerne for 1 og 3 år, på ugentlige afkast i DKK |
| `risk.min_weeks` | {{settings:risk.min_weeks}} | Færre uger giver ingen statistik (tomt, aldrig et gæt) |
| `risk.factors` | {{settings:risk.factors}} | Faktor-ETF'er til faktortilt (som afvigelse fra ACWI) |
| `risk.budget` | {{settings:risk.budget|pct}} | Risikobudget: positionsstørrelsen, hvor et fald til stoppet koster dette af porteføljen |
| `risk.covariance.history_weeks` | {{settings:risk.covariance.history_weeks}} uger | Risikomodellen for et sæt beholdninger (porteføljeforslag og porteføljens røntgen): ugentlige afkast i DKK, som kovariansen regnes på |
| `risk.covariance.min_weeks` | {{settings:risk.covariance.min_weeks}} | Et papir med færre uger er ikke med i risikomodellen; det står som manglende, aldrig som nul risiko |
| `risk.covariance.shrink` | {{settings:risk.covariance.shrink}} | Den andel, kovariansen trækkes mod en matrix med samme korrelation mellem alle par |
| `risk.world_funds` | {{settings:risk.world_funds}} | Brede verdensfonde, der regnes med ACWI's vægte (en tilnærmelse: MSCI World udelader emerging markets) |
| `risk.stress` | | Historiske perioder (Covid-krakket, rentechokket i 2022, momentum-tilbageslaget i sommeren 2024, toldchokket i 2025), som dagens vægte afspilles igennem, hvor kurshistorikken dækker dem |
| `risk.xray.min_coverage` | {{settings:risk.xray.min_coverage|pct}} | Porteføljens røntgen: under denne andel af den investerede værdi i risikomodellen vises ingen risikotal, kun en note |
| `risk.xray.warn_coverage` | {{settings:risk.xray.warn_coverage|pct}} | Under denne andel vises risikotallene med en advarsel om dækningen |
| `risk.xray.pair_corr` | {{settings:risk.xray.pair_corr}} | Par af beholdninger med en ugentlig korrelation over dette vises som papirer, der bevæger sig sammen |

Nøglerne `covariance`, `world_funds` og `stress` lå tidligere under `propose:` (som `history_weeks`, `min_weeks`, `shrink`, `look_through` og `stress`). Har du ændret dem der, så flyt dine værdier hertil; en gammel nøgle under `propose:` giver en fejl ved start, der nævner den. `propose.min_weeks` er blevet: den gælder bootstrappen og puljens korrelation med porteføljen.

Se [Beta, alfa og faktorer](laerebog/beta-og-alfa).

## `attribution`: attribution mod ACWI

Attributionen er under opbygning; indtil videre gemmer radaren ACWI's vægte hver uge, så den senere kan forklare tidligere måneder.

| Nøgle | Værdi | Betyder |
|---|---|---|
| `attribution.snapshot_days` | {{settings:attribution.snapshot_days}} dage | ACWI's beholdningsfil hentes igen, når den er ældre end dette, og ugens vægte (sektor, region, land og valuta) gemmes i historikmappen. iShares viser kun dagens beholdninger, så en uge uden opdatering kan ikke hentes bagefter |
| `attribution.min_proxy_coverage` | {{settings:attribution.min_proxy_coverage|pct}} | En regions afkast bygges af lande-ETF'er vægtet med ACWI's landevægte; dækker landene med en ETF mindre end denne andel af regionen, mangler regionens afkast den dag |

## `analyst`: analytikerkonsensus

`analyst.max_age_days` = {{settings:analyst.max_age_days}}: Yahoos konsensus for beholdninger og watchlist hentes igen, når den er ældre end dette. Hvor gammel konsensus må være, før kursmålene ikke længere bruges, styres af `coverage.max_age.analyst` ({{settings:coverage.max_age.analyst}} dage).

## `coverage`: friskhed og blinde vinkler

### max_age

`coverage.max_age` sætter for hver kilde, hvor mange dage den må være bagud, før den er *stale* og holder op med at tælle. Tabellen med alle grænser står i [Data og dækning](brugervejledning/data-og-daekning). Kurserne har den korteste grænse ({{settings:coverage.max_age.prices}} dage); den bestemmer også, hvornår det gule banner om gamle data vises. OECD har den længste ({{settings:coverage.max_age.oecd}} dage), fordi tallene udgives med omkring to måneders forsinkelse.

### blind_spots

`coverage.blind_spots` er listen over det, radaren ikke ser. Den vises på siden [Data & coverage](/data) og kommer med i `summary.json`, så Claude-skills tager højde for den. Tilføjer du en datakilde, så ret listen.

## `network`: tempo og pauser

Alle forespørgsler til eksterne kilder går gennem ét lag, der holder tempoet pr. websted. Se [Drift: forespørgsler, fejl og pauser](brugervejledning/drift).

### default

Gælder ethvert websted, der ikke står under `hosts`:

| Nøgle | Værdi | Betyder |
|---|---|---|
| `network.default.rate` | {{settings:network.default.rate}} | Forespørgsler pr. sekund |
| `network.default.burst` | {{settings:network.default.burst}} | Antal, der må gå på én gang efter en stille periode |
| `network.default.concurrency` | {{settings:network.default.concurrency}} | Højst så mange samtidig |
| `network.default.retries` | {{settings:network.default.retries}} | Nye forsøg ved 429, 5xx, timeout og forbindelsesfejl |
| `network.default.backoff` | {{settings:network.default.backoff}} | Sekunder før første nye forsøg (fordobles, plus lidt tilfældighed) |
| `network.default.max_wait` | {{settings:network.default.max_wait}} | En ønsket ventetid (`Retry-After`) i sekunder; er den længere, opgives forsøget i stedet |
| `network.default.budget` | ingen | Blødt dagsbudget; overskridelse er en advarsel, aldrig en blokering |

### hosts

`network.hosts` giver bestemte websteder deres egne grænser. Nøglerne er mønstre, fx `"*.yahoo.com"`, og det første mønster, der passer, gælder. Websteder under samme mønster deler grænserne, så alle Yahoos websteder har ét fælles tempo og ét fælles dagsbudget. Langsomme kilder som multpl.com, Damodarans side og AAII har et meget lavt tempo og kun én forespørgsel ad gangen. `api.github.com` (tjekket for nye versioner, se `updates` nedenfor) har også sin egen, lave grænse og kun én forespørgsel ad gangen. Værdierne står direkte i filen.

### cooldown

| Nøgle | Værdi | Betyder |
|---|---|---|
| `network.cooldown.trip` | {{settings:network.cooldown.trip}} | Så mange HTTP 429-svar … |
| `network.cooldown.window_min` | {{settings:network.cooldown.window_min}} | … inden for så mange minutter sætter webstedet på pause |
| `network.cooldown.cooldown_min` | {{settings:network.cooldown.cooldown_min}} | Første pause i minutter; fordobles ved gentagelse samme dag |
| `network.cooldown.max_cooldown_min` | {{settings:network.cooldown.max_cooldown_min}} | Længste pause i minutter |

## `updates`: tjek for nye versioner

| Nøgle | Standard | Betydning |
|---|---|---|
| `updates.repo` | tom (`null`) | Det offentlige GitHub-repo (`ejer/navn`), som tjekket for nye versioner spørger. Uden det er der intet at tjekke, og kortet *New versions* siger det |

Tjekket er slået fra, til du sætter flueben i *Check for a new version once a day* på siden [Data & coverage](/data) eller kører `uv run radar updates --on`. Dit valg gemmes i datamappen, ikke i denne fil. Når det er slået til, spørges GitHub højst én gang om dagen. Se [Dine data, backup og opdatering](brugervejledning/dine-data#tjek-for-nye-versioner).

## `ops`: driftsloggen

| Nøgle | Værdi | Betyder |
|---|---|---|
| `ops.keep_requests_days` | {{settings:ops.keep_requests_days}} | Dage, enkelte forespørgsler gemmes i `ops.db` i cache-mappen |
| `ops.keep_events_days` | {{settings:ops.keep_events_days}} | Dage, hændelser og job gemmes |

## `valuation`: værdiansættelse

| Nøgle | Værdi | Betyder |
|---|---|---|
| `valuation.snapshot_days` | {{settings:valuation.snapshot_days}} | Et nyt P/E-snapshot tages, når det seneste er ældre end dette (ugentligt) |
| `valuation.fallback_max` | {{settings:valuation.fallback_max}} | Højst så mange aktier, Yahoos screener mangler, slås op én ad gangen |
| `valuation.pe_range` | [{{settings:valuation.pe_range}}] | En aktie-P/E uden for intervallet smides væk med en note |
| `valuation.fund_pe_range` | [{{settings:valuation.fund_pe_range}}] | Det samme for fonde |
| `valuation.rel_band` | {{settings:valuation.rel_band|pct}} | P/E mod sektorens median: mere end dette under er billig, over er dyr |
| `valuation.min_peers` | {{settings:valuation.min_peers}} | Mindste antal navne med P/E til en sektormedian |
| `valuation.revision_band` | {{settings:valuation.revision_band|pct}} | En ændring i EPS-estimatet inden for ± dette tæller som uændret |
| `valuation.etf_history_weeks` | {{settings:valuation.etf_history_weeks}} | Ugentlige snapshots, før en ETF's P/E-percentil i egen historik vises |
| `valuation.etf_min_share` | {{settings:valuation.etf_min_share}} | Andel af det seneste snapshots ETF'er, et nyt ETF-snapshot skal have fonddata for. Ellers beholdes det seneste |

Se [Relativ værdiansættelse](laerebog/relativ-vaerdiansaettelse) og [Estimatrevisioner](laerebog/estimatrevisioner).

## `fundamentals`: regnskaber, kvalitets- og værdiscore

| Nøgle | Værdi | Betyder |
|---|---|---|
| `fundamentals.top_n` | {{settings:fundamentals.top_n}} | Navne pr. region på siden *Quality & value* |
| `fundamentals.min_sector_peers` | {{settings:fundamentals.min_sector_peers}} | Et nøgletal rangeres i sektoren (alle regioner samlet), når så mange aktier har det; ellers blandt alle |
| `fundamentals.ttm_max_age_days` | {{settings:fundamentals.ttm_max_age_days}} | Tal for de seneste 12 måneder, der ender længere tilbage end dette, bruges ikke |
| `fundamentals.stability_years` | {{settings:fundamentals.stability_years}} | Regnskabsår bag spredning i bruttoavance, jævn vækst og spredning i ROE |
| `fundamentals.quality.min_pillars` | {{settings:fundamentals.quality.min_pillars}} | Søjler, en kvalitetsscore kræver (lønsomheden skal være med) |
| `fundamentals.value.min_components` | {{settings:fundamentals.value.min_components}} | Værdinøgletal, en værdiscore kræver (FCF yield eller EBIT/EV skal være med) |
| `fundamentals.yahoo.max_per_run` | {{settings:fundamentals.yahoo.max_per_run}} | Aktier, hvis regnskaber hentes fra Yahoo pr. opdatering |
| `fundamentals.edgar.max_per_run` | {{settings:fundamentals.edgar.max_per_run}} | Amerikanske selskaber, der hentes fra SEC EDGAR pr. opdatering |

Vægtene (`quality.weights`, `value.weights`, `financial_value.weights`), branchelisten for banker og forsikring (`financial_industries`) og de rimelige intervaller (`ranges`) står i samme blok. Se [Radarens kvalitets- og værdiscore](laerebog/kvalitetsscore).

## `abtest`: A/B-testen

| Nøgle | Værdi | Betyder |
|---|---|---|
| `abtest.n` | {{settings:abtest.n}} | Aktier pr. kurv, med lige vægte |
| `abtest.max_per_sector` | {{settings:abtest.max_per_sector}} | Højst så mange fra samme sektor i en kurv |
| `abtest.capital` | {{settings:abtest.capital}} | Kroner, hver kurv starter med (virtuelt) |
| `abtest.value_score` | `qv` | `qv`: kvalitets- og værdikurven rangerer på K+V; `value`: kun på værdiscoren |

Ændringer gælder kun for en ny test; en kørende test beholder sine indstillinger. Se [Rigtige og virtuelle porteføljer](brugervejledning/portefoljer-og-tags#ab-test-kvalitet-og-værdi-mod-momentum).

## `sentiment`: put/call og AAII

| Nøgle | Værdi | Betyder |
|---|---|---|
| `sentiment.putcall_backfill_days` | {{settings:sentiment.putcall_backfill_days}} | Dage med CBOE-data, der hentes første gang |
| `sentiment.putcall_retry_days` | {{settings:sentiment.putcall_retry_days}} | En hverdag inden for så mange dage, som radaren ikke har (CBOE havde ikke offentliggjort den, eller svarede ikke), hentes igen ved næste opdatering |
| `sentiment.putcall_lookback_days` | {{settings:sentiment.putcall_lookback_days}} | Dage, gennemsnittet af put/call over 10 dage rangeres over (cirka 3 år) |
| `sentiment.aaii_extreme_pct` | {{settings:sentiment.aaii_extreme_pct}} | Percentil for AAII's bull-bear-spænd: højst dette er ekstrem frygt, mindst 100 minus dette eufori |

Sentiment er kontrært og stemmer aldrig i regimet. Se [Put/call og AAII: kontrær sentiment](laerebog/sentiment).

## `gauges`: graderede aflæsninger

Blokken `gauges` bestemmer, hvordan tal farves efter, hvor tæt de er på deres tærskler (de ni trin fra advarsel til gunstig; se [Data og dækning](brugervejledning/data-og-daekning)). Hver aflæsning har:

| Felt | Betyder |
|---|---|
| `scale` | `diverging` (kan være både god og dårlig) eller `sequential` (envejs-risikomål, kun grå til rød) |
| `anchors` | Punkter [værdi, score]: +1 er grøn (gunstig), −1 rød (advarsel); imellem interpoleres |
| `labels` | Ordene: [øvre grænse, ord], hvor den sidste grænse er `null` |
| `ticks` | Tærskelstregerne på den lille skala og i hjælpeteksten |
| `range` | Skalaens yderpunkter |
| `unit` | `pct`, når værdien er en brøk, der vises som procent |
| `abs_from` | Gradér efter afstanden fra dette midtpunkt (bruges til CFTC-trængsel) |

Eksempler: RSI ({{settings:gauges.rsi14.ticks}} som tærskler), momentumscoren ({{settings:gauges.score.ticks}}), afstanden til stoppet, analytikernes kursmål, P/E mod sektoren, CAPE- og AAII-percentiler. Regimets rækker bygger deres gradering af tærsklerne under `regime:`, så hver tærskel kun står ét sted. Graderingen ændrer ikke selve afstemningen.

## De andre konfigurationsfiler

### universe.yaml

`config/universe.yaml` bestemmer, hvad radaren følger:

- `benchmark`: MSCI ACWI.
- `watchlist`: faste ekstra navne til watchlisten (ud over dem, du stjernemarkerer i appen).
- `sector_etfs`: hvilken sektor-ETF en aktie sammenlignes med på sin tickerprofil, efter Yahoo-sektor og region.
- `etf_groups`: sektorer, regioner, temaer og faktorer, med UCITS-alternativ og ISIN til tjek mod positivlisten.
- `stock_groups`: aktielisterne pr. region (USA er S&P 500).
- `macro`: makrotickere og FRED-serier.
- `external`: CFTC-markeder og OECD-områder.
- `attribution`: de ETF'er, der står i stedet for ACWI's sektorer (MSCI World-sektorfonde, med de amerikanske sektor-ETF'er før deres første kurs) og regioner (lande-ETF'er) i attributionen.

Et symbol, der ikke findes på Yahoo, dukker op under *Missing tickers* på siden [Data & coverage](/data).

### views.yaml

`config/views.yaml` holder skabelonerne til markedssyn (færdige syn med eksponeringer og indikatorer, ordnet i modsatte par) og kataloget over indikatorer, evidenstjekket kan læse, hver med et bånd for "flat". Her står også tærsklerne for sammenhæng: `theme_corr` (en aktie bevæger sig med en ETF ved en korrelation på mindst 0,5), `min_weeks` (26 ugers fælles historik) og `thresholds.aligned` (0,35). Se [Mine markedssyn](brugervejledning/markedssyn).

### discovery.yaml

`config/discovery.yaml` styrer Discover-scanningen: markederne (børser, mindste markedsværdi, mindste antal navne pr. børs), størrelsesgrupper, likviditetsgrænsen for "thin", flag, hvilke børser ETF'er foretrækkes fra, og hvordan ETF'er kategoriseres. Navnelisten bygges igen, når den er ældre end `universe_max_age_days`. Se [Discover](brugervejledning/discover).
