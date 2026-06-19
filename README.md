# Orari Agent

Agente di pianificazione settimanale per:

- **CarpEvolution Store**
- **Tenuta del Germano**

Il progetto genera un orario settimanale in italiano e può creare un **PDF** pronto da condividere manualmente. Non serve una grafica: su Windows e Mac basta modificare un file e avviare il programma con doppio clic.

## Uso rapido per Giammarco

1. Apri la cartella del progetto.
2. Apri il file `input/weekly_plan.yaml`.
3. Modifica assenze, eventi, note e preferenze della settimana.
4. Salva il file.
5. Fai doppio clic sul launcher corretto:
   - Windows: `avvia_orari_windows.bat`
   - Mac: `avvia_orari_mac.command`
6. Trova il PDF generato nella cartella `output/`.

## Installazione e avvio su Windows

1. Scarica o clona il progetto sul PC.
2. Se non lo hai già, installa **Python 3.11 o superiore** da <https://www.python.org/downloads/windows/>.
   - Durante l'installazione, seleziona l'opzione **Add python.exe to PATH**.
3. Apri la cartella del progetto.
4. Modifica il file `input/weekly_plan.yaml` con la pianificazione della settimana.
5. Fai doppio clic su `avvia_orari_windows.bat`.
6. Attendi la fine dell'esecuzione.
7. Il PDF sarà nella cartella `output/`.

Il launcher Windows controlla Python, crea un ambiente locale `.venv`, prova a installare il progetto se necessario e genera il PDF usando `input/weekly_plan.yaml`. Se l’installazione automatica non riesce, prova comunque a usare i file locali del progetto.

## Installazione e avvio su Mac

1. Scarica o clona il progetto sul Mac.
2. Se non lo hai già, installa **Python 3.11 o superiore** da <https://www.python.org/downloads/macos/>.
3. Apri la cartella del progetto.
4. Modifica il file `input/weekly_plan.yaml` con la pianificazione della settimana.
5. Fai doppio clic su `avvia_orari_mac.command`.
6. Attendi la fine dell'esecuzione.
7. Il PDF sarà nella cartella `output/`.

Il launcher Mac controlla Python 3, crea un ambiente locale `.venv`, prova a installare il progetto se necessario e genera il PDF usando `input/weekly_plan.yaml`. Se l’installazione automatica non riesce, prova comunque a usare i file locali del progetto.

Se macOS avvisa che il file non può essere aperto perché proviene da uno sviluppatore non identificato, apri la cartella, fai clic destro su `avvia_orari_mac.command`, scegli **Apri** e conferma.

## Dove modificare la pianificazione settimanale

Il file da modificare ogni settimana è:

```text
input/weekly_plan.yaml
```

Puoi scrivere assenze, eventi, necessità extra e note. Esempio:

```yaml
week_start: 2026-06-15

absences:
  Lorenzo Sansavini:
    - day: venerdì
      period: full_day
      reason: ferie

lake:
  extra_coverage:
    - day: domenica
      period: full_day
      reason: lago pieno di prenotazioni

notes:
  - "PDF pronto per WhatsApp."
```

## Dove trovare il PDF

Dopo il doppio clic sul launcher, il PDF viene creato in:

```text
output/
```

Il nome del file segue questo formato:

```text
Orario_CarpeEvolution_Tenuta_YYYY-MM-DD.pdf
```

La data nel nome deriva da `week_start` dentro `input/weekly_plan.yaml`.

## PDF operativo per WhatsApp/Telegram

Il PDF settimanale usa un layout stabile basato su **ReportLab Platypus** (`SimpleDocTemplate`, `Table`, `Paragraph`, `Spacer` e `PageBreak`) invece di un renderer manuale a coordinate assolute. L'output predefinito privilegia la leggibilità rispetto alla compressione in una sola pagina: per una settimana normale il PDF è pensato come documento **A4 verticale di 2 pagine**, con pagina 1 dedicata all'orario e pagina 2 dedicata a riepiloghi, note, conflitti, alert e memorie operative. Se una settimana molto piena non entra nella prima pagina, ReportLab lascia continuare l'orario su una pagina aggiuntiva e sposta il riepilogo alla pagina successiva.

Il PDF settimanale è in formato **A4 verticale** e usa un layout a **card giornaliere**, pensato per sembrare un calendario operativo e non una tabella grezza del database. Ogni card mostra subito il giorno, la data e due sezioni principali: **LAGO** e **NEGOZIO**. Se necessario può comparire anche una sezione compatta per il **LAVORO ESTERNO**.

Dentro ogni sezione il PDF mostra una sola riga per **persona + sede + giorno** quando i turni appartengono alla stessa sede. Se una persona copre più intervalli nello stesso giorno e nello stesso luogo, gli intervalli vengono uniti nella stessa riga. Esempio: invece di due righe separate `14:00-15:00` e `16:30-18:30`, la card mostra `14:00-15:00 / 16:30-18:30`.

Il PDF non forza piu tutta la settimana in una sola pagina: la leggibilita ha priorita sulla compressione. La versione ufficiale privilegia una struttura A4 verticale leggibile: pagina 1 contiene le card giornaliere, mentre la pagina di riepilogo contiene monte ore, note, conflitti e alert; le settimane molto piene possono creare pagine di continuazione senza omettere turni.

Dentro ogni sezione il PDF usa ora una piccola tabella ReportLab allineata, con tre colonne:

```text
Persona | Turno / Pausa / Compito | Ore
```

La colonna centrale contiene orario, pausa e compito in testo semplice, ad esempio `07:30-16:30 | pausa 14:00-15:00 | APERTURA LAGO`. La colonna **Ore** resta separata e allineata a destra, così le ore giornaliere sono più facili da scorrere visivamente anche quando il dettaglio del turno va a capo.

Esempi di righe leggibili:

- `Lorenzo Sansavini | 07:30-16:30 | pausa 14:00-15:00 | APERTURA LAGO | 8h 00m`;
- `Angelo Antonelli | 09:00-12:30 / 15:30-19:30 | pausa 12:30-15:30 | NEGOZIO | 7h 30m`;
- `Gianmarco Mengozzi | 14:00-15:00 / 16:30-18:30 | pausa - | LAGO + CHIUSURA LAGO | 3h 00m`.

Le giornate chiuse restano compatte, ad esempio `LUNEDI 22/06` seguito da `Lago chiuso | Negozio chiuso`, senza grandi box vuoti.

Le barre unicode della vecchia timeline sono state rimosse: il PDF usa solo testo semplice, ad esempio `07:30-16:30` oppure `09:00-12:30 / 15:30-19:30`, per evitare punti interrogativi su telefono e anteprime PDF. Una copertura breve `14:00-15:00` viene indicata come lavoro, non come pausa: la colonna `Pausa` resta `-` se quella persona sta coprendo davvero quell'intervallo.

La **pagina 1** contiene l'intestazione e le card giornaliere dell'orario settimanale, da lunedì a domenica. La **pagina 2** contiene `RIEPILOGO MONTE ORE`, `NOTE OPERATIVE`, `CONFLITTI CRITICI`, `ALERT INFORMATIVI` e `MEMORIE OPERATIVE APPLICATE`. Se una settimana estrema contiene troppe note o troppe righe operative, il PDF può creare una pagina di continuazione senza omettere turni e il riepilogo slitta alla pagina successiva.

I conflitti critici restano separati dagli alert informativi. Sono conflitti critici, ad esempio, coperture mancanti, sovrapposizioni incompatibili, apertura lago di Gianmarco in una data con codice moglie `M`, o assegnazioni su giorni chiusi senza apertura esplicita. Sono invece alert informativi gli scostamenti di Lorenzo dal target 40 ore o i turni lunghi.

