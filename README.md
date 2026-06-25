# BB2Fetcher

Skapar katalogstrukturen `BB2/2011` från `bilder.json` och hämtar bilderna
från Bildbank 2.

Kör från projektkatalogen:

```powershell
python bb2_fetcher.py
```

Filer som redan finns lämnas orörda, så programmet kan köras igen efter ett
avbrott. Använd `--overwrite` för att hämta om dem.

För att bara skapa och kontrollera katalogstrukturen utan att hämta bilder:

```powershell
python bb2_fetcher.py --dry-run
```

Övriga alternativ visas med:

```powershell
python bb2_fetcher.py --help
```
