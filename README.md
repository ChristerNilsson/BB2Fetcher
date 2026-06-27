# BB2Fetcher

Skapar katalogstrukturen `BB2` från `bilder.json` och hämtar bilder från
Bildbank 2. Standardkörningen hämtar bara år `2011`, enligt `spec.md`.

Kör från projektkatalogen:

```powershell
python bb2_fetcher.py
```

Filer som redan finns lämnas orörda, så programmet kan köras igen efter ett
avbrott. Använd `--overwrite` för att hämta om dem.

För att hämta ett annat år:

```powershell
python bb2_fetcher.py --year 2012
```

För att hämta alla år:

```powershell
python bb2_fetcher.py --all-years
```

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

## Date taken

`date_taken.py` skriver bilder i `BB2` som saknar EXIF-fältet
`DateTimeOriginal`, det vill säga normalt “date taken”, till `date_taken.txt`.
Standardurvalet är sökvägar som innehåller `2025-07-12`, och rapporten tar med
alla EXIF-attribut som hittas för varje listad fil.

```powershell
python date_taken.py
```

Övriga alternativ visas med:

```powershell
python bb2_fetcher.py --help
python fetch_files.py --help
python stavfel.py --help
python date_taken.py --help
```