### Apertura serale stagionale lago 2026

Dal **22 giugno 2026** al **30 settembre 2026** compresi, la Tenuta del Germano resta aperta fino alle **23:00** ogni:

- **venerdì**;
- **domenica**.

Questa è una regola operativa reale per aperitivi, cene ed eventi serali: il motore aggiunge copertura lago obbligatoria `18:30-23:00` e il PDF mostra l’intestazione `Lago aperto 07:30-23:00 (evento serale)`.

Se nessuno è disponibile, il PDF viene comunque generato e compare un conflitto critico: `Copertura mancante evento serale lago dalle 18:30 alle 23:00.` La copertura serale conta nel monte ore settimanale come lavoro reale.

Per rendere i turni sostenibili con le tre persone attuali, il generatore usa una rotazione deterministica basata sulla settimana:

- **venerdì stagionale**: Angelo resta in negozio fino alle `19:30` e viene aggiunto come supporto lago serale predefinito `20:00-22:00`; Gianmarco e Lorenzo sono i due operatori principali del lago, uno in apertura lunga e uno in chiusura fino alle `23:00`;
- **domenica stagionale**: il negozio è chiuso e tutti e tre possono lavorare al lago con turni lunghi scaglionati, ad esempio `07:30-21:00`, `09:00-22:00`, `11:00-23:00`;
- la rotazione evita, in modo semplice e ripetibile, che la stessa persona apra o chiuda sempre;
- se l'utente dà una fascia esplicita, ad esempio `Venerdì sera Angelo al lago dalle 19:30 alle 23`, quella richiesta viene rispettata se non crea sovrapposizioni personali.

Etichette semplici usate nella colonna `Compito`:

- `APERTURA LAGO`, `CHIUSURA LAGO`, `LAGO`;
- `EVENTO SERALE LAGO`, `CHIUSURA LAGO 23:00`;
- `APERTURA NEGOZIO`, `CHIUSURA NEGOZIO`, `NEGOZIO`;
- `LAVORO ESTERNO`;
- `TURNO LUNGO` quando un turno effettivo supera le 8 ore.

Il calcolo del monte ore usa il tempo di lavoro reale e sottrae le pause note. Esempi:

- `09:00-12:30 / 15:30-19:30` = **7h 30m**;
- `07:30-16:30` con pausa `14:00-15:00` = **8h 00m**;
- lavoro esterno di Gianmarco conta come lavoro;
- ferie e assenze non contano come lavoro.

### Target Lorenzo 40 ore

Per Lorenzo le **40 ore settimanali sono un target di monitoraggio, non un vincolo bloccante**. Il programma può generare l'orario anche se Lorenzo lavora meno di 40 ore, più di 40 ore o più di 8 ore in un giorno. Il PDF e il riepilogo Telegram lo rendono visibile:

- `OK 40h` se Lorenzo è esattamente a 40 ore;
- `ATTENZIONE: Lorenzo sotto target...` se è sotto;
- `ATTENZIONE: Lorenzo sopra target...` se è sopra;
- `TURNO LUNGO` sul turno se supera le 8 ore giornaliere.

Questi sono **alert informativi**, non conflitti critici. I conflitti critici restano invece coperture mancanti, sovrapposizioni incompatibili, apertura lago di Gianmarco in data con codice moglie `M`, o assegnazioni in giorni chiusi senza apertura esplicita.

Esempi di frasi operative:

```text
Martedì Gianmarco apre il lago
Sabato Lorenzo lavora 07:30-18:30
Settimana prossima Lorenzo può fare straordinario
```

La frase sullo straordinario salva una nota operativa (`Straordinario Lorenzo autorizzato`), ma lo straordinario non richiede una parola di sblocco: se il turno serve, viene calcolato e mostrato comunque.

## Cosa fare se c'è un errore

La finestra del launcher resta aperta alla fine, così puoi leggere il messaggio.

Controlla in particolare:

- che Python 3.11 o superiore sia installato;
- che il file `input/weekly_plan.yaml` esista;
- che il file YAML sia scritto con spazi corretti e senza tab;
- che i nomi dei giorni siano in italiano, per esempio `lunedì`, `martedì`, `mercoledì`;
- che i nomi delle persone siano `Angelo Antonelli`, `Lorenzo Sansavini` o `Giammarco Mengozzi`.

Se il PDF viene comunque generato con avvisi, aprilo e controlla le note: possono indicare coperture mancanti, conflitti o regole non rispettate.

## Struttura semplice per l'uso quotidiano

- `input/` — contiene il file da modificare ogni settimana.
- `input/weekly_plan.yaml` — pianificazione settimanale modificabile.
- `output/` — qui viene salvato il PDF generato.
- `examples/` — contiene esempi di pianificazione.
- `avvia_orari_windows.bat` — launcher con doppio clic per Windows.
- `avvia_orari_mac.command` — launcher con doppio clic per Mac.

## Pianificazione settimanale con file YAML/JSON

Il file può essere YAML o JSON. Se contiene `week_start`, quella data viene usata automaticamente per calendario moglie di Giammarco e nome PDF; `--week-start` può comunque sovrascriverla da riga di comando.

Sezioni supportate:

- `absences`: assenze di Angelo, Lorenzo o Giammarco con `day`, `period` (`full_day`, `morning`, `afternoon`) e `reason` opzionale.
- `giammarco.preferred_shop_days`: giorni in cui Giammarco è preferito in negozio.
- `giammarco.company_work`: impegni aziendali esterni che non valgono come copertura fissa.
- `lake.events`, `lake.extra_coverage`, `lake.exceptional_openings`, `lake.exceptional_closures`.
- `shop.special_needs`, `shop.exceptional_openings`, `shop.exceptional_closures`.
- `manual_coverage` o `lake.manual_coverage` / `shop.manual_coverage`: coperture forzate con `person`, `day`, `period`, `activity` quando serve nella sezione globale, e `reason`.
- `notes`: note settimanali stampate nell'output e nel PDF.

## CLI ancora disponibile

La riga di comando esistente continua a funzionare.

Esempio con file settimanale e PDF:

```bash
PYTHONPATH=src python -m orari_agent --planning-file input/weekly_plan.yaml --pdf --output output
```

Esempio con testo libero:

```bash
PYTHONPATH=src python -m orari_agent "Domenica Lorenzo è assente"
```

Dopo installazione locale:

```bash
pip install -e .
orari-agent --planning-file input/weekly_plan.yaml --pdf --output output
```

## Priorità operative predefinite

1. **Angelo Antonelli** copre il negozio di default.
2. **Lorenzo Sansavini** copre il lago di default, con 5 giorni e 40 ore settimanali.
3. **Giammarco Mengozzi** è general manager / CEO dell’operazione: lavora sempre per l’azienda, ma viene contato come copertura fissa solo quando è assegnato a lago o negozio. Se serve copertura e non ci sono istruzioni esplicite, la priorità è il lago.

Il motore prova a mantenere sempre almeno una persona al lago e una persona in negozio durante gli orari di apertura. Se una combinazione di assenze rende impossibile coprire tutto con le sole tre persone disponibili e con i vincoli di Lorenzo, l'orario viene comunque generato e il validatore evidenzia l'intervallo scoperto.

## Istruzioni testuali supportate

Il parser leggero riconosce frasi italiane o inglesi con giorno, persona e intenzione. È deterministico, non usa API AI esterne e conserva sempre il testo originale della nota. Le istruzioni possono essere passate in un unico testo, separate da punto o a capo.

Pattern operativi ora supportati:

