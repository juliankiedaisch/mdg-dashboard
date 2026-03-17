from src.db import db
from src.globals import TIMEDELTA
from sqlalchemy.orm import joinedload
from modules.approvals.src.db_models import Applications, Approval
from src.db_models import User, Group
from src.permissions import user_has_permission
from datetime import datetime, timezone, timedelta
from pytz import utc 
from flask import session

def create_application(name: str, description: str = "", url: str = "") -> Applications:
    """
    Erstellt einen neuen Application-Eintrag in der Datenbank.

    :param name: Name der Anwendung (Pflichtfeld)
    :param description: Beschreibung der Anwendung (optional)
    :param url: URL der Anwendung (optional)
    :return: Das erstellte Applications-Objekt
    """
    application = Applications(name=name, description=description, url=url)
    db.session.add(application)
    db.session.commit()
    return application

def delete_application_and_approvals(application_id):
    application = Applications.query.get(application_id)
    if not application:
        print(f"Application mit ID {application_id} wurde nicht gefunden.")
        return {"status": False, "message": "Anwendung nicht gefunden."}

    # Alle zugehörigen Approvals löschen
    for approval in application.approvals:
        db.session.delete(approval)

    # Application selbst löschen
    db.session.delete(application)

    try:
        db.session.commit()
        return {"status": True, "message": "Anwendung und zugehörige Freigaben wurden gelöscht."}
    except Exception as e:
        db.session.rollback()
        return {"status": False, "message": "Fehler bei der Löschung der Anwendung."}


def update_application(app_id, new_name, new_description, new_url):
    from sqlalchemy.exc import IntegrityError

    try:
        # Gruppe nach ID suchen
        app = db.session.query(Applications).filter_by(id=app_id).first()

        if not app:
            return {"status": False, "message": "Anwendung nicht gefunden."}
        elif not new_name:
            return {"status": False, "message": "Ein Name muss gegeben sein."}
        elif not new_url:
            return {"status": False, "message": "Eine URL muss gegeben sein."}

        # Namen ändern
        app.name = new_name
        app.description = new_description
        app.url = new_url
        db.session.commit()
        return {"status": True, "message": f"Anwendung '{new_name}' wurde aktualisiert."}

    except IntegrityError:
        db.session.rollback()
        return {"status": False, "message": "Eine Anwendung mit diesem Namen existiert bereits."}

    except Exception as e:
        db.session.rollback()
        return {"status": False, "message": f"Fehler beim Aktualisieren: {str(e)}"}
    

def add_new_approval(app_id, user_ids, group_ids, start_time, end_time, current_user_uuid):
    try:
        # Application holen
        application = Applications.query.get(int(app_id))
        if not application:
            return {'status': False, 'message': 'Anwendung nicht gefunden.'}

        # Aktuellen Nutzer ermitteln (angenommen: request.user oder current_user.uuid)
        given_by = User.query.filter_by(uuid=current_user_uuid).first()
        if not given_by:
            return {'status': False, 'message': 'Vergebender Benutzer nicht gefunden.'}

        # Benutzer und Gruppen abrufen
        users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
        groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []

        if not users and not groups:
            return {'status': False, 'message': 'Mindestens ein Benutzer oder eine Gruppe ist erforderlich.'}

        # Approval erstellen
        approval = Approval(
            application=application,
            given_by=given_by,
            start=start_time,
            end=end_time,
            approved_users=users,
            groups=groups
        )

        db.session.add(approval)
        db.session.commit()
        print("Eingetragen")
        return {'status': True, 'message': "Neue Freigabe wurde hinzugefügt."}
    except Exception as e:
        db.session.rollback()
        return {'status': False, 'message': f'Unerwarteter Fehler: {str(e)}'}

