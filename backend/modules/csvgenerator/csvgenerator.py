from flask import Blueprint, session, request, url_for, jsonify, send_from_directory
from flask_socketio import emit, join_room, leave_room
from src import socketio, globals
from src.decorators import login_required, permission_required, permission_required
import os, threading, time, csv
import pandas as pd
from pathlib import Path
from io import BytesIO, StringIO
import base64

def delete_file_after_delay(filepath, delay):
    """Delete file after specified delay in seconds"""
    try:
        time.sleep(delay)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[CSV Generator] Deleted file: {filepath}")
        else:
            print(f"[CSV Generator] File already deleted: {filepath}")
    except Exception as e:
        print(f"[CSV Generator] Error deleting file {filepath}: {e}")

class Module():
    ### CHANGE only this (start)

    #MODULE_NAME must be the same as the folder name in /modules/MODULE_NAME/
    MODULE_NAME = "csvgenerator"

    # showed in main menu
    MODULE_MENU_NAME = "CSV Generator"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = True
    MODULE_ICON= "M2 6.75A2.75 2.75 0 0 1 4.75 4h10.5A2.75 2.75 0 0 1 18 6.75v10.5A2.75 2.75 0 0 1 15.25 20H4.75A2.75 2.75 0 0 1 2 17.25V6.75Zm2.75-.25a.25.25 0 0 0-.25.25v10.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25V6.75a.25.25 0 0 0-.25-.25H4.75ZM20 5a1 1 0 0 1 1 1v12a1 1 0 1 1-2 0V6a1 1 0 0 1 1-1Z"

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "csvgenerator.use": "Use CSV Generator to upload, process, and download CSV/Excel files",
        "csvgenerator.manage_terms": "Manage filter terms for CSV processing",
    }

    UPLOAD_FOLDER = os.path.join(Path(__file__).parent.absolute(), 'static', 'download')

    TERMS_FILE_BUECHEREI = Path(__file__).parent.absolute() / 'terms_buecherei.txt'
    TERMS_FILE_MOODLE = Path(__file__).parent.absolute() / 'terms_moodle.txt'

    # Stelle sicher, dass das Verzeichnis existiert
    TERMS_FILE_BUECHEREI.parent.mkdir(parents=True, exist_ok=True)

    # Lege die Dateien an, falls sie nicht existieren
    TERMS_FILE_BUECHEREI.touch(exist_ok=True)
    TERMS_FILE_MOODLE.touch(exist_ok=True)

    def __init__(self, oauth):
        self.blueprint = Blueprint(self.MODULE_NAME, __name__, 
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL
        )
        self.oauth = oauth
        self.clients = {}
        self.register_routes()
        self.register_socketio_events()

    def load_terms(self, term_file):
        if os.path.exists(term_file):
            with open(term_file, 'r') as file:
                return file.read().strip()
        return ''
   
    def process_csv_buecherei(self, csv_text, terms_to_remove):
        status = True
        processed_filepath = os.path.join(self.UPLOAD_FOLDER, 'Lehrerimport-Schulbuechereimodul.csv')

        try:
            # Lade den Text als CSV über StringIO
            df = pd.read_csv(StringIO(csv_text), delimiter=";", on_bad_lines='skip', encoding="utf-8")

            # Entferne Zeilen mit leerer 2. Spalte
            df = df[df.iloc[:, 1].notna()]

            # Filtere Begriffe in den ersten 3 Spalten
            for term in terms_to_remove:
                df = df[~df.iloc[:, :3].apply(
                    lambda row: row.astype(str).str.contains(rf'\b{term}\b', case=False, regex=True).any(),
                    axis=1
                )]

            # Setze in Spalte "Klasse/Information" den Wert "Lehrer"
            if 'Klasse/Information' in df.columns:
                df['Klasse/Information'] = "Lehrer"
            elif df.shape[1] >= 10:
                # Fallback: Verwende Index 9 falls Spaltenname nicht existiert
                column_name = df.columns[9]
                df[column_name] = "Lehrer"
            
            print(processed_filepath)
            df.to_csv(processed_filepath, index=False, sep=";", encoding="utf-8")

        except Exception as e:
            print(f"Fehler bei CSV-Verarbeitung Iserv Buecherei: {e}")
            status = False

        return status, processed_filepath

    def process_csv_moodle(self, csv_text, terms_to_remove):
        # Liste für die gespeicherten Daten
        accounts_liste = []
        status = True
        processed_filepath = os.path.join(self.UPLOAD_FOLDER, 'Moodle_Teacher.csv')
        try:
            reader = csv.DictReader(StringIO(csv_text), delimiter=';')  # DictReader liest die CSV als Dictionary
            for zeile in reader:
                # Daten für jeden Account speichern
                account = {
                    "Account": zeile["Account"],
                    "Vorname": zeile["Vorname"],
                    "Nachname": zeile["Nachname"],
                    "Email": zeile["E-Mail-Adresse"]
                }
                accounts_liste.append(account)

            #processed_filepath = 'Moodle_Teacher.csv'
            with open(processed_filepath, 'w', encoding='utf-8') as file:
                firstLine = "username;firstname;lastname;email;password;cohort1;cohort2;profile_field_schoolno;profile_field_schoolname;profile_field_schoolpersona\n"
                profile_field_schoolno = "5841"
                profile_field_schoolname = "Marion Dönhoff Gymnasium"
                profile_field_schoolpersona = "Lehrer/in"
                cohort1 = "5841_mdg"
                cohort2 = cohort1 + "_teacher"
                file.write(firstLine)
                for elem in accounts_liste:
                    file.write(elem["Account"] + ";" + elem["Vorname"] + ";" + elem["Nachname"] + ";" + elem["Email"] + ";;" + cohort1 + ";" + cohort2 + ";" + profile_field_schoolno + ";" + profile_field_schoolname + ";" + profile_field_schoolpersona + "\n")
            
                # CSV-Datei einlesen
            df = pd.read_csv(processed_filepath, delimiter=';', encoding='utf-8-sig')  # Semikolon-Trennzeichen und BOM-Entfernung

            # Einträge entfernen
            for term in terms_to_remove:
                df = df[~df.iloc[:, :3].apply(
                    lambda row: row.astype(str).str.contains(rf'\b{term}\b', case=False, regex=True).any(), axis=1
                )]

            # Ergebnis speichern (optional)
            df.to_csv(processed_filepath, index=False, sep=';', encoding='utf-8-sig')

        except Exception as e:
            print(f"Fehler bei CSV-Verarbeitung Moodle: {e}")
            status = False

        return status, processed_filepath

    def process_excel_anmeldedaten(self, excel_data):
        status = True
        processed_filepath = os.path.join(self.UPLOAD_FOLDER, 'Anmeldedaten.xlsx')
        message = "Excel Datei erfolgreich erstellt."
        try:
            # Decode base64 → bytes
            file_bytes = base64.b64decode(excel_data)

            # Convert to a BytesIO stream
            file_stream = BytesIO(file_bytes)
            xls = pd.ExcelFile(file_stream)
            df = pd.read_excel(xls, xls.sheet_names[1])

                # neue Tabelle mit deinen Spalten
            neue_tabelle = pd.DataFrame({
                    "Vorname sorgeber. Person": df["Vorname der sorgeberechtigten Person"],
                    "Nachname sorgeber. Person": df["Nachname der sorgeberechtigten Person"],
                    "Vorname Kind": df["Name Teilnehmer*in: Vorname"],
                    "Nachname Kind": df["Name Teilnehmer*in: Nachname"],
                    "Tag und Beginn": df["Beginn"],
                    "Geschwisterkind ja/nein": df["Wird im kommenden Schuljahr ein Geschwisterkind unsere Schule besuchen?"],
                    "Grundschule des Kindes": df["Grundschule des Kindes"],
                    "Gymnasialempfehlung ja/nein": df["Liegt eine Gymnasialempfehlung vor"],
                    "Telefonnummer": df["Telefonnummer"],
                    "Email": df["E-Mail"],
            })

            neue_tabelle.to_excel(processed_filepath, index=False)


        except Exception as e:
            message = f"Fehler bei Excel-Verarbeitung der Anmeldedaten: {e}"
            print(message)
            status = False

        return status, message, processed_filepath

    def register_routes(self):
        @self.blueprint.route(f"/api{self.MODULE_URL}/terms", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def get_terms():
            """Get saved filter terms"""
            return jsonify({
                "terms_buecherei": self.load_terms(self.TERMS_FILE_BUECHEREI),
                "terms_moodle": self.load_terms(self.TERMS_FILE_MOODLE)
            })
        
        @self.blueprint.route(f"/api{self.MODULE_URL}/download/<filename>", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def download_file(filename):
            """Serve generated CSV/Excel files"""
            try:
                return send_from_directory(self.UPLOAD_FOLDER, filename, as_attachment=True)
            except FileNotFoundError:
                return jsonify({"error": "File not found"}), 404
        

    def register_socketio_events(self):

        # Wir benoetigt, damit beim senden von Daten auch immer nur der richtige Client angesprochen wird.
        @socketio.on('connect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def handle_connect():
            # Beim Verbinden wird die session ID gespeichert
            self.clients[request.sid] = {"username": session.get('username', 'Unbekannt')}
            join_room(request.sid)
            print(f"Client {request.sid} verbunden.")

        @socketio.on('disconnect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def handle_disconnect():
            # Client-ID beim Trennen entfernen
            leave_room(request.sid)
            if request.sid in self.clients:
                del self.clients[request.sid]
            print(f"Client {request.sid} getrennt.")

        @socketio.on("generate_iserv_csv", namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def handle_iserv_csv(data):
            try:
                terms = data["terms"]
                with open(self.TERMS_FILE_BUECHEREI, 'w') as term_file:
                    term_file.write(terms)
                csv_text = data.get("content", "")
                status, processed_filepath = self.process_csv_buecherei(csv_text, data["terms"].split(','))

                # Dateiname für Downloadlink erzeugen
                download_filename = os.path.basename(processed_filepath)
                download_link = f"/api/csvgenerator/download/{download_filename}"

                # Lösche Datei nach 60 Sekunden
                cleanup_thread = threading.Thread(target=delete_file_after_delay, args=(processed_filepath, 60))
                cleanup_thread.daemon = False
                cleanup_thread.start()
                print(f"[CSV Generator] Cleanup thread started for {download_filename}")

                emit("csv_ready", {
                    "status": status,
                    "message": "CSV erfolgreich erstellt.",
                    "link": download_link,
                    "type": "iservbuecherei"
                })
            except Exception as e:
                print(e)
                emit("csv_error", {"error": str(e), "type": "iservbuecherei"})

        @socketio.on("generate_moodle_csv", namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def handle_moodle_csv(data):
            try:
                terms = data["terms"]
                with open(self.TERMS_FILE_MOODLE, 'w') as term_file:
                    term_file.write(terms)
                csv_text = data.get("content", "")
                status, processed_filepath = self.process_csv_moodle(csv_text, data["terms"].split(','))

                # Dateiname für Downloadlink erzeugen
                download_filename = os.path.basename(processed_filepath)
                download_link = f"/api/csvgenerator/download/{download_filename}"

                # Lösche Datei nach 60 Sekunden
                cleanup_thread = threading.Thread(target=delete_file_after_delay, args=(processed_filepath, 60))
                cleanup_thread.daemon = False
                cleanup_thread.start()
                print(f"[CSV Generator] Cleanup thread started for {download_filename}")

                emit("csv_ready", {
                    "status": status,
                    "message": "CSV erfolgreich erstellt.",
                    "link": download_link,
                    "type": "moodle"
                })
            except Exception as e:
                print(e)
                emit("csv_error", {"error": str(e), "type": "moodle"})

        @socketio.on("generate_anmeldedaten_csv", namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("csvgenerator.use")
        def handle_anmeldedaten_csv(data):
            try:
               
                excel_data = data.get("content", "")
                status, message, processed_filepath = self.process_excel_anmeldedaten(excel_data)

                # Dateiname für Downloadlink erzeugen
                download_filename = os.path.basename(processed_filepath)
                download_link = f"/api/csvgenerator/download/{download_filename}"

                # Lösche Datei nach 60 Sekunden
                cleanup_thread = threading.Thread(target=delete_file_after_delay, args=(processed_filepath, 60))
                cleanup_thread.daemon = False
                cleanup_thread.start()
                print(f"[CSV Generator] Cleanup thread started for {download_filename}")

                emit("csv_ready", {
                    "status": status,
                    "message": message,
                    "link": download_link,
                    "type": "anmeldedaten"
                })
            except Exception as e:
                print(e)
                emit("csv_error", {"error": str(e), "type": "anmeldedaten"})