- **Assenza per giornata intera**: `Sabato Angelo non c’è`, `Venerdì Lorenzo è assente`, `Giovedì io non ci sono`, `Martedì Gianmarco non c’è tutto il giorno`. La persona viene esclusa da coperture lago/negozio per tutto il giorno.
- **Assenza o uscita su fascia oraria**: `Angelo non c’è martedì mattina`, `Lorenzo non c’è sabato pomeriggio`, `Sabato Lorenzo deve uscire alle 15`. Mattina/pomeriggio usano le fasce dell’attività quando l’attività è chiara; le uscite `alle HH` bloccano la persona da quell’ora in poi.
- **Impegni esterni di Giammarco**: `Giovedì io sono dal commercialista dalle 10 alle 12`, `Venerdì Gianmarco in banca dalle 9 alle 11`, `Martedì io ho appuntamento dal commercialista alle 10`, `Mercoledì Gianmarco attività aziendale esterna tutto il giorno`. L’impegno compare come lavoro aziendale/esterno e impedisce coperture fisse sovrapposte.
- **Copertura forzata negozio**: `Giovedì Gianmarco in negozio tutto il giorno per fatture`, `Sabato Angelo deve stare in negozio il pomeriggio`, `Martedì Angelo apre il negozio`, `Venerdì Gianmarco negozio mattina`. `apre il negozio` significa 09:00-12:30; `chiude il negozio` significa 15:30-19:30.
- **Copertura forzata lago**: `Martedì Lorenzo deve aprire il lago`, `Domenica Gianmarco apre il lago`, `Sabato Lorenzo chiude il lago`, `Venerdì Gianmarco lago pomeriggio`, `Domenica serve Angelo al lago la mattina`. `apre il lago` significa 07:30-14:00; `chiude il lago` significa 14:00-18:30.
- **Carico alto al lago / copertura extra**: `Domenica al lago ci sono molte prenotazioni`, `Sabato lago pieno`, `Domenica serve doppia copertura al lago`. Il PDF mostra una nota di attenzione e il motore prova ad aggiungere Giammarco come supporto extra se è disponibile e non bloccato dal calendario moglie.
- **Regole speciali Lorenzo**: `Martedì Lorenzo deve lavorare`, `Martedì Lorenzo deve aprire il lago`, `Domenica Lorenzo non c’è`, `Sabato Lorenzo deve uscire alle 15`. Il motore monitora il target 40 ore/5 giorni/8 ore come informazione: l’orario viene generato anche sotto o sopra target e il PDF evidenzia gli alert.
- **Calendario moglie codice M**: se una nota forza `Gianmarco apre il lago` in una data con codice `M`, il motore non lo assegna all’apertura 07:30 e genera un conflitto esplicito.

Esempio CLI veloce:

```bash
PYTHONPATH=src python -m orari_agent "Giovedì io sono dal commercialista dalle 10 alle 12. Domenica al lago ci sono molte prenotazioni."
```

## Esempi di comportamento

- Se **Giammarco è richiesto in negozio** in un giorno in cui Lorenzo è al lago, il negozio viene coperto da Giammarco e Angelo può essere spostato sulla chiusura del lago 16:30-18:30.
- Se **Lorenzo è assente domenica**, il motore sposta il suo quinto giorno sul martedì per conservare 5 giorni e 40 ore, mentre Giammarco copre il lago la domenica.
- Se **Angelo è in ferie sabato**, Giammarco copre il negozio. La chiusura lago 16:30-18:30 viene evidenziata se resta scoperta; Lorenzo può comunque superare 8 ore se una nota operativa lo assegna a un turno più lungo.
- Se **Giammarco è dal commercialista, in banca, dai fornitori o in amministrazione**, l’impegno viene registrato come lavoro aziendale esterno e non vale come copertura fissa di lago o negozio.

## Struttura tecnica

- `src/orari_agent/business_rules.py` — regole di apertura, orari e vincoli fissi.
- `src/orari_agent/people.py` — persone, ruoli e vincoli individuali.
- `src/orari_agent/generator.py` — generazione e riequilibrio dell'orario settimanale.
- `src/orari_agent/validator.py` — controlli su coperture e conflitti critici.
- `src/orari_agent/formatter.py` — output italiano leggibile.
- `src/orari_agent/pdf_exporter.py` — generazione PDF A4 verticale operativo, separata dal motore di scheduling.
- `src/orari_agent/wife_calendar.py` — regole del calendario persistente della moglie di Giammarco.
- `src/orari_agent/wife_calendar_ocr.py` — lettura locale, opzionale e prudente della foto calendario moglie.
- `src/orari_agent/weekly_input.py` — parser leggero delle istruzioni in linguaggio naturale e dei file YAML/JSON settimanali.
- `src/orari_agent/presentation.py` — conversione dai blocchi interni ai turni effettivi e calcolo monte ore.

## Limiti intenzionali

- Non è stata creata una app grafica completa.
- L'invio automatico WhatsApp non è implementato: il PDF va condiviso manualmente.
- L'OCR automatico della tabella moglie è locale e prudente: propone date candidate ma non le salva senza conferma; se la foto o le dipendenze non permettono una lettura sicura, il bot chiede di usare `/moglie_importa_m`.
- Il parser non è un NLP completo: riconosce pattern ricorrenti e conserva come note non interpretate le frasi non supportate.
- Non vengono introdotte risorse esterne oltre ad Angelo, Giammarco e Lorenzo.

## Nota sul calendario della moglie di Giammarco

Il calendario moglie può essere inserito manualmente oppure tramite foto dal bot Telegram. La regola operativa resta una sola: **viene importato e applicato solo il codice `M`**. Se una data contiene `M`, Giammarco non può aprire il lago alle 07:30 in quella data. I codici `P`, `I`, `F`, colori, celle rosse, celle vuote o altre marcature vengono ignorati.

### Import manuale sempre disponibile

Il comando manuale non cambia e rimane il metodo più sicuro quando la foto non è leggibile:

```text
/moglie_importa_m 2026-09-03,2026-09-10
```

### Import automatico da foto Telegram

1. Scrivi `/importa_calendario_moglie`.
2. Invia la foto della tabella.
3. Il bot salva sempre la foto ricevuta in `data/imports/`.
4. Il bot prova una lettura locale della griglia e mostra solo le date candidate con `M` se la confidenza è alta.
5. Le date candidate **non vengono salvate subito**: controlla il messaggio e conferma solo se sono corrette con `/conferma_calendario_moglie`.
6. Dopo la conferma, controlla il risultato con `/moglie_lista M`.

Se la lettura è sicura, il bot risponde con un riepilogo tipo “Calendario moglie letto automaticamente”, il numero di date `M` candidate, la confidenza OCR e l’avviso che non sono ancora salvate. Se la confidenza è bassa, **non salva automaticamente nessuna data** e chiede di mandare una foto migliore o usare `/moglie_importa_m`.

### Come fare una buona foto

- Tieni il foglio il più possibile **dritto**, non ruotato e non inclinato.
- Inquadra tutta la tabella, compresi intestazioni, righe dei mesi e colonne dei giorni.
- Usa buona luce, evita ombre, riflessi e sfocatura.
- Avvicinati abbastanza perché le lettere nelle celle siano leggibili.
- Evita pieghe o prospettive molto storte: una foto frontale aumenta molto la confidenza.

### Dipendenze OCR locali

L'avvio del bot non richiede OCR obbligatorio. Il modulo prova a usare dipendenze locali se presenti:

- **Pillow** per leggere formati comuni come JPG/PNG;
- **OpenCV** per eventuale preprocessing quando disponibile;
- **pytesseract** e il binario `tesseract` come aiuto opzionale alla lettura testuale.

