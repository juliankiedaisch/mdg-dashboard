from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import desc
from src.db import db
from datetime import datetime, timezone
from modules.unify.src.db_models import Device, DeviceLocation
from modules.unify.src.unify_functions import fetch_client_locations

# --- Hintergrundjob ---
def poll_devices(app, db_session):
    with app.app_context():
        try:
            locations = fetch_client_locations()
            now = datetime.now(timezone.utc)

            for device in Device.query.all():
                if device.mac not in locations:
                    continue

                ap_mac, ap_name = locations[device.mac]

                # Letzte zwei Einträge holen
                recent_locations = db_session.query(DeviceLocation)\
                    .filter_by(device_id=device.id)\
                    .order_by(desc(DeviceLocation.timestamp))\
                    .limit(2)\
                    .all()

                if not recent_locations or len(recent_locations) == 1:
                    # Noch kein Eintrag vorhanden – neuen erstellen
                    db_session.add(DeviceLocation(
                        device_id=device.id,
                        timestamp=now,
                        ap_mac=ap_mac,
                        ap_name=ap_name
                    ))

                else:
                    # Zwei Einträge vorhanden
                    last_location, prev_location = recent_locations[0], recent_locations[1]

                    if (
                        last_location.ap_mac == ap_mac and last_location.ap_name == ap_name and
                        prev_location.ap_mac == ap_mac and prev_location.ap_name == ap_name
                    ):
                        # Zwei vorherige identische Locations – Timestamp aktualisieren
                        last_location.timestamp = now
                    else:
                        # Neue Location oder nur ein vorheriger Eintrag mit gleicher Location
                        db_session.add(DeviceLocation(
                            device_id=device.id,
                            timestamp=now,
                            ap_mac=ap_mac,
                            ap_name=ap_name
                        ))

            db_session.commit()

        except Exception as e:
            print(f"Fehler im Background Scheduler: {e}")

def start(app, db_session):
    scheduler = BackgroundScheduler()
    scheduler.add_job(poll_devices, 'interval', args=[app, db_session], minutes=1)
    scheduler.start()