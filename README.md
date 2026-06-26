# BB2Fetcher

Skapar hela katalogstrukturen `BB2` från `bilder.json` och hämtar samtliga
bilder från Bildbank 2.

Kör från projektkatalogen:

```powershell
python bb2_fetcher.py
```

Filer som redan finns lämnas orörda, så programmet kan köras igen efter ett
avbrott. Använd `--overwrite` för att hämta om dem.

Under körningen visas en löpande prognos med beräknad sluttid. Prognosen bygger
på den faktiska hastigheten sedan programmet startade och blir därför
stabilare efter en stund.

För att bara skapa och kontrollera katalogstrukturen utan att hämta bilder:

```powershell
python bb2_fetcher.py --dry-run
```

## Filer

`fetch_files.py` läser `json/file_index.txt` och hämtar alla `files/...`-poster
till `BB2/files` från:

```text
https://storage.googleapis.com/bildbank2/files/
```

Kör:

```powershell
python fetch_files.py
```

Externa URL:er i indexet hoppas över eftersom de inte matchar Google
Storage-mallen i `spec_files.md`. Programmet skriver ut varje fil som hämtas,
hoppar över befintliga filer och kan köras om efter avbrott.

## Stavfel

`stavfel.py` listar misstänkta stavfel i `BB2`, förutom katalogen `BB2/files`,
och skriver ut vilken ändring som föreslås. Programmet analyserar bara fil- och
katalognamn, genomför inga ändringar, loggar till `stavfel.txt` och avbryter
efter 1000 träffar.
Utöver fasta regler görs en generell kontroll av namn som ligger nära
`Josefina`, till exempel `Josrfina` och liknande varianter.
Rapporten listar också alla ord som bara förekommer en gång i det analyserade
materialet. Varje engångsord visas med ett filnummer, och filnumren listas med
full sökväg längst ned i rapporten.
Korrekta ord kan filtreras bort med `--word-list`, och medlems-/namnlistor kan
anges med `--member-list`. Båda alternativen accepterar fil eller URL och kan
anges flera gånger. Verktyget använder också återkommande ord i materialet som
lokala referenser för automatiska förslag, vilket fångar namnvarianter som
felstavningar av `Alexandra`/`Alexander`.

```powershell
python stavfel.py
```

Övriga alternativ visas med:

```powershell
python bb2_fetcher.py --help
python fetch_files.py --help
python stavfel.py --help
```
