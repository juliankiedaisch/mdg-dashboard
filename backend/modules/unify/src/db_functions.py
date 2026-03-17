from src.db import db
from modules.unify.src.db_models import Device, DeviceGroup, DeviceLocation


def import_devices(device_data):
    """
    device_data: Liste von Dictionaries mit den Keys: 'mac', 'name', 'raum', 'ip'
    Beispiel:
        [
            {'mac': 'AA:BB:CC:DD:EE:01', 'name': 'Gerät 1', 'raum': 'Gruppe A', 'ip' : '0.0.0.0'},
            {'mac': 'AA:BB:CC:DD:EE:02', 'name': 'Gerät 2', 'raum': 'Gruppe B', 'ip' : '0.0.0.0'},
        ]
    """
    new_devices = 0
    new_groups = 0
    updated_group_assignments = 0

    group_cache = {}

    for entry in device_data:
        mac = entry['mac'].strip().lower()
        name = entry['name'].strip()
        ip = entry['ip'].strip()
        group_name = entry['raum'].strip()

        # Gruppe holen oder anlegen
        group = group_cache.get(group_name)
        if group is None:
            group = DeviceGroup.query.filter_by(name=group_name).first()
            if group is None:
                group = DeviceGroup(name=group_name)
                db.session.add(group)
                db.session.flush()  # Damit group.id bereits verfügbar ist
                new_groups += 1
            group_cache[group_name] = group

        # Gerät holen oder anlegen
        device = Device.query.filter_by(mac=mac).first()
        if device is None:
            device = Device(mac=mac, name=name, group=group, ip=ip)
            db.session.add(device)
            new_devices += 1
        else:
            # Name ggf. aktualisieren
            device.name = name
            device.ip = ip
            if device.group_id != group.id:
                device.group = group
                updated_group_assignments += 1

    db.session.commit()

    return {
        "new_devices": new_devices,
        "new_groups": new_groups,
        "updated_group_assignments": updated_group_assignments,
    }

def delete_device_from_db(device_id):
    device = Device.query.get_or_404(device_id)
    return_value = f"{device.name} wurde erfolgreich aus der Datenbank gelöscht"
    return_status = True
    try:
        locations = DeviceLocation.query.filter_by(device_id=device.id).all()

        for loc in locations:
            db.session.delete(loc)

        # Gerät selbst löschen
        db.session.delete(device)

        # Änderungen übernehmen
        db.session.commit()
    except Exception as e:
        return_value = f"Beim löschen von {device.name} ist ein Fehler aufgetreten: {e}"
        return_status = False

    return {"message": return_value, "status": return_status}


def delete_group_from_db(group_id):
    try:
        # Gruppe holen
        group = db.session.query(DeviceGroup).filter_by(id=group_id).first()
        if not group:
            return {"status": False, "message": "Gerätegruppe nicht gefunden."}

        # Alle Geräte der Gruppe holen
        devices = db.session.query(Device).filter_by(group_id=group_id).all()
        device_ids = [device.id for device in devices]

        # DeviceLocations löschen
        if device_ids:
            db.session.query(DeviceLocation).filter(DeviceLocation.device_id.in_(device_ids)).delete(synchronize_session=False)

        # Devices löschen
        db.session.query(Device).filter_by(group_id=group_id).delete(synchronize_session=False)

        # Gruppe löschen
        db.session.delete(group)

        # Änderungen speichern
        db.session.commit()
        return {"status": True, "message": "Gruppe und zugehörige Geräte wurden gelöscht."}

    except Exception as e:
        db.session.rollback()
        return {"status": False, "message": f"Fehler beim Löschen: {str(e)}"}

def rename_device_group(group_id, new_name):
    from sqlalchemy.exc import IntegrityError

    try:
        # Gruppe nach ID suchen
        group = db.session.query(DeviceGroup).filter_by(id=group_id).first()

        if not group:
            return {"status": False, "message": "Gruppe nicht gefunden."}

        # Namen ändern
        group.name = new_name
        db.session.commit()
        return {"status": True, "message": f"Gruppe wurde in '{new_name}' umbenannt."}

    except IntegrityError:
        db.session.rollback()
        return {"status": False, "message": "Eine Gruppe mit diesem Namen existiert bereits."}

    except Exception as e:
        db.session.rollback()
        return {"status": False, "message": f"Fehler beim Umbenennen: {str(e)}"}