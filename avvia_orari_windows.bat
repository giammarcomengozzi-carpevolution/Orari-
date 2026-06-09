@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo  Orari Agent - avvio Windows
echo ========================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo ERRORE: Python 3.11 o superiore non trovato.
    echo Installa Python da https://www.python.org/downloads/windows/
    echo Durante l'installazione seleziona "Add python.exe to PATH".
    goto end
)

if not exist "input\weekly_plan.yaml" (
    echo ERRORE: non trovo il file input\weekly_plan.yaml
    echo Controlla di aver avviato questo file dalla cartella principale del progetto.
    goto end
)

if not exist "output" mkdir "output"

if not exist ".venv\Scripts\python.exe" (
    echo Creo l'ambiente locale Python nella cartella .venv...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto error
)

echo Installo o aggiorno le dipendenze del progetto, se necessario...
".venv\Scripts\python.exe" -c "import setuptools" >nul 2>nul
if errorlevel 1 (
    echo ATTENZIONE: setuptools non e' disponibile nell'ambiente locale.
    echo Continuo usando direttamente i file locali del progetto.
) else (
    ".venv\Scripts\python.exe" -m pip install --no-build-isolation -e .
    if errorlevel 1 (
        echo ATTENZIONE: installazione automatica non riuscita.
        echo Continuo usando direttamente i file locali del progetto.
    )
)

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo.
echo Genero il PDF usando input\weekly_plan.yaml...
".venv\Scripts\python.exe" -m orari_agent --planning-file "input\weekly_plan.yaml" --pdf --output "output"
if errorlevel 1 goto error

echo.
echo OPERAZIONE COMPLETATA.
echo Trovi il PDF nella cartella output.
goto end

:error
echo.
echo ERRORE: qualcosa non ha funzionato.
echo Leggi il messaggio qui sopra per capire il problema.

:end
echo.
echo Premi un tasto per chiudere questa finestra...
pause >nul