Non vengono usate API esterne a pagamento. Se le dipendenze non sono installate o la foto non è abbastanza chiara, il bot fallisce in modo controllato, salva l'immagine, spiega il problema e lascia disponibile l'import manuale.

### Debug ultimo import

Il comando amministrativo `/debug_calendario_moglie` mostra l'ultimo riepilogo import: percorso immagine, stato OCR, date candidate/summary e avvisi. Per salvare le candidate dell’ultimo OCR ad alta confidenza usa `/conferma_calendario_moglie`.

---

# Bot Telegram privato con memoria SQLite

Questa versione aggiunge un **chatbot Telegram privato** che permette a Gianmarco di scrivere note durante la settimana e poi generare direttamente il PDF dell'orario settimanale.

La CLI e i launcher storici restano disponibili; il bot usa lo stesso motore di generazione PDF già presente nel progetto.

## Cosa fa il bot

- salva messaggi liberi come note settimanali persistenti in SQLite;
- protegge l'accesso con `ALLOWED_TELEGRAM_USER_ID`;
- genera l'orario con le regole fisse di CarpEvolution Store e Tenuta del Germano;
- valida l'orario e riepiloga eventuali avvisi/conflitti;
- crea un PDF A4 verticale pronto da inoltrare su Telegram o WhatsApp;
- invia il PDF direttamente nella chat Telegram;
- accetta note vocali Telegram, file audio e documenti con MIME audio, li trascrive con OpenAI speech-to-text e passa il testo allo stesso AI Agent dei messaggi scritti;
- mantiene una **memoria operativa persistente** per ferie, assenze future, appuntamenti ricorrenti e vincoli non legati solo alla settimana corrente;
- mantiene la tabella `wife_calendar` compilabile manualmente: solo il codice `M` blocca Giammarco dall’apertura lago alle 07:30.

## Comandi Telegram

- `/start` — spiega cosa fa il bot.
- `/aiuto` — mostra esempi e comandi.
- `/nota Giovedì Gianmarco in negozio tutto il giorno per fatture` — salva una nota.
- `/lista` — mostra ID, settimana interpretata, data interpretata e testo delle note attive della settimana corrente/prossima.
- `/lista questa settimana` — mostra le note della settimana corrente lunedì-domenica.
- `/lista settimana prossima` o `/lista prossima settimana` — mostra le note della prossima settimana lunedì-domenica.
- `/lista fra 2 settimane` o `/lista fra due settimane` — mostra le note della settimana dopo la prossima.
- `/lista dal 17 al 23 giugno` — mostra le note di un intervallo specifico.
- `/cancella 12` — cancella la nota attiva con ID 12 e conferma l’operazione; se l’ID non esiste lo dice chiaramente.
- `/cancella_tutte confermo` — archivia tutte le note attive della prossima settimana.
- `/cancella_tutte settimana prossima confermo` — archivia tutte le note attive della prossima settimana.
- `/cancella_tutte questa settimana confermo` — archivia tutte le note attive della settimana corrente.
- `/cancella_tutte fra 2 settimane confermo` — archivia tutte le note attive della settimana dopo la prossima.
- `/memoria` — mostra l’aiuto della memoria operativa persistente.
- `/memoria_aggiungi Lorenzo in ferie dal 10 al 15 agosto` — salva ferie/assenze future e le applica automaticamente alle settimane sovrapposte.
- `/memoria_aggiungi Angelo assente il 27 giugno` — salva un’assenza di una giornata.
- `/memoria_aggiungi Angelo non c’è il 3 settembre mattina` — salva un’assenza parziale di mattina.
- `/memoria_aggiungi Gianmarco attività aziendale esterna il 12 luglio dalle 10 alle 12` — salva lavoro esterno che non vale come copertura fissa.
- `/memoria_aggiungi Gianmarco dal commercialista ogni giovedì mattina` — salva una ricorrenza settimanale semplice.
- `/memoria_lista` — mostra tutte le memorie operative attive.
- `/memoria_lista luglio` — filtra le memorie attive rilevanti per luglio, quando il mese è riconoscibile.
- `/memoria_cancella ID` — archivia una singola memoria operativa.
- `/memoria_reset` — chiede conferma prima di archiviare tutte le memorie operative.
- `/memoria_reset confermo` — archivia tutte le memorie operative attive.
- `/moglie_set YYYY-MM-DD M` — salva il codice `M` per quella data; blocca Giammarco dall’apertura lago alle 07:30.
- `/moglie_set YYYY-MM-DD P` — salva il codice `P`; non ha effetto bloccante.
- `/moglie_importa_m 2026-09-03,2026-09-10` — importa in blocco più date con codice `M`.
- `/moglie_importa_m` seguito da una data per riga — importa lo stesso elenco in formato multilinea.
- `/importa_calendario_moglie` — avvia la ricezione della foto della tabella orari moglie e salva l’immagine in `data/imports/`.
- foto con caption `/importa_calendario_moglie` — salva direttamente l’immagine senza passaggio intermedio.
- `/moglie_lista` — mostra i codici calendario moglie salvati.
- `/moglie_lista M` — mostra solo le date con codice `M`.
- `/moglie_cancella YYYY-MM-DD` — elimina il codice salvato per quella data.
- `/moglie_reset` — chiede conferma prima di svuotare il calendario moglie.
- `/moglie_reset confermo` — svuota tutte le righe del calendario moglie.
- `/genera` — genera il PDF della settimana prossima.
- `/genera dal 17 al 23 giugno` — genera il PDF della settimana indicata. Il bot invia anche un riepilogo breve con intervallo settimana, numero di note usate, numero di memorie operative applicate, numero di avvisi/conflitti e nome del file PDF allegato.
- `/reset_settimana dal 17 al 23 giugno confermo` — archivia le note attive della settimana indicata.
- `/trascrivi_ultimo` — mostra l’ultima trascrizione vocale salvata per l’utente autorizzato, utile per debug.

Puoi anche scrivere messaggi normali o inviare un vocale, ad esempio:

```text
Giovedì Gianmarco deve stare in negozio tutto il giorno per fatture.
Sabato Lorenzo deve uscire alle 15.
Domenica al lago ci sono molte prenotazioni.
Martedì prossimo Angelo non c'è la mattina.
Venerdì io sono dal commercialista alle 10.
```

Se il messaggio inizia con `Genera orario`, il bot genera il PDF invece di salvarlo come nota. Se il messaggio inizia con `ricordati che ...`, `memorizza che ...` o `salva memoria ...`, viene salvato nella memoria operativa persistente invece che tra le note settimanali.

Quando una nota viene salvata, il bot risponde con ID nota, settimana interpretata, data se riconosciuta, persona, luogo, tipo vincolo e una sintesi dell’interpretazione automatica. Se una frase non è supportata, la nota resta comunque salvata e viene riportata nel PDF come avviso/nota non interpretata.

Esempio di risposta:

```text
Nota salvata con ID 12.
Settimana: 2026-06-15 - 2026-06-21.
Data interpretata: 2026-06-18.
Persona: Giammarco Mengozzi.
Luogo: CarpEvolution Store.
Tipo vincolo: copertura_negozio.
Interpretazione: Giammarco Mengozzi forzato su negozio Giovedì 09:00-12:30. Giammarco Mengozzi forzato su negozio Giovedì 15:30-19:30.
```

## Memoria operativa persistente

La memoria operativa serve per salvare una volta sola vincoli futuri o ricorrenti che non appartengono soltanto alla prossima settimana. Esempi tipici:

- `Lorenzo in ferie dal 10 al 15 agosto`;
- `Angelo assente il 27 giugno`;
- `Angelo non c’è il 3 settembre mattina`;
- `Gianmarco attività aziendale esterna il 12 luglio dalle 10 alle 12`;
- `Gianmarco dal commercialista ogni giovedì mattina`.