def get_approvels_for_user(user_uuid, only_active=True):
    try:
        now = datetime.now(timezone.utc) + timedelta(hours=TIMEDELTA)

        # Hole den Benutzer anhand der UUID
        user = User.query.filter_by(uuid=user_uuid).first()
        if not user:
            print("no user found for approvals")
            return []

        active_approvals = []
        for approval in user.approvals_given:
            start = approval.start + timedelta(hours=TIMEDELTA)
            end = approval.end + timedelta(hours=TIMEDELTA)

            # Konvertiere naive Datumsobjekte zu UTC
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=utc)
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=utc)

            if start <= now and (end is None or end >= now) or not only_active:
                approved_usernames = ", ".join(sorted(u.username for u in approval.approved_users))
                approved_groupnames = ", ".join(sorted(g.name for g in approval.groups))

                active_approvals.append({
                    'approval_id': approval.id,
                    'application_id': approval.application_id,
                    'application_name': approval.application.name if approval.application else None,
                    'start': start.strftime("%-d.%-m.%Y - %H:%M"),
                    'end': end.strftime("%-d.%-m.%Y - %H:%M") if end else None,
                    'given_by': approval.given_by.username if approval.given_by else None,
                    'approved_users': approved_usernames,
                    'approved_groups': approved_groupnames,
                })

        print(len(active_approvals))
        return active_approvals
    
    except Exception as e:
        print(f"Fehler beim Abrufen der aktiven Approvals: {e}")
        return []
    
def get_approvels_for_app(app_id, only_active=True):
    try:
        now = datetime.now(timezone.utc) + timedelta(hours=TIMEDELTA)

        # Hole den Benutzer anhand der UUID
        app = Applications.query.filter_by(id=app_id).first()
        if not app:
            print("no app found for approvals")
            return []

        active_approvals = []
        for approval in app.approvals:
            start = approval.start + timedelta(hours=TIMEDELTA)
            end = approval.end + timedelta(hours=TIMEDELTA)

            # Konvertiere naive Datumsobjekte zu UTC
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=utc)
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=utc)

            if start <= now and (end is None or end >= now) or not only_active:
                approved_usernames = ", ".join(sorted(u.username for u in approval.approved_users))
                approved_groupnames = ", ".join(sorted(g.name for g in approval.groups))

                active_approvals.append({
                    'approval_id': approval.id,
                    'application_id': approval.application_id,
                    'application_name': approval.application.name if approval.application else None,
                    'start': start.strftime("%-d.%-m.%Y - %H:%M"),
                    'end': end.strftime("%-d.%-m.%Y - %H:%M") if end else None,
                    'given_by': approval.given_by.username if approval.given_by else None,
                    'approved_users': approved_usernames,
                    'approved_groups': approved_groupnames,
                })

        print(len(active_approvals))
        return active_approvals

    except Exception as e:
        print(f"Fehler beim Abrufen der aktiven Approvals: {e}")
        return []
    
def delete_approval_from_db(approval_id):
    return_value = f"Freigabe mit ID {approval_id} wurde erfolgreich aus der Datenbank gelöscht"
    return_status = True
    try:
        approval = Approval.query.get_or_404(approval_id)
        db.session.delete(approval)

        # Änderungen übernehmen
        db.session.commit()
    except Exception as e:
        return_value = f"Beim löschen der Freigaben mit ID {approval.id} ist ein Fehler aufgetreten: {e}"
        return_status = False

    print({"message": return_value, "status": return_status})
    return {"message": return_value, "status": return_status}

def get_approval_given_user(approval_id):
    approval = Approval.query.get_or_404(approval_id)
    if approval:
        return approval.given_by
    return None

def has_active_approval(user_uuid: str, url: str) -> bool:
    now = datetime.now(timezone.utc)

    # Lade den Nutzer inkl. Gruppen
    user = (
        db.session.query(User)
        .options(joinedload(User.groups))  # Gruppen des Users laden
        .filter_by(uuid=user_uuid)
        .first()
    )
    if not user:
        return False
    if user_has_permission('approvals.always_access', user_uuid):
        return True
    
    # Lade relevante Anwendungen mit passender URL
    apps = db.session.query(Applications).filter_by(url=url).all()
    if not apps:
        return False

    user_groups = set(user.groups)

    for app in apps:
        # Suche alle aktiven Approvals dieser Anwendung
        approvals = (
            db.session.query(Approval)
            .options(
                joinedload(Approval.approved_users),
                joinedload(Approval.groups)
            )
            .filter(Approval.application == app)
            .filter(Approval.start <= now)
            .filter((Approval.end == None) | (Approval.end >= now))
            .all()
        )

        for approval in approvals:
            # Direkter Nutzervergleich
            if user in approval.approved_users:
                return True

            # Gruppenzugehörigkeit prüfen
            if user_groups & set(approval.groups):  # Schnittmenge?
                return True

    return False