#!/bin/bash

# Absoluter Pfad zur virtuellen Umgebung
VENV_PATH="/root/.venv"
APP_DIR="/root/mdg-admin-dashboard"
APP_MODULE="app:app"
BIND_ADDRESS="0.0.0.0:5000"
LOGFILE="$APP_DIR/server.log"

# In das Verzeichnis der App wechseln
cd "$APP_DIR" || exit 1

# Endlosschleife zur Überwachung und Neustart bei Fehlern
while true; do
    echo "[$(date)] Starte Gunicorn mit eventlet..."
    
    # Aktivieren der virtuellen Umgebung
    source "$VENV_PATH/bin/activate"

    # Starte Gunicorn mit eventlet worker
    gunicorn -k eventlet -w 1 "$APP_MODULE" --bind "$BIND_ADDRESS" >> "$LOGFILE" 2>&1

    # Falls gunicorn abstürzt, kurz warten und neu starten
    echo "[$(date)] Gunicorn wurde beendet. Neustart in 5 Sekunden..."
    sleep 5
done
