# Orari Agent

Agente di pianificazione settimanale per:

- **CarpeEvolution Store**
- **Tenuta del Germano**

L'agente conserva le regole fisse, interpreta semplici istruzioni settimanali in linguaggio naturale, genera una tabella in italiano e segnala conflitti, mancate coperture e violazioni delle regole di Lorenzo.

## Priorità operative predefinite

1. **Angelo Antonelli** copre il negozio di default.
2. **Lorenzo Sansavini** copre il lago di default, con 5 giorni e 40 ore settimanali.
3. **Gianmarco Mengozzi** viene usato come jolly flessibile solo quando serve copertura, quando un'istruzione settimanale lo richiede o quando un'altra persona non è disponibile.

Il motore prova a mantenere sempre almeno una persona al lago e una persona in negozio durante gli orari di apertura. Se una combinazione di assenze rende impossibile coprire tutto con le sole tre persone disponibili e con i vincoli di Lorenzo, l'orario viene comunque generato e il validatore evidenzia l'intervallo scoperto.

## Istruzioni supportate

Il parser leggero riconosce frasi italiane o inglesi con giorno, persona e intenzione. Esempi:

- `Giovedì Gianmarco deve stare in negozio.`
- `Martedì Lorenzo deve aprire il lago.`
- `Domenica Lorenzo è assente.`
- `Sabato Angelo è in ferie.`
- `Venerdì Gianmarco deve stare al lago.`
- `Domenica il lago ha molte prenotazioni.`

Le istruzioni possono essere passate in un unico testo, separate da punto o a capo.

## Avvio rapido

```bash
PYTHONPATH=src python -m orari_agent "Giovedì Gianmarco deve stare in negozio. Martedì Lorenzo deve aprire il lago. Domenica Lorenzo è assente. Sabato Angelo è in ferie. Venerdì Gianmarco deve stare al lago."
```

In alternativa, dopo installazione locale:

```bash
pip install -e .
orari-agent "Domenica il lago ha molte prenotazioni"
```

## Esempi di comportamento

- Se **Gianmarco è richiesto in negozio** in un giorno in cui Lorenzo è al lago, il negozio viene coperto da Gianmarco e Angelo può essere spostato sulla chiusura del lago 16:30-18:30.
- Se **Lorenzo è assente domenica**, il motore sposta il suo quinto giorno sul martedì per conservare 5 giorni e 40 ore, mentre Gianmarco copre il lago la domenica.
- Se **Angelo è in ferie sabato**, Gianmarco copre il negozio. La chiusura lago 16:30-18:30 resta scoperta perché, con Lorenzo vincolato a 8 ore e Angelo assente, non esiste una copertura completa possibile con le sole tre persone.

## Struttura

- `src/orari_agent/business_rules.py` — regole di apertura, orari e vincoli fissi.
- `src/orari_agent/people.py` — persone, ruoli e vincoli individuali.
- `src/orari_agent/generator.py` — generazione e riequilibrio dell'orario settimanale.
- `src/orari_agent/validator.py` — controlli su ore, giorni, coperture e conflitti.
- `src/orari_agent/formatter.py` — output italiano leggibile.
- `src/orari_agent/wife_calendar.py` — predisposizione per calendario persistente della moglie di Gianmarco.
- `src/orari_agent/weekly_input.py` — parser leggero delle istruzioni in linguaggio naturale.

## Limiti intenzionali

- La generazione PDF non è ancora implementata.
- L'OCR e la lettura immagini non sono ancora implementati.
- Il parser non è un NLP completo: riconosce pattern ricorrenti e conserva come note non interpretate le frasi non supportate.
- Non vengono introdotte risorse esterne oltre ad Angelo, Gianmarco e Lorenzo.

## Nota sul calendario della moglie di Gianmarco

L'OCR e la lettura immagini non sono implementati. È però presente un archivio JSON persistente e un'interfaccia dedicata, così una prossima attività potrà aggiungere lettura immagine, codici `M`, `P`, `I`, `MPI` e regole operative senza riscrivere il generatore.
