# Stil og konventioner for bøgerne

Denne fil er til den, der skriver eller vedligeholder bøgerne i `guide/`. Den vises ikke i appen.

## Opbygning
- `guide.yaml` bestemmer rækkefølge og titler: bøger → dele → kapitler. Ét kapitel = én fil: `guide/<bog>/<slug>.md`.
- Filen begynder med `# Titel`, præcis som titlen i `guide.yaml`. Derefter `##` for afsnit og `###` for underafsnit (de vises i "På denne side"). `####` bruges sparsomt.
- Et nyt kapitel: tilføj det i `guide.yaml`, opret filen, og kør `uv run pytest -q tests/test_guide.py`.
- Når appen ændrer sig for brugeren (en side, en kolonne, en kommando, en tærskel), opdateres det tilsvarende kapitel i samme ændring.

## Sprog og tone
- Dansk, "du", nøgternt og præcist. Ingen salgssprog, ingen løfter om afkast. Radaren er analyse, ikke rådgivning; skriv aldrig "køb" eller "sælg" som anbefaling.
- Appens brugerflade er på engelsk. Skriv knapper, faner og kolonner præcis som i appen, i kursiv: *Update data*, fanen *Sector rotation*, kolonnen *Score*. Forklar gerne på dansk første gang.
- Korte afsnit. Punktlister, når der er tre eller flere parallelle ting. Tabeller til sammenligninger.
- Decimaler med komma (0,5), tusinder med punktum (20.000), procent med mellemrum ("5 %").
- Fagudtryk på engelsk, der er gængse på dansk (beta, drawdown, momentum, spread, ETF), bruges uden oversættelse; forklar dem første gang.

## Fast terminologi
| Engelsk (appen) | Dansk i bøgerne |
|---|---|
| Regime, risk-on / risk-off | regime, risk-on / risk-off; afstemningen = risk-on/risk-off-afstemningen |
| Mixed | blandet (*Mixed*) |
| Relative Rotation Graph (RRG) | rotationsgraf (RRG) |
| Leading / Weakening / Lagging / Improving | fører / svækkes / halter / forbedres |
| Breadth | markedsbredde |
| Credit spread, high yield | kreditspænd, high yield (HY) |
| Momentum score | momentumscore |
| Trailing stop, take-profit | trailing stop (glidende stop), take-profit (kursmål) |
| Time-weighted / money-weighted return | tidsvægtet afkast (TWR) / pengevægtet afkast (MWR) |
| Positive list | positivlisten (SKATs liste over aktiebaserede investeringsselskaber) |
| Aktiesparekonto / free funds | aktiesparekonto (ASK) / frie midler |
| Mark-to-market taxation | lagerbeskatning |
| Market views | markedssyn |
| Holdings, watchlist | beholdninger, watchlist |
| Benchmark | benchmark (MSCI ACWI) |

## Lærebogens kapitelskabelon
Hvert kapitel i lærebogen har disse afsnit (`##`), i denne rækkefølge, med de afsnit der giver mening:
1. `## Intuition`: hvad og hvorfor, uden formler.
2. `## Teori`: definitioner og formler (KaTeX), evidens og kilder.
3. `## Sådan gør radaren`: præcis metoden som koden gør den (vinduer, tærskler, datakilde) og hvor det ses i appen. Beskriv koden, som den er, også når den afviger fra lærebogsversionen; sig det så.
4. `## Regneeksempel`: et gennemregnet eksempel med tal.
5. `## Faldgruber og begrænsninger`
6. `## Videre læsning`: få, gode kilder (forfatter, titel, år).

Brugervejledningens kapitler har frit format, men typisk: hvad siden viser → sådan læser du den → sådan bruger du den → tips.

## Formler (KaTeX)
- Inline: `$\beta = \frac{\operatorname{cov}(r_i, r_m)}{\operatorname{var}(r_m)}$`. Blok: en linje med `$$`, formlen, en linje med `$$`.
- Brug punktum som decimaltegn inde i formler, og `{{settings:…|raw}}` når en indstilling står i en formel.

## Levende indstillinger
- `{{settings:regime.vix_calm}}` indsætter værdien fra `config/settings.yaml` (dansk decimalkomma).
- `{{settings:regime.oil_shock|pct}}` viser en brøk som procent (0.3 → "30 %").
- `{{settings:risk.min_weeks|raw}}` beholder punktum (til formler).
- Brug dem for alle tærskler og vinduer, der står i `settings.yaml`, så teksten aldrig er forældet. Tærskler, der står fast i koden, skrives som tal med en bemærkning om, at de ligger i koden.

## Links
- Til et andet kapitel: `[RS-Ratio](laerebog/rrg#rs-ratio)` (bog/slug#anker). Ankeret er overskriftens tekst med små bogstaver og bindestreger (æ, ø, å bevares; tegnsætning fjernes): `## Sådan gør radaren` → `#sådan-gør-radaren`.
- Til en side i appen: `[Regime](/regime)`.
- Eksterne links skrives fuldt (`https://…`) og åbner i en ny fane.

## Fremhævninger
- `> **Bemærk:** …` giver en gul boks, `> **Eksempel:** …` en grå, `> **Tip:** …` en blå.
