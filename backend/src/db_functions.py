from datetime import datetime, timezone
from src.db_models import User, Group

def upsert_user_with_groups(uuid, username, groups, db_session):

    # Benutzer abrufen oder neu erstellen
    user = db_session.query(User).filter_by(uuid=uuid).first()

    if not user:
        user = User(uuid=uuid, username=username)
        db_session.add(user)
    else:
        user.username = username  # optional aktualisieren

    # Last Login aktualisieren
    user.last_login = datetime.now(timezone.utc)

    # Bestehende Gruppen abrufen oder neu erstellen
    current_groups = []
    for group_data in groups.values():
        group = db_session.query(Group).filter_by(uuid=group_data["act"]).first()
        if not group:
            group = Group(name=group_data["name"],uuid=group_data["act"])
            db_session.add(group)
        current_groups.append(group)

    # Gruppenmitgliedschaften aktualisieren
    user.groups = current_groups

    db_session.commit()