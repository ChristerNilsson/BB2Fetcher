Skapa filen replace.py

Gå igenom alla katalognamn i BB2 förutom files.

Om en sträng av typen _I12345 förekommer, ta bort den och lägg till den filen i katalogen.
Exempel:

```BB2\2021\2021-08-09 Uppsala Chess Festival_T08792_I10486```

Ersätts med 
```BB2\2021\2021-08-09 Uppsala Chess Festival_T08792```

Om 10486 motsvarar filen `files/Inbjudan_Uppsala_Schackfestival_2021.pdf`

kopieras `files/Inbjudan_Uppsala_Schackfestival_2021.pdf`. Dessutom byts namn till `Inbjudan`. Ändelsen behålles oförändrad.

Om 10486 däremot är en länk ska file Inbjudan.url skapas med korrekt innehåll

Gör samma sak med F12345. Filen ska heta Fakta + ändelse.

Gör samma sak med R12345. Filen ska heta Resultat + ändelse.

Nu ska pythonfilen vara skarp.
Jag vill själv exekvera pythonfilen.