Differenza rispetto alle note settimanali:

- le **note settimanali** (`/nota`) sono pensate per una settimana specifica o per la prossima settimana e vengono usate solo quando quella settimana viene generata;
- la **memoria operativa** (`/memoria_aggiungi`) resta attiva nel database e viene caricata automaticamente ogni volta che `/genera` riguarda una settimana che si sovrappone alle sue date o alla sua ricorrenza.

Quando viene generato l’orario, il bot:

1. carica le note settimanali della settimana richiesta;
2. carica le memorie operative attive sovrapposte alla settimana;
3. trasforma le memorie interpretate negli stessi vincoli usati dal motore settimanale;
4. aggiunge nel PDF note del tipo `Memoria: Lorenzo in ferie`, `Memoria: Angelo assente mattina` o `Memoria: Gianmarco commercialista 10:00-12:00`;
5. conserva le memorie non interpretate come promemoria/avvisi, senza bloccare la generazione del PDF.

Il parser della memoria è deterministico e non usa API AI esterne. Se l’anno non viene indicato, usa la prossima occorrenza della data: ad esempio, con data corrente 2026-06-10, `27 giugno` diventa `2026-06-27`; se una data è già passata nell’anno corrente, viene spostata all’anno successivo.

Limite attuale delle ricorrenze: è supportata solo la ricorrenza settimanale per giorno della settimana e periodo (`mattina`, `pomeriggio` o giornata intera). Il formato interno è semplice, per esempio `WEEKLY:THURSDAY:MORNING`; non è ancora implementato un parser iCal complesso.

## Creare il bot con BotFather

1. Apri Telegram e cerca **@BotFather**.
2. Scrivi `/newbot`.
3. Scegli un nome leggibile, per esempio `Orari CarpeEvolution`.
4. Scegli uno username che finisca con `bot`, per esempio `orari_carpeevolution_bot`.
5. BotFather ti darà un token simile a:

```text
123456789:AAExampleToken...
```

Questo valore va inserito in `TELEGRAM_BOT_TOKEN`.

## Trovare ALLOWED_TELEGRAM_USER_ID

Il bot è privato: salva e genera orari solo per l'ID Telegram configurato.

Metodo semplice:

1. Apri Telegram.
2. Cerca **@userinfobot** oppure **@RawDataBot**.
3. Avvialo e leggi il tuo `id` numerico.
4. Copia quel numero in `ALLOWED_TELEGRAM_USER_ID`.

Esempio:

```env
ALLOWED_TELEGRAM_USER_ID=123456789
```

Se un altro utente scrive al bot, il bot risponde cortesemente e non salva nulla.

## Configurare `.env`

Copia il file di esempio:

```bash
cp .env.example .env
```

Poi modifica `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCDEF_TOKEN_DEL_BOT
ALLOWED_TELEGRAM_USER_ID=123456789
DATABASE_PATH=data/orari_bot.sqlite3
OUTPUT_DIR=output
```

`DATABASE_PATH` indica il file SQLite persistente. Se cancelli quel file perdi note, cronologia generazioni e futuro calendario moglie.

## Avvio locale su macOS

Dalla cartella del progetto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
# In alternativa: python -m pip install -r requirements.txt
cp .env.example .env
```

Dopo aver compilato `.env`, avvia il bot:

```bash
python main.py
```

Oppure, dopo l'installazione editable:

```bash
orari-telegram-bot
```

Il bot usa **long polling** (`getUpdates`), quindi non serve configurare webhook, HTTPS o dominio. Telegram non può usare contemporaneamente long polling e webhook per lo stesso bot: per questa prima versione resta attivo solo il polling.

## Deploy futuro su piccolo server cloud

Per un server Linux economico:

1. installa Python 3.10+;
2. clona il repository;
3. crea `.env` con token, user ID e percorso database;
4. installa il progetto con `python -m pip install -e .`;
5. avvia `orari-telegram-bot` dentro `tmux`, `screen` o come servizio `systemd`.

Esempio servizio `systemd` indicativo:

```ini
[Unit]
Description=Orari Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/Orari-
ExecStart=/opt/Orari-/.venv/bin/orari-telegram-bot
Restart=always
EnvironmentFile=/opt/Orari-/.env

[Install]
WantedBy=multi-user.target
```

## Struttura tecnica aggiunta

- `main.py` — avvio locale del bot.
- `.env.example` — esempio variabili d'ambiente.
- `requirements.txt` — dipendenze minime del bot se non usi `pip install -e .`.
- `src/orari_agent/config.py` — lettura configurazione.
- `src/orari_agent/bot/` — ApplicationBuilder, comandi, sicurezza e servizio di generazione.
- `src/orari_agent/storage/` — SQLite, repository note, memoria operativa, cronologia PDF, calendario moglie e parsing settimane.
- `src/orari_agent/scheduling/memory_adapter.py` — trasforma la memoria operativa in vincoli settimanali applicabili dal generatore.
- `src/orari_agent/bot_runner.py` — entry point installabile `orari-telegram-bot`.

## Database SQLite

All'avvio il bot crea automaticamente le tabelle:

- `notes` — note attive/usate/cancellate con testo originale e metadati interpretati;
- `generated_schedules` — cronologia PDF generati, riepilogo e avvisi;
- `operational_memory` — ferie, assenze future, impegni esterni e ricorrenze operative persistenti.
- `wife_calendar` — tabella del calendario moglie compilabile da Telegram; solo il codice `M` ha effetto operativo, mentre `P`, `I`, `F` e colori/altre marcature sono ignorati.
- `wife_calendar_imports` — registro degli import da immagine, con percorso file salvato, stato, riepilogo e avvisi per futuri miglioramenti OCR.


## Interpretazione settimane nel bot

Il parser delle settimane è deterministico e usa regole italiane:

- `questa settimana` = settimana corrente da lunedì a domenica;
- `settimana prossima` e `prossima settimana` = prossima settimana da lunedì a domenica;
- `fra 2 settimane`, `tra 2 settimane`, `fra due settimane`, `tra due settimane` = settimana dopo la prossima;
- `dal 17 al 23 giugno` = intervallo esatto indicato;
- `settimana del 17 giugno` = settimana lunedì-domenica che contiene il 17 giugno.

Senza indicazione di settimana, i comandi operativi usano la prossima settimana.

## Calendario moglie di Giammarco

La regola operativa è volutamente minima: conta solo il codice `M`. I codici si possono salvare uno alla volta con `/moglie_set` oppure in blocco con `/moglie_importa_m`.

Esempio import in una riga:

```text
/moglie_importa_m 2026-09-03,2026-09-10,2026-09-17
```

Esempio import con una data per riga:

```text
/moglie_importa_m
2026-09-03
2026-09-10
2026-09-17
```

Il bot accetta solo date ISO `YYYY-MM-DD`, ignora le date non valide e le riporta nella risposta. Se una data era già presente, viene salvato un nuovo valore aggiornato senza duplicare l’effetto operativo.

Per caricare più rapidamente una tabella da immagine puoi usare:

```text
/importa_calendario_moglie
```

Il bot risponde `Mandami ora la foto della tabella orari di tua moglie.`; quando invii la foto, la salva in `data/imports/` e registra l’operazione nel database. Puoi anche inviare direttamente la foto con caption `/importa_calendario_moglie`.

Limite attuale: in questa versione l’OCR automatico della griglia non è abilitato perché potrebbe leggere male lettere e giorni. Dopo aver salvato la foto, il bot chiede di mandare l’elenco delle sole date `M` con `/moglie_importa_m`. L’architettura mantiene immagine, stato e avvisi per aggiungere in futuro un OCR locale e sicuro senza cambiare la regola operativa.

Regola operativa attiva:

- se in una data il codice è `M`, Giammarco non può aprire il lago alle `07:30`;
- tutti gli altri codici, per esempio `P`, `I`, `F`, e i colori rosso/giallo/rosa non bloccano nulla.

Durante `/genera`, se il motore trova Giammarco assegnato all’apertura lago delle 07:30 in una data con codice `M`, mostra un avviso chiaro:

```text
Conflitto: Giammarco non può aprire il lago il YYYY-MM-DD perché nel calendario moglie c’è M.
```

Il generatore prova prima a evitare quell’assegnazione. Se non riesce a coprire tutto, genera comunque il PDF e lascia l’avviso/conflitto nel riepilogo.

## Come testare senza Telegram

Puoi verificare che il motore PDF continui a funzionare:

```bash
PYTHONPATH=src python -m orari_agent --planning-file input/weekly_plan.yaml --pdf --output output
```

Puoi verificare parsing e SQLite con un piccolo script temporaneo:

```bash
PYTHONPATH=src python - <<'PY'
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.week_parser import parse_note_metadata

