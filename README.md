# Orari Agent

Agente di pianificazione settimanale per:

- **CarpeEvolution Store**
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

## Esempi di comportamento

- Se **Giammarco è richiesto in negozio** in un giorno in cui Lorenzo è al lago, il negozio viene coperto da Giammarco e Angelo può essere spostato sulla chiusura del lago 16:30-18:30.
- Se **Lorenzo è assente domenica**, il motore sposta il suo quinto giorno sul martedì per conservare 5 giorni e 40 ore, mentre Giammarco copre il lago la domenica.
- Se **Angelo è in ferie sabato**, Giammarco copre il negozio. La chiusura lago 16:30-18:30 resta scoperta perché, con Lorenzo vincolato a 8 ore e Angelo assente, non esiste una copertura completa possibile con le sole tre persone.
- Se **Giammarco è dal commercialista, in banca, dai fornitori o in amministrazione**, l’impegno viene registrato come lavoro aziendale esterno e non vale come copertura fissa di lago o negozio.

## Struttura tecnica

- `src/orari_agent/business_rules.py` — regole di apertura, orari e vincoli fissi.
- `src/orari_agent/people.py` — persone, ruoli e vincoli individuali.
- `src/orari_agent/generator.py` — generazione e riequilibrio dell'orario settimanale.
- `src/orari_agent/validator.py` — controlli su ore, giorni, coperture e conflitti.
- `src/orari_agent/formatter.py` — output italiano leggibile.
- `src/orari_agent/pdf_exporter.py` — generazione PDF A4 orizzontale separata dal motore di scheduling.
- `src/orari_agent/wife_calendar.py` — predisposizione per calendario persistente della moglie di Giammarco.
- `src/orari_agent/weekly_input.py` — parser leggero delle istruzioni in linguaggio naturale e dei file YAML/JSON settimanali.

## Limiti intenzionali

- Non è stata creata una app grafica completa.
- L'invio automatico WhatsApp non è implementato: il PDF va condiviso manualmente.
- L'OCR e la lettura immagini non sono ancora implementati.
- Il parser non è un NLP completo: riconosce pattern ricorrenti e conserva come note non interpretate le frasi non supportate.
- Non vengono introdotte risorse esterne oltre ad Angelo, Giammarco e Lorenzo.

## Nota sul calendario della moglie di Giammarco

L'OCR e la lettura immagini non sono implementati. È però presente un archivio JSON persistente e un'interfaccia dedicata. In questa fase solo il codice `M` è un vincolo: Giammarco non può aprire il lago alle 07:30 nella data interessata. I codici `P`, `I`, `F`, colori o altre marcature non vincolano l’orario.

---

# Bot Telegram privato con memoria SQLite

Questa versione aggiunge un **chatbot Telegram privato** che permette a Gianmarco di scrivere note durante la settimana e poi generare direttamente il PDF dell'orario settimanale.

La CLI e i launcher storici restano disponibili; il bot usa lo stesso motore di generazione PDF già presente nel progetto.

## Cosa fa il bot

- salva messaggi liberi come note settimanali persistenti in SQLite;
- protegge l'accesso con `ALLOWED_TELEGRAM_USER_ID`;
- genera l'orario con le regole fisse di CarpeEvolution Store e Tenuta del Germano;
- valida l'orario e riepiloga eventuali avvisi/conflitti;
- crea un PDF A4 orizzontale pronto da inoltrare su Telegram o WhatsApp;
- invia il PDF direttamente nella chat Telegram;
- mantiene già pronta la tabella `wife_calendar` per la regola futura sul codice `M`.

## Comandi Telegram

- `/start` — spiega cosa fa il bot.
- `/aiuto` — mostra esempi e comandi.
- `/nota Giovedì Gianmarco in negozio tutto il giorno per fatture` — salva una nota.
- `/lista` — mostra le note attive della settimana corrente/prossima.
- `/lista dal 17 al 23 giugno` — mostra le note di una settimana specifica.
- `/cancella 12` — cancella la nota con ID 12.
- `/genera` — genera il PDF della settimana prossima.
- `/genera dal 17 al 23 giugno` — genera il PDF della settimana indicata.
- `/reset_settimana dal 17 al 23 giugno confermo` — archivia le note attive della settimana indicata.

Puoi anche scrivere messaggi normali, ad esempio:

```text
Giovedì Gianmarco deve stare in negozio tutto il giorno per fatture.
Sabato Lorenzo deve uscire alle 15.
Domenica al lago ci sono molte prenotazioni.
Martedì prossimo Angelo non c'è la mattina.
Venerdì io sono dal commercialista alle 10.
```

Se il messaggio inizia con `Genera orario`, il bot genera il PDF invece di salvarlo come nota.

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
- `src/orari_agent/storage/` — SQLite, repository note, cronologia PDF, calendario moglie e parsing settimane.
- `src/orari_agent/bot_runner.py` — entry point installabile `orari-telegram-bot`.

## Database SQLite

All'avvio il bot crea automaticamente le tabelle:

- `notes` — note attive/usate/cancellate con testo originale e metadati interpretati;
- `generated_schedules` — cronologia PDF generati, riepilogo e avvisi;
- `wife_calendar` — tabella pronta per il calendario moglie; per ora il motore può usare il codice `M` se presente.

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
4. scrivi una o più note;
5. scrivi `/lista`;
6. scrivi `/genera` e controlla che arrivi il PDF.
