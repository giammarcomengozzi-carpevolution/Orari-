#!/bin/bash
cd "$(dirname "$0")" || exit 1

echo "========================================"
echo " Orari Agent - avvio Mac"
echo "========================================"
echo

finish() {
    echo
    echo "Premi INVIO per chiudere questa finestra..."
    read -r _
}

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERRORE: Python 3 non trovato."
    echo "Installa Python 3.11 o superiore da https://www.python.org/downloads/macos/"
    finish
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    echo "ERRORE: serve Python 3.11 o superiore."
    echo "Installa una versione aggiornata da https://www.python.org/downloads/macos/"
    finish
    exit 1
fi

if [ ! -f "input/weekly_plan.yaml" ]; then
    echo "ERRORE: non trovo il file input/weekly_plan.yaml"
    echo "Controlla di aver avviato questo file dalla cartella principale del progetto."
    finish
    exit 1
fi

mkdir -p output

if [ ! -x ".venv/bin/python" ]; then
    echo "Creo l'ambiente locale Python nella cartella .venv..."
    python3 -m venv .venv || {
        echo "ERRORE: impossibile creare l'ambiente Python locale."
        finish
        exit 1
    }
fi

echo "Installo o aggiorno le dipendenze del progetto, se necessario..."
if ".venv/bin/python" -c 'import setuptools' >/dev/null 2>&1; then
    if ! ".venv/bin/python" -m pip install --no-build-isolation -e .; then
        echo "ATTENZIONE: installazione automatica non riuscita."
        echo "Continuo usando direttamente i file locali del progetto."
    fi
else
    echo "ATTENZIONE: setuptools non è disponibile nell'ambiente locale."
    echo "Continuo usando direttamente i file locali del progetto."
fi

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "Genero il PDF usando input/weekly_plan.yaml..."
".venv/bin/python" -m orari_agent --planning-file "input/weekly_plan.yaml" --pdf --output "output" || {
    echo "ERRORE: generazione PDF non riuscita."
    finish
    exit 1
}

echo
echo "OPERAZIONE COMPLETATA."
echo "Trovi il PDF nella cartella output."
finish