conn = connect('data/test_orari_bot.sqlite3')
repo = NotesRepository(conn)
note = repo.add('Giovedì Gianmarco in negozio tutto il giorno per fatture', parse_note_metadata('Giovedì Gianmarco in negozio tutto il giorno per fatture'))
print(note)
PY
```

Per il test completo con Telegram:

1. avvia `python main.py`;
2. apri la chat con il bot;
3. scrivi `/start`;
3-bis. prova `/genera` oppure `/genera dal 17 al 23 giugno` e verifica che arrivino il PDF e un riepilogo simile a `Orario generato per 2026-06-15 / 2026-06-21. Note usate: 3. Memorie operative: 2. Avvisi/conflitti: 1. PDF allegato: Orario_CarpeEvolution_Tenuta_2026-06-15_2026-06-21.pdf.`;
4. prova `/nota Sabato Lorenzo deve uscire alle 15` e verifica che il bot risponda con l’ID della nota;
5. prova `/lista`, `/lista questa settimana`, `/lista settimana prossima`, `/lista fra 2 settimane` e `/lista dal 17 al 23 giugno`; ogni riga deve mostrare ID, settimana, data interpretata se presente e testo;
6. prova `/cancella ID` usando un ID reale, poi riprova con lo stesso ID per verificare il messaggio “non trovata”;
7. crea due note di prova e usa `/cancella_tutte confermo` oppure `/cancella_tutte questa settimana confermo`; senza `confermo` il bot deve rispondere `Per sicurezza, ripeti il comando aggiungendo confermo.`;
8. prova `/memoria_aggiungi Lorenzo in ferie dal 10 al 15 agosto`, poi `/memoria_lista`, poi `/memoria_cancella ID`;
9. prova `/memoria_reset`: senza conferma deve chiedere `/memoria_reset confermo`;
10. prova `/memoria_reset confermo` e verifica che `/memoria_lista` non mostri più righe;
11. prova `/moglie_set 2026-06-14 M`, poi `/moglie_lista`, poi `/moglie_cancella 2026-06-14`;
12. prova `/moglie_importa_m 2026-09-03,2026-09-10`, poi `/moglie_lista M`;
13. prova `/moglie_reset`: senza conferma deve rispondere `Per sicurezza, ripeti con: /moglie_reset confermo`;
14. prova `/moglie_reset confermo` e verifica che `/moglie_lista` non mostri più righe;
15. prova `/importa_calendario_moglie`, invia una foto e verifica che il bot la salvi in `data/imports/` chiedendo poi l’elenco date con `/moglie_importa_m`;
16. per verificare il conflitto calendario moglie, salva una data con `M` nella settimana da generare e usa `/genera`; se Giammarco fosse assegnato all’apertura lago delle 07:30, il riepilogo deve mostrare il conflitto;
17. prova anche `/moglie_set 2026-06-14 P` e `/genera`: `P` deve essere ignorato come vincolo.

## Test automatici principali

Per eseguire tutta la suite:

```bash
pytest -q
```

I test coprono anche le frasi operative più importanti:

- `Giovedì Gianmarco in negozio tutto il giorno per fatture` forza la copertura negozio mattina e pomeriggio.
- `Martedì Lorenzo deve aprire il lago` forza Lorenzo sull’apertura lago del martedì.
- `Sabato Lorenzo deve uscire alle 15` blocca Lorenzo dopo le 15:00 e produce gli avvisi ore se necessari.
- `Giovedì io sono dal commercialista dalle 10 alle 12` crea lavoro esterno di Giammarco e impedisce coperture sovrapposte.
- `Domenica al lago ci sono molte prenotazioni` aggiunge nota di carico alto e prova una copertura extra.
- Il codice calendario moglie `M` blocca Gianmarco dall’apertura lago delle 07:30.
- Le note sconosciute sono preservate come avvisi del PDF.
- La memoria operativa salva assenze singole, ferie, assenze parziali, lavoro esterno, ricorrenze settimanali e preserva testo non interpretato senza interrompere la generazione.
- La risposta `/nota` include la sintesi dell’interpretazione automatica.

---

## Produzione su VPS Linux

Target consigliato: **Hetzner Cloud CX22** o VPS equivalente con Ubuntu/Debian, Python 3.10+ e disco persistente. Il bot usa long polling Telegram: non servono dominio, HTTPS o webhook.

### Verifica dipendenze

Le dipendenze runtime sono dichiarate in `requirements.txt` e nel `pyproject.toml`. Per l'import Excel è richiesta `openpyxl`:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Se l'ambiente non ha accesso a PyPI, installare prima i pacchetti di progetto in una rete abilitata oppure preparare una wheelhouse interna.

### Installazione iniziale VPS

Esempio Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
sudo useradd --system --create-home --shell /usr/sbin/nologin orari
sudo mkdir -p /opt/Orari-
sudo chown orari:orari /opt/Orari-
sudo -u orari git clone <URL_REPOSITORY> /opt/Orari-
cd /opt/Orari-
sudo -u orari python3 -m venv .venv
sudo -u orari .venv/bin/python -m pip install --upgrade pip
sudo -u orari .venv/bin/python -m pip install -r requirements.txt
sudo -u orari cp .env.example .env
sudo -u orari nano .env
```

Configurazione minima `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCDEF_TOKEN_DEL_BOT
ALLOWED_TELEGRAM_USER_ID=123456789
DATABASE_PATH=data/orari_bot.sqlite3
OUTPUT_DIR=output
```

Tutti i dati persistenti operativi stanno sotto `data/`: database SQLite, file importati e backup. La cartella `output/` contiene i PDF generati.

### Avvio manuale

```bash
cd /opt/Orari-
./start_bot.sh
```

### Servizio systemd 24/7

Il file `orari-bot.service` è un esempio pronto da copiare:

```bash
sudo cp /opt/Orari-/orari-bot.service /etc/systemd/system/orari-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now orari-bot.service
sudo systemctl status orari-bot.service
journalctl -u orari-bot.service -f
```

Dopo un riavvio del VPS, `systemd` riavvia automaticamente il bot.

## Persistenza dati

La configurazione standard usa:

- `data/orari_bot.sqlite3` per note, memoria operativa, cronologia PDF e calendario moglie;
- `data/imports/` per file ricevuti da Telegram, inclusi Excel e immagini calendario moglie;
- `data/audio/` per audio scaricati temporaneamente dalle note vocali e dagli allegati audio;
- `data/backups/` per gli ZIP creati da `/backup`.

