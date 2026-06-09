# Orari Agent

Prima versione dell'agente di pianificazione settimanale per:

- **CarpeEvolution Store**
- **Tenuta del Germano**

L'agente conserva le regole fisse, interpreta semplici istruzioni settimanali in linguaggio naturale, genera una tabella in italiano e segnala conflitti, mancate coperture e violazioni delle regole di Lorenzo.

## Avvio rapido

```bash
PYTHONPATH=src python -m orari_agent "La prossima settimana Lorenzo deve aprire il lago martedì. Giovedì Gianmarco deve stare in negozio per fatture. Domenica il lago ha molte prenotazioni."
```

In alternativa, dopo installazione locale:

```bash
pip install -e .
orari-agent "Domenica il lago ha molte prenotazioni"
```

## Struttura

- `src/orari_agent/business_rules.py` — regole di apertura, orari e vincoli fissi.
- `src/orari_agent/people.py` — persone, ruoli e vincoli individuali.
- `src/orari_agent/generator.py` — generazione dell'orario settimanale.
- `src/orari_agent/validator.py` — controlli su ore, giorni, coperture e conflitti.
- `src/orari_agent/formatter.py` — output italiano leggibile.
- `src/orari_agent/wife_calendar.py` — predisposizione per calendario persistente della moglie di Gianmarco.
- `src/orari_agent/weekly_input.py` — parser leggero delle istruzioni in linguaggio naturale.

## Nota sul calendario della moglie di Gianmarco

L'OCR e la lettura immagini non sono implementati in questa prima versione. È però presente un archivio JSON persistente e un'interfaccia dedicata, così una prossima attività potrà aggiungere lettura immagine, codici `M`, `P`, `I`, `MPI` e regole operative senza riscrivere il generatore.
