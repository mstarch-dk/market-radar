# Månedsbriefen i GitHub

Har du Market Radar i dit eget GitHub-repository, kan markedsbriefen skrive sig selv. Den første i hver måned starter en GitHub Actions-workflow, der henter friske data, lader Claude skrive briefen efter samme opskrift som `/market-brief` og lægger resultatet frem som en pull request, du kan læse og flette. Du behøver ikke have din computer tændt.

Opsætningen kræver lidt teknisk erfaring med GitHub. Bruger du kun appen på din egen computer, kan du springe kapitlet over og køre `/market-brief` i Claude Code i stedet; se [Claude Code-skills](brugervejledning/claude-code).

## Sådan kører den

Workflowen ligger i `.github/workflows/monthly-brief.yml` og hedder *Monthly market brief*. Den starter kl. 06.00 UTC den 1. i hver måned. Du kan også starte den selv fra fanen *Actions* på GitHub eller med `gh workflow run monthly-brief.yml`.

Trinene er:

1. **Tests**: radarens tests køres først (`uv run pytest -q`). Fejler de, stopper kørslen.
2. **Gendan dine beholdninger**: `uv run radar unbundle-holdings` pakker hemmeligheden `HOLDINGS_BUNDLE` ud, så GitHub kender dine porteføljer, din watchlist og dine markedssyn. Mangler hemmeligheden, kører briefen uden beholdninger.
3. **Opdater radaren**: `uv run radar run` henter data og bygger `reports/summary.json`.
4. **Skriv briefen**: Claude følger `.claude/skills/market-brief/SKILL.md`, læser `summary.json`, søger på nettet og skriver `briefs/ÅÅÅÅ-MM-DD.md`.
5. **Gem rapporten**: mappen `reports/` uploades som artefaktet *radar-dashboard*, som gemmes i 90 dage. Du kan hente den og se den lokalt med `uv run radar serve`.
6. **Pull request**: briefen og de nye rangsnapshots i `data/snapshots/` lægges på en gren `brief/ÅÅÅÅ-MM-DD`, og der åbnes en pull request med briefens TL;DR som beskrivelse og et link til kørslen.

En kørsel stoppes, hvis den tager mere end 45 minutter.

## Opsætning

Du skal bruge to hemmeligheder (*Settings → Secrets and variables → Actions* i dit repository):

| Hemmelighed | Indhold |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Adgangen til Claude, som workflowen skriver briefen med |
| `HOLDINGS_BUNDLE` | Dine porteføljer, watchlist og markedssyn, pakket af `radar bundle-holdings` |

### HOLDINGS_BUNDLE

Den nemmeste vej er at lade radaren sætte hemmeligheden direkte. Det kræver GitHub CLI (`gh`), logget ind på dit repository:

```
uv run radar bundle-holdings --set-secret
```

Uden `--set-secret` skriver kommandoen bundtet i terminalen (som base64-tekst), så du selv kan indsætte det som hemmelighed på GitHub.

Bundtet er et øjebliksbillede. Kør kommandoen igen, når du har ændret noget, du vil have briefen til at se: efter en import, nye handler, ændringer i watchlisten eller nye markedssyn.

## Hvad bundtet indeholder

| Fil i bundtet | Indhold |
|---|---|
| `portfolios.json` | Dine rigtige porteføljer med type, skattetype og tags |
| `portfolio_transactions.csv` | Alle rækker i de porteføljer, også arkiverede |
| `watchlist.csv` | Dine watchlist-ændringer fra appen |
| `yahoo_watch.json` | Watchlisten fra din seneste Yahoo-import |
| `views.json` | Dine markedssyn |
| `regime_votes.json` | Hvilke indikatorgrupper der stemmer i regimet (dit valg på siden [Regime](/regime)) |

Virtuelle porteføljer er udeladt. Vil du have dem med, så brug `uv run radar bundle-holdings --set-secret --include-virtual`. Selv da tæller de ikke som dine i briefen, der kun ser dine rigtige porteføljer.

Bundtet indeholder ikke `notes/`, så briefen på GitHub kender hverken din investorprofil (`notes/investor.md`) eller dine læsenoter.

## Hvad briefen indeholder

Briefen følger samme skabelon som `/market-brief` på din egen computer:

- TL;DR med de vigtigste ændringer og hvorfor.
- Regime, positionering og cyklus.
- Rotation i sektorer, regioner og temaer, med UCITS-alternativer og positivliste-status.
- Nye momentumledere og, når Discover-scanningen er frisk, nye navne uden for radarens lister (kun lokalt, se nedenfor).
- Dine markedssyn mod data.
- Din portefølje i den sammenhæng: hver rigtig porteføljes afkast mod ACWI, flag på beholdningerne, watchlist-navne der vender op, og hvordan solgte navne har klaret sig siden salget.
- En kø af navne til `/research`.

Alle påstande om nyheder skal have et kildelink. Briefen er analyse, ikke rådgivning.

> **Bemærk:** På GitHub må Claude kun læse og skrive filer, søge på nettet og køre `uv run radar info`. Den kan derfor ikke køre `radar views`, så dine markedssyn ses kun gennem afsnittet om markedssyn i `radar info` for de navne, briefen slår op. Discover-scanningen køres ikke på GitHub, så afsnittet om nye navne udelades. Den lokale `/market-brief` har ikke de begrænsninger.

## Privatliv

Briefen handler om dine penge, så tænk over, hvor den ender:

- **Hemmeligheden** `HOLDINGS_BUNDLE` er krypteret hos GitHub og kan ikke læses igen fra webgrænsefladen, kun bruges af workflows i dit repository.
- **Briefen** nævner dine beholdninger og porteføljers afkast. Den lægges i en pull request i dit repository, så repositoryet skal være privat.
- **Artefaktet** *radar-dashboard* indeholder `summary.json` med dine beholdninger og afkast. Alle med adgang til repositoryet kan hente det i 90 dage.
- **Lokalt** er `briefs/` udeladt fra git; workflowen tilføjer kun sin egen brief med vilje (`git add -f`). Den offentlige udgave af Market Radar udelader `briefs/`, `journal/` og `notes/`.

Vil du ikke have dine beholdninger på GitHub, så lad være med at sætte `HOLDINGS_BUNDLE`. Briefen dækker så kun markedet.

## Når noget går galt

- **"No brief was written"**: Claude skrev ingen fil. Se loggen for trinnet *Write brief with Claude* under kørslen på fanen *Actions*.
- **Testene fejler**: kørslen stopper før data hentes. Ret fejlen, og start workflowen igen.
- **Briefen ser gamle beholdninger**: kør `uv run radar bundle-holdings --set-secret` igen.
- **Bundtet kan ikke læses**: radaren tåler mellemrum og linjeskift, som en terminal kan have tilføjet, men et afkortet bundt kan ikke læses. Sæt hemmeligheden igen med `--set-secret`.
