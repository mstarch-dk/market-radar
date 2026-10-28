Market Radar: dine data
=======================

Denne mappe er dine egne data. Den ligger uden for programmappen, så du kan
skifte til en ny version af Market Radar uden at miste noget.

  radar.db        dine porteføljer, handler, markedssyn, watchlist og valg
  notes/          dine noter og investorprofil (til Claude-skills)
  briefs/         markedsbriefs
  research/       research-notater og sammenligninger
  journal/        beslutningsjournal
  exports/        eksporter og sammenligninger
  imports/        filer fra din bank/mægler
  history/        historik radaren har samlet over tid (kan ikke hentes igen)
  backups/        automatiske sikkerhedskopier
  market-radar.json   hvilken version der sidst brugte mappen

Markedsdata (kurser m.m.) ligger i en cache-mappe et andet sted; den kan
slettes og hentes igen. Kør "uv run radar paths" for at se hvor.

Tag backup af hele denne mappe. Læg den ikke direkte i OneDrive, iCloud eller
Dropbox: en database der synkroniseres mens den er i brug kan gå i stykker.
Læg i stedet backups der (se guiden: Dine data, backup og opdatering).