Il database SQLite sopravvive al riavvio del processo e del VPS finché non viene cancellato il file in `data/`. Sopravvivono quindi anche:

- note settimanali;
- memoria operativa;
- import calendario moglie;
- trascrizioni vocali nella tabella `voice_transcripts`;
- cronologia essenziale delle generazioni.

## Import Excel calendario moglie

Comando principale:

```text
/carica_calendario_moglie
```

Workflow:

1. scrivi `/carica_calendario_moglie`;
2. il bot chiede il file Excel;
3. carica un file `.xlsx`;
4. il bot legge il file con `openpyxl`;
5. salva in `wife_calendar` solo le date collegate al codice esatto `M`;
6. risponde con numero di date importate, inserimenti e aggiornamenti.

Regola business in produzione: **solo `M` conta**. `P`, `I`, `F`, colori, celle vuote e formattazione non creano vincoli. Se il file attuale termina a giugno 2026 e non viene caricato un calendario più recente, luglio e agosto 2026 sono considerati liberi: le date mancanti non generano avvisi e Gianmarco può aprire il lago normalmente.

Comandi di controllo:

```text
/calendario_moglie_info
/calendario_moglie_reset confermo
```

`/calendario_moglie_info` mostra prima data caricata, ultima data caricata, numero di date `M` e timestamp dell'ultimo import. `/calendario_moglie_reset confermo` svuota il calendario moglie importato.

## Backup e restore preparation

Backup immediato da Telegram:

```text
/backup
```

Il bot crea `backup_YYYYMMDD_HHMMSS.zip` in `data/backups/` e lo invia in chat. Lo ZIP contiene:

- database SQLite;
- file importati in `data/imports/`, inclusi Excel calendario moglie;
- `metadata.json` con percorso database, timestamp e conteggi principali.

Info backup e dati persistenti:

```text
/backup_info
```

Mostra percorso database, numero note, numero memorie operative, numero righe calendario moglie e ultimo backup disponibile. Il restore automatico completo non è ancora implementato: per ora lo ZIP prepara il ripristino manuale dei file persistenti.

## Workflow operativo consigliato in produzione

1. Caricare il calendario moglie Excel con `/carica_calendario_moglie`.
2. Aggiungere le note settimanali con `/nota ...` o messaggi liberi.
3. Aggiungere memoria operativa persistente con `/memoria_aggiungi ...`.
4. Generare l'orario con `/genera`.
5. Condividere il PDF ricevuto dal bot.
6. Creare un backup con `/backup` dopo import o modifiche importanti.

## Modalità Telegram: comandi deterministici e AI Agent

Il bot Telegram mantiene due modalità complementari:

- **Modalità comando**: i comandi espliciti (`/nota`, `/lista`, `/genera`, `/memoria_aggiungi`, `/memoria_lista`, `/carica_calendario_moglie`, `/calendario_moglie_info`, `/backup`, `/backup_info` e gli altri comandi amministrativi) continuano a usare direttamente i servizi deterministici Python. Questa modalità non richiede OpenAI e resta disponibile anche se la chiave AI manca.
- **Modalità AI**: i normali messaggi testuali non preceduti da `/` passano dal layer AI. Anche le note vocali, dopo la trascrizione OpenAI, entrano nello stesso identico flusso tramite `AiAgent.handle_message()`. L'AI interpreta l'italiano naturale, decide un'intenzione strutturata e richiama i tool interni già esistenti senza sostituire il motore di scheduling.

Flusso della modalità AI:

```text
Messaggio Telegram libero o trascrizione vocale
→ layer AI
→ OpenAI Responses API
→ JSON strutturato con tool call
→ repository/servizi Python esistenti
→ risposta Telegram naturale ed eventuale PDF
```

Se `OPENAI_API_KEY` non è configurata, il bot parte comunque e i comandi continuano a funzionare. In quel caso i messaggi liberi ricevono:

```text
Modalità AI non configurata: manca OPENAI_API_KEY.
```

### Configurare OPENAI_API_KEY

1. Crea una chiave API dal pannello OpenAI: <https://platform.openai.com/api-keys>.
2. Apri o crea il file `.env` nella directory di deploy.
3. Aggiungi la variabile:

```env
OPENAI_API_KEY=sk-...
```

Le altre variabili Telegram restano necessarie:

```env
TELEGRAM_BOT_TOKEN=...
ALLOWED_TELEGRAM_USER_ID=...
DATABASE_PATH=data/orari_bot.sqlite3
OUTPUT_DIR=output
OPENAI_API_KEY=sk-...
VOICE_DEBUG=false
```

### Messaggi vocali e file audio

Il bot supporta lo stesso flusso AI anche quando il vincolo arriva come audio:

```text
Nota vocale / file audio Telegram
→ download temporaneo in data/audio/
→ OpenAI audio transcription API tramite SDK openai
→ trascrizione testuale
→ stesso AiAgent.handle_message() usato dai messaggi scritti
→ tool interni e salvataggio vincoli identici alla modalità testo
→ risposta Telegram con trascrizione e interpretazione
```

Formati supportati:

- `ogg` per le note vocali Telegram;
- `mp3`;
- `m4a`;
- `wav`.

Sono accettati:

- voice note Telegram;
- allegati audio Telegram;
- documenti Telegram con MIME type audio.

La risposta mostra:

```text
🎤 Trascrizione:
...

🤖 Interpretazione:
...
```

Se la trascrizione supera 1000 caratteri, in chat viene mostrata solo l’anteprima; il testo completo resta salvato nella tabella `voice_transcripts` ed è recuperabile con `/trascrivi_ultimo`. I file audio vengono salvati temporaneamente in `data/audio/` e cancellati dopo una trascrizione riuscita. Con `VOICE_DEBUG=true`, invece, il bot conserva sia il file audio sia un file `.txt` accanto all’audio con la trascrizione completa.

Troubleshooting vocale:

- `Trascrizione non disponibile: controlla OPENAI_API_KEY.` — manca la chiave OpenAI nel `.env` o nel servizio systemd.
- `Non sono riuscito a trascrivere il messaggio vocale.` — OpenAI o il download Telegram hanno restituito errore, oppure l’audio non contiene testo utilizzabile.
- `Messaggio vocale troppo grande.` — il file supera il limite della pipeline di trascrizione.
- `Formato audio non supportato. Usa ogg, mp3, m4a o wav.` — inviare nuovamente il file in uno dei formati supportati.

### Riavvio del servizio in produzione

Dopo aver aggiornato `.env` sul VPS Hetzner:

```bash
sudo systemctl restart orari-bot
```

Per controllare lo stato:

```bash
sudo systemctl status orari-bot
```

### Cosa sa l'AI del contesto operativo

L'assistente AI conosce le regole principali:

- Gianmarco Mengozzi è titolare/manager/jolly e può coprire negozio o lago; se serve copertura extra, preferisce il lago salvo assegnazioni esplicite.
- Angelo Antonelli copre principalmente CarpEvolution Store.
- Lorenzo Sansavini copre principalmente Tenuta del Germano/lago, con 40 ore, 5 giorni, normalmente mercoledì-domenica; lunedì chiuso e martedì riposo preferito.
- Tenuta del Germano è aperta martedì-domenica 07:30-18:30 e chiusa lunedì.
- CarpEvolution Store è aperto martedì-sabato 09:00-12:30 e 15:30-19:30, chiuso domenica e lunedì.
- Nel calendario moglie conta solo il codice `M`: se una data ha `M`, Gianmarco non può aprire il lago alle 07:30. Dati luglio/agosto mancanti non creano vincoli.

### Tool AI disponibili

Il layer AI può richiamare solo funzioni interne controllate:

