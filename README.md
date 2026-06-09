# Orari Agent

Agente di pianificazione settimanale per:

- **CarpeEvolution Store**
- **Tenuta del Germano**

L'agente conserva le regole fisse, interpreta semplici istruzioni settimanali in linguaggio naturale, genera una tabella in italiano e segnala conflitti, mancate coperture e violazioni delle regole di Lorenzo.

## Priorità operative predefinite

1. **Angelo Antonelli** copre il negozio di default.
2. **Lorenzo Sansavini** copre il lago di default, con 5 giorni e 40 ore settimanali.
3. **Giammarco Mengozzi** è general manager / CEO dell’operazione: lavora sempre per l’azienda, ma viene contato come copertura fissa solo quando è assegnato a lago o negozio. Se serve copertura e non ci sono istruzioni esplicite, la priorità è il lago.

Il motore prova a mantenere sempre almeno una persona al lago e una persona in negozio durante gli orari di apertura. Se una combinazione di assenze rende impossibile coprire tutto con le sole tre persone disponibili e con i vincoli di Lorenzo, l'orario viene comunque generato e il validatore evidenzia l'intervallo scoperto.

## Istruzioni supportate

Il parser leggero riconosce frasi italiane o inglesi con giorno, persona e intenzione. Esempi:

- `Giovedì Giammarco deve stare in negozio.`
- `Giammarco deve stare due giorni in negozio questa settimana.`
- `Martedì Lorenzo deve aprire il lago.`
- `Domenica Lorenzo è assente.`
- `Sabato Angelo è in ferie.`
- `Venerdì Giammarco deve stare al lago.`
- `Giovedì Giammarco è dal commercialista.`
- `Venerdì mattina Giammarco è in banca.`
- `Domenica il lago ha molte prenotazioni.`

Le istruzioni possono essere passate in un unico testo, separate da punto o a capo.

## Avvio rapido

```bash
PYTHONPATH=src python -m orari_agent "Giovedì Giammarco deve stare in negozio. Martedì Lorenzo deve aprire il lago. Domenica Lorenzo è assente. Sabato Angelo è in ferie. Venerdì Giammarco deve stare al lago."
```

In alternativa, dopo installazione locale:

```bash
pip install -e .
orari-agent "Domenica il lago ha molte prenotazioni"
```


## Esportazione PDF per WhatsApp

È possibile generare un PDF settimanale pronto per la condivisione manuale su WhatsApp con Angelo, Lorenzo e Giammarco. Il file usa formato **A4 orizzontale**, etichette italiane e una tabella leggibile da smartphone con colonne per lago, negozio e note operative.

Esempio con nome file automatico nella cartella corrente:

```bash
PYTHONPATH=src python -m orari_agent --week-start 2026-06-08 --pdf "Domenica Lorenzo è assente"
```

Con un percorso di output esplicito:

```bash
PYTHONPATH=src python -m orari_agent --week-start 2026-06-08 --pdf --output ./export/Orario_CarpeEvolution_Tenuta_2026-06-08.pdf "Sabato Angelo è in ferie"
```

Se `--output` indica una cartella, il programma crea al suo interno un file con nome standard:

```text
Orario_CarpeEvolution_Tenuta_YYYY-MM-DD.pdf
```

La data nel nome file deriva da `--week-start`, quando presente; altrimenti viene usata la data del giorno di generazione. L'invio automatico su WhatsApp non è incluso: il PDF viene solo creato su disco per essere condiviso manualmente.

## Esempi di comportamento

- Se **Giammarco è richiesto in negozio** in un giorno in cui Lorenzo è al lago, il negozio viene coperto da Giammarco e Angelo può essere spostato sulla chiusura del lago 16:30-18:30.
- Se **Lorenzo è assente domenica**, il motore sposta il suo quinto giorno sul martedì per conservare 5 giorni e 40 ore, mentre Giammarco copre il lago la domenica.
- Se **Angelo è in ferie sabato**, Giammarco copre il negozio. La chiusura lago 16:30-18:30 resta scoperta perché, con Lorenzo vincolato a 8 ore e Angelo assente, non esiste una copertura completa possibile con le sole tre persone.
- Se **Giammarco è dal commercialista, in banca, dai fornitori o in amministrazione**, l’impegno viene registrato come lavoro aziendale esterno e non vale come copertura fissa di lago o negozio.

## Struttura

- `src/orari_agent/business_rules.py` — regole di apertura, orari e vincoli fissi.
- `src/orari_agent/people.py` — persone, ruoli e vincoli individuali.
- `src/orari_agent/generator.py` — generazione e riequilibrio dell'orario settimanale.
- `src/orari_agent/validator.py` — controlli su ore, giorni, coperture e conflitti.
- `src/orari_agent/formatter.py` — output italiano leggibile.
- `src/orari_agent/pdf_exporter.py` — generazione PDF A4 orizzontale separata dal motore di scheduling.
- `src/orari_agent/wife_calendar.py` — predisposizione per calendario persistente della moglie di Giammarco.
- `src/orari_agent/weekly_input.py` — parser leggero delle istruzioni in linguaggio naturale.

## Limiti intenzionali

- L'invio automatico WhatsApp non è implementato: il PDF va condiviso manualmente.
- L'OCR e la lettura immagini non sono ancora implementati.
- Il parser non è un NLP completo: riconosce pattern ricorrenti e conserva come note non interpretate le frasi non supportate.
- Non vengono introdotte risorse esterne oltre ad Angelo, Giammarco e Lorenzo.

## Nota sul calendario della moglie di Giammarco

L'OCR e la lettura immagini non sono implementati. È però presente un archivio JSON persistente e un'interfaccia dedicata. In questa fase solo il codice `M` è un vincolo: Giammarco non può aprire il lago alle 07:30 nella data interessata. I codici `P`, `I`, `F`, colori o altre marcature non vincolano l’orario.
