## Intro 

Skapa filen replace.py

Gå igenom alla katalognamn i BB2 förutom files.

## Hantering av I, F, R och L

Om en sträng av typen _I12345 förekommer, ta bort den och lägg till den filen i katalogen.
Exempel:

```BB2\2021\2021-08-09 Uppsala Chess Festival_T08792_I10486```

Ersätts med 
```BB2\2021\2021-08-09 Uppsala Chess Festival_T08792```

Om 10486 motsvarar filen `files/Inbjudan_Uppsala_Schackfestival_2021.pdf`

kopieras `files/Inbjudan_Uppsala_Schackfestival_2021.pdf`. Dessutom byts namn till `Inbjudan`. Ändelsen behålles oförändrad.

Om 10486 däremot är en länk ska filen Inbjudan.url skapas med korrekt innehåll

Gör samma sak med F12345. Filen ska heta Fakta + ändelse.

Gör samma sak med R12345. Filen ska heta Resultat + ändelse.

Gör samma sak med L12345. Filen ska heta Länk + ändelse.

## Hantering av T, C och V

Om en sträng av typen _T18469 förekommer, ta bort den och lägg till en url-fil i katalogen innehållande
```https://member.schack.se/ShowTournamentServlet?id=18469&listingtype=2```
Filnamn: Turnering.url

Om en sträng av typen _C967022 förekommer, ta bort den och lägg till en url-fil i katalogen innehållande
```https://chess-results.com/tnr967022.aspx?lan=6&art=4```
Filnamn: Chess-Results.url

Om en sträng av typen _V718763090 förekommer, ta bort den och lägg till en url-fil i katalogen innehållande
```https://player.vimeo.com/video/718763090```
Filnamn: Video.url

## Outro

Nu ska pythonfilen vara skarp.
Jag vill själv exekvera pythonfilen.