- `add_weekly_note(text, week_request)`
- `list_weekly_notes(week_request)`
- `delete_weekly_note(note_id)`
- `delete_weekly_notes_for_week(week_request)`
- `add_operational_memory(text)`
- `list_operational_memory()`
- `generate_schedule(week_request)`
- `get_wife_calendar_info()`
- `list_wife_calendar_m_dates()`
- `backup_info()`
- `create_backup()`

Le azioni distruttive, come cancellare tutte le note di una settimana o futuri reset di memoria/calendario, non vengono eseguite al primo messaggio: il bot chiede conferma con `Confermi? Rispondi ‘confermo’.` e salva l'azione in attesa nel database.

### Esempi di conversazioni AI

**Salvataggio nota settimanale**

```text
Gianmarco: Giovedì sono dal commercialista dalle 10 alle 12.
Bot: Perfetto, ho interpretato un impegno esterno di Gianmarco giovedì 10:00-12:00.
Nota salvata con ID ...
La userò nella generazione dell'orario.
```

**Memoria operativa persistente**

```text
Gianmarco: Ricordati che Lorenzo è in ferie dal 10 al 15 agosto.
Bot: Ho salvato questa memoria operativa per Lorenzo.
Memoria operativa salvata con ID ...
La applicherò automaticamente quando genera orari compatibili.
```

**Generazione PDF**

```text
Gianmarco: Fammi l'orario della prossima settimana.
Bot: Genero l'orario richiesto usando note, memorie e calendario moglie.
Bot: [allega PDF]
Bot/PDF: riepilogo note usate, memorie operative e avvisi/conflitti.
```

**Azione distruttiva con conferma**

```text
Gianmarco: Cancella tutte le note della settimana prossima.
Bot: Cancellerò le note della settimana prossima. Confermi? Rispondi ‘confermo’.
Gianmarco: confermo
Bot: Azione confermata ed eseguita. Ho archiviato ... note attive.
```

## Agente AI operativo Telegram

Il bot Telegram ora è pensato come un **agente AI di pianificazione**, non solo come un elenco di comandi. L'obiettivo è permettere a Gianmarco di scrivere o dettare frasi naturali e trasformarle in vincoli strutturati, memorie operative, generazioni di orario e spiegazioni sull'ultimo PDF prodotto.

### Cosa capisce

L'agente conosce alias e contesto operativo:

- `negozio`, `CarpEvolution Store`, `CarpeEvolution Store`, `Carp Evolution` indicano il negozio di pesca;
- `lago`, `tenuta`, `Tenuta del Germano` indicano la Tenuta del Germano;
- `io`, `me`, `sono`, `devo` indicano Gianmarco/Giammarco Mengozzi;
- Angelo Antonelli è principalmente negozio;
- Lorenzo Sansavini è principalmente lago.

Esempi di frasi gestite:

```text
Giovedì sono dal commercialista dalle 10 alle 12.
Venerdì Angelo dopo il negozio viene al lago fino alle 23.
Lorenzo martedì lascialo a casa.
Da luglio il venerdì sera Angelo può sempre aiutare al lago.
Genera settimana prossima.
Perché Lorenzo chiude domenica?
Che note hai usato?
```

### Workflow dell'agente

Il flusso AI è diviso in stadi tracciabili:

1. **Context loader**: carica note settimanali, memorie operative, calendario moglie e ultimo orario.
2. **Intent interpreter**: classifica l'intento e produce un oggetto strutturato con confidenza `high`, `medium` o `low`.
3. **Tool executor**: esegue solo strumenti sicuri e validati, ad esempio salvataggio nota, lista memorie, generazione orario, backup o spiegazione ultimo orario.
4. **Scheduling planner**: continua a usare il generatore deterministico esistente, combinando regole fisse, note, memorie e calendario moglie.
5. **Schedule validator**: separa conflitti critici e alert informativi.
6. **Repair/explanation layer**: conserva lo snapshot dell'ultimo orario e risponde a domande successive.
7. **Audit trail**: salva l'interpretazione AI nella tabella `ai_events` per debug.

### Confidenza e conferme

L'agente non deve fare assunzioni rischiose:

- alta confidenza + azione non distruttiva: salva automaticamente;
- media confidenza: chiede conferma;
- bassa confidenza o pronomi ambigui: chiede chiarimento;
- cancellazioni, reset o sovrascritture richiedono sempre conferma.

Esempio:

```text
Utente: Venerdì lui va al lago.
Bot: Chi intendi? Angelo, Lorenzo o Gianmarco?
```

### Strumenti strutturati disponibili

Lo strato AI può chiamare strumenti validati, tra cui:

- `add_weekly_note` / `list_weekly_notes` / `delete_weekly_note`;
- `add_operational_memory` / `list_operational_memories`;
- `generate_schedule`;
- `validate_schedule` e `repair_schedule` come passaggi controllati della generazione;
- `explain_last_schedule` / `get_last_schedule`;
- `get_wife_calendar_info` / `list_wife_calendar_m_dates`;
- `create_backup` / `backup_info`.

L'LLM non genera l'orario finale come prosa libera: interpreta l'intento e usa tool strutturati, mentre la pianificazione resta affidata alla logica deterministica del progetto.

### Validazione prima del PDF

Ogni generazione salva uno snapshot dell'orario con:

- note usate;
- memorie operative usate;
- riepilogo;
- PDF generato;
- conflitti critici;
- alert informativi.

Sono conflitti critici le coperture mancanti, le sovrapposizioni impossibili, le aperture del lago incompatibili con codice moglie `M`, la copertura serale stagionale mancante o l'assegnazione del negozio scoperta.

Sono alert informativi gli scostamenti di Lorenzo dal target 40 ore, i turni lunghi e gli avvisi di evento serale. Lorenzo può superare o non raggiungere le 40 ore: il bot lo segnala, ma non lo blocca come conflitto critico.

### Comandi Telegram utili

Oltre ai comandi storici, sono disponibili o migliorati:

```text
/aiuto          mostra cosa capisce l'agente
/stato          mostra settimana attiva, note, memorie e ultimo orario
/note           lista le note settimanali
/memorie        lista le memorie operative persistenti
/ultimo_orario  riepiloga l'ultimo orario generato
/spiega         spiega l'ultimo orario o una domanda specifica
/debug_ai       mostra l'ultima interpretazione AI salvata
/backup         crea un backup
/backup_info    mostra lo stato dei backup
```

### Esempi conversazionali

```text
Utente: Giovedì Lorenzo va dal commercialista dalle 10 alle 12.
Bot: Ok, salvo vincolo settimanale: Lorenzo Sansavini giovedì 10:00-12:00, lavoro esterno/commercialista.
```

```text
Utente: Venerdì Angelo dopo il negozio viene al lago fino alle 23.
Bot: Ok, salvo vincolo settimanale: Angelo Antonelli copre il negozio 09:00-12:30 / 15:30-19:30 e poi supporta il lago 19:30-23:00.
```

```text
Utente: Genera settimana prossima.
Bot: Genero l'orario della settimana richiesta. Uso note, memorie e calendario moglie salvati. Dopo la generazione invio il PDF con caption breve e il riepilogo in messaggi separati.
```

```text
Utente: Che note hai usato?
Bot: Note usate per l'ultimo orario:
• Venerdì Angelo dopo il negozio al lago fino alle 23
```

### Configurazione OpenAI

La configurazione AI resta controllata da variabili d'ambiente:

```text
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_REASONING_EFFORT=
OPENAI_AGENT_MODE=responses
```

Se `OPENAI_API_KEY` manca, i comandi deterministici continuano a funzionare e il bot risponde che la modalità AI non è configurata.
