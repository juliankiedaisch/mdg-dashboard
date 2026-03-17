from flask import Blueprint, session, request, send_file, redirect, url_for, flash, jsonify
from flask_socketio import emit, join_room, leave_room
from src import socketio, db, globals
from modules.unify.src import db_models
from src.decorators import login_required, permission_required
from src.permissions import user_has_permission
import os, csv
from pathlib import Path
from modules.unify.src.db_models import Device, DeviceGroup, DeviceLocation
from modules.unify.src.background import start as start_background
from modules.unify.src.db_functions import import_devices, delete_device_from_db, delete_group_from_db, rename_device_group
from modules.unify.src.unify_functions import group_locations_lueckenlos
from src.globals import TIMEDELTA
from io import TextIOWrapper, BytesIO
from datetime import timedelta, datetime
from sqlalchemy import desc

class Module():
    ### CHANGE only this (start)

    #MODULE_NAME must be the same as the folder name in /modules/MODULE_NAME/
    MODULE_NAME = "unify"

    # showed in main menu
    MODULE_MENU_NAME = "iPad Standorte"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = True
    MODULE_ICON= "M4.5 3A1.5 1.5 0 0 0 3 4.5v9A1.5 1.5 0 0 0 4.5 15H8v1H6a.5.5 0 0 0 0 1h12a.5.5 0 0 0 0-1h-2v-1h3.5a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 18.5 3h-14Zm0 1.5h14a.5.5 0 0 1 .5.5v9a.5.5 0 0 1-.5.5h-14a.5.5 0 0 1-.5-.5v-9a.5.5 0 0 1 .5-.5Z"
    
    # Submenu configuration - API endpoint that returns submenu items
    MODULE_SUBMENU_API = f"/api{MODULE_URL}/groups"
    MODULE_SUBMENU_TYPE = "dynamic"  # "dynamic" means loaded from API, "static" for predefined items

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "unify.view": "View device groups and device status",
        "unify.manage": "Import, rename, delete device groups and devices",
    }

    UPLOAD_FOLDER = os.path.join(Path(__file__).parent.absolute(), MODULE_URL, 'uploads')

    TERMS_FILE = os.path.join(Path(__file__).parent.absolute(), 'terms.txt')

    def __init__(self, app, db_session, oauth):
        self.app = app
        self.oauth = oauth
        self.db_session = db_session
        self.blueprint = Blueprint(self.MODULE_NAME, __name__, 
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL
        )
        self.clients = {}
        self.register_routes()
        self.register_socketio_events()
        start_background(app, db_session)

    def _calculate_offline_duration(self, last_seen):
        """Calculate how long a device has been offline"""
        if not last_seen:
            return "Nie online gewesen"
        
        now = datetime.now()
        diff = now - last_seen
        
        if diff.days > 0:
            return f"{diff.days} Tag{'e' if diff.days > 1 else ''}"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} Stunde{'n' if hours > 1 else ''}"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} Minute{'n' if minutes > 1 else ''}"
        else:
            return "Gerade eben"

    def register_routes(self):
        @self.blueprint.route(f"/api{self.MODULE_URL}/overview", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("unify.view")
        def unify_overview():
            """Get overview of all devices and their status"""
            all_devices = Device.query.all()
            total_devices = len(all_devices)
            
            online_devices = []
            offline_devices = []
            
            # Consider device offline if no location update in last 15 minutes
            offline_threshold = datetime.now() - timedelta(minutes=15)
            
            for device in all_devices:
                last_location = DeviceLocation.query.filter_by(device_id=device.id).order_by(
                    DeviceLocation.timestamp.desc()
                ).first()
                
                if last_location and last_location.timestamp > offline_threshold:
                    online_devices.append(device.id)
                else:
                    offline_info = {
                        "id": device.id,
                        "name": device.name,
                        "mac": device.mac,
                        "group": device.group.name if device.group else "Keine Gruppe",
                        "last_seen": last_location.timestamp.strftime('%d.%m.%Y %H:%M:%S') if last_location else "Nie",
                        "last_location": last_location.ap_name if last_location else "Unbekannt",
                        "offline_since": self._calculate_offline_duration(last_location.timestamp if last_location else None)
                    }
                    offline_devices.append(offline_info)
            
            return jsonify({
                "total_devices": total_devices,
                "online_count": len(online_devices),
                "offline_count": len(offline_devices),
                "offline_devices": offline_devices
            })
        
        @self.blueprint.route(f"/api{self.MODULE_URL}/groups", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("unify.view")
        def unify_group_menu():
            grouplist = DeviceGroup.query.all()
            return jsonify({
                "groups": [{"id": group.id, "name": group.name, "path": f"/unify/device-groups/{group.id}"} for group in grouplist],
                "isAdmin": user_has_permission("unify.manage")
            })

        @self.blueprint.route(f"/api{self.MODULE_URL}/device/<int:device_id>")
        @login_required(self.oauth)
        @permission_required("unify.view")
        def unify_device_view(device_id):
            device = Device.query.get_or_404(device_id)
            locations = DeviceLocation.query.filter_by(device_id=device.id).order_by(desc(DeviceLocation.timestamp)).all()
            location_blocks = group_locations_lueckenlos(locations)

            return jsonify({
                "name": device.name,
                "mac": device.mac,
                "group_id": device.group_id,
                "locations": [
                    {
                        "ap": block["ap_name"],
                        "start": block["start"].strftime('%d.%m.%Y %H:%M:%S'),
                        "end": block["end"].strftime('%d.%m.%Y %H:%M:%S'),
                    }
                    for block in location_blocks
                ]
            })

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups/<int:group_id>")
        @login_required(self.oauth)
        @permission_required("unify.view")
        def unify_group_view(group_id):
            group = DeviceGroup.query.get_or_404(group_id)
            devices_data = []
            
            # Consider device offline if no location update in last 15 minutes
            offline_threshold = datetime.now() - timedelta(minutes=15)
            
            for device in group.devices:
                last_loc = DeviceLocation.query.filter_by(device_id=device.id).order_by(DeviceLocation.timestamp.desc()).first()
                if last_loc:
                    last_loc.timestamp += timedelta(hours=TIMEDELTA)
                
                # Determine if device is online
                is_online = last_loc and last_loc.timestamp > (offline_threshold + timedelta(hours=TIMEDELTA)) if last_loc else False
                
                devices_data.append({
                    "id": device.id,
                    "name": device.name,
                    "mac": device.mac,
                    "ip": device.ip,
                    "is_online": is_online,
                    "location": {
                        "ap_name": last_loc.ap_name if last_loc else "nicht verbunden",
                        "timestamp": last_loc.timestamp.strftime('%d.%m.%Y %H:%M:%S') if last_loc else ""
                    }
                })
            return jsonify({
                "group": {"id": group.id, "name": group.name},
                "devices": devices_data,
                "isAdmin": user_has_permission("unify.manage")
            })

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups", methods=["POST"])
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def unify_add_group():
            data = request.get_json()
            name = data.get("name", "").strip()
            if not name:
                return jsonify({"status": False, "message": "Gruppenname fehlt."}), 400
            db.session.add(DeviceGroup(name=name))
            db.session.commit()
            return jsonify({"status": True, "message": "Gruppe erfolgreich erstellt."})

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups/<int:group_id>/devices", methods=["POST"])
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def unify_add_device(group_id):
            data = request.get_json()
            mac = data.get("mac", "").strip()
            name = data.get("name", "").strip()
            ip = data.get("ip", "").strip()
            if not mac or not name:
                return jsonify({"status": False, "message": "MAC und Name sind erforderlich."}), 400
            db.session.add(Device(mac=mac, name=name, ip=ip, group_id=group_id))
            db.session.commit()
            return jsonify({"status": True, "message": "Gerät erfolgreich hinzugefügt."})

        @self.blueprint.route(f"/api{self.MODULE_URL}/device/<int:device_id>", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def unify_delete_device(device_id):
            if device_id is None:
                return jsonify({'status' : False, 'message' : "Keine ID Übergeben."}), 400

            return_data = delete_device_from_db(device_id)
            if return_data["status"]:
                return jsonify({'status' : True, 'message' : return_data["message"]})
            return jsonify({'status' : False, 'message' : return_data["message"]})

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups/<int:group_id>", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def unify_delete_group(group_id):
            if group_id is None:
                return jsonify({'status' : False, 'message' : "Keine ID Übergeben."}), 400

            return_data = delete_group_from_db(group_id)
            if return_data["status"]:
                # Notify main namespace to reload submenu
                socketio.emit('load_menu', namespace='/main')
                return jsonify({'status' : True, 'message' : return_data["message"]})
            return jsonify({'status' : False, 'message' : return_data["message"]})

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups/<int:group_id>", methods=["PUT"])
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def unify_rename_group(group_id):
            if group_id is None:
                return jsonify({'status' : False, 'message' : "Keine ID Übergeben."}), 400
            data = request.get_json()
            new_name = data.get("new_name", "").strip()

            if not new_name:
                return jsonify({'status': False, 'message': "Neuer Gruppenname fehlt, bzw. muss gesetzt sein."}), 400

            return_data = rename_device_group(group_id, new_name)
            if return_data["status"]:
                # Notify main namespace to reload submenu
                socketio.emit('load_menu', namespace='/main')
                return jsonify({'status' : True, 'message' : return_data["message"]}), 200
            return jsonify({'status' : False, 'message' : return_data["message"]}), 400

    def register_socketio_events(self):

        @socketio.on('upload_csv', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def handle_upload_csv(data):
            sid = request.sid
            filename = data.get('filename', '')
            file_data = data.get('data', None)
            data["client_id"] = request.sid
            if not file_data or filename == '':
                flash('Keine Datei hochgeladen.')
                socketio.emit('upload_error', 'Keine Datei empfangen.', namespace=self.MODULE_URL,  room=sid)
            
            print("Import starts...")
            try:
                # Dateiinhalt lesen, als Text interpretieren
                file_stream = TextIOWrapper(BytesIO(file_data), encoding='utf-8')
                reader = csv.DictReader(file_stream, delimiter=';')  # falls Semikolon verwendet wird

                geraete_liste = []

                for zeile in reader:
                    raum = zeile.get('Raum')
                    geraetename = zeile.get('\ufeffName')
                    mac = zeile.get('MAC')
                    ip = zeile.get('IP')

                    if raum and geraetename:
                        geraete_liste.append({'raum' : raum.strip(), 'name' : geraetename.strip(), 'mac': mac.strip(), 'ip' : ip.strip()})
                    else:
                        self.app.logger.warning(f"Zeile unvollständig: {zeile}")
                message = import_devices(geraete_liste)
                print(f"{message}")
                # Hier kannst du weiterarbeiten: z.B. in DB speichern
                socketio.emit('upload_success', f'Datei {filename} erfolgreich empfangen und {message}.', namespace=self.MODULE_URL, room=sid)
                # Notify main namespace to reload submenu (broadcast to all clients)
                socketio.emit('load_menu', namespace='/main')
            except Exception as e:
                self.app.logger.exception("Fehler beim Verarbeiten der Datei:")
                print(f"Fehler beim Import: {e}")
                socketio.emit('upload_error', 'Fehler beim Verarbeiten der Datei.', namespace=self.MODULE_URL, room=sid)        
        
        # Wir benoetigt, damit beim senden von Daten auch immer nur der richtige Client angesprochen wird.
        @socketio.on('connect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("unify.manage")
        def handle_connect():
            # Beim Verbinden wird die session ID gespeichert
            self.clients[request.sid] = {"username": session.get('username', 'Unbekannt')}
            join_room(request.sid)
            print(f"Unify: Client {request.sid} verbunden.")

        @socketio.on('disconnect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        def handle_disconnect():
            # Client-ID beim Trennen entfernen
            leave_room(request.sid)
            if request.sid in self.clients:
                del self.clients[request.sid]
            print(f"Unify: Client {request.sid} getrennt.")

        # SocketIO-Event zum Empfang der Frage und Rückgabe der Antwort
        @socketio.on('load_menu', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("unify.view")
        def handle_message(data):
            data["client_id"] = request.sid
            socketio.emit('load_menu', namespace=self.MODULE_URL, room=data["client_id"])
