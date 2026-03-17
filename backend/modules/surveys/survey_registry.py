"""
Survey Type Registry

A scalable pattern for managing multiple survey types.
Each survey type registers itself with metadata, permissions, and
management-check callables. Adding a new survey type requires only:
  1. Creating a new subfolder (e.g. surveys/newtype/)
  2. Implementing routes + DB logic in that folder
  3. Calling register_survey_type() with the type's config
  4. Adding the type's permission to MODULE_PERMISSIONS

No switch-case, no modifications to core survey logic.
"""

_SURVEY_TYPES = {}


def register_survey_type(type_key, config):
    """
    Register a survey type.

    config dict keys:
      - label (str): Human-readable name (e.g. "Normale Umfrage")
      - permission (str): Permission required to manage this type
      - register_routes (callable): function(blueprint, module_url, oauth) that registers routes
      - can_manage (callable): function() -> bool — checks if current user can manage this type
      - order (int): Display order in UI (lower = first)
    """
    _SURVEY_TYPES[type_key] = {
        'key': type_key,
        'label': config.get('label', type_key),
        'permission': config.get('permission', ''),
        'register_routes': config.get('register_routes'),
        'can_manage': config.get('can_manage'),
        'order': config.get('order', 100),
    }


def get_survey_type(type_key):
    """Get a registered survey type config by key."""
    return _SURVEY_TYPES.get(type_key)


def get_all_survey_types():
    """Get all registered survey types, sorted by order."""
    return sorted(_SURVEY_TYPES.values(), key=lambda t: t['order'])


def get_survey_type_keys():
    """Get all registered type keys."""
    return list(_SURVEY_TYPES.keys())


def can_manage_any_type():
    """Return True if the current user can manage at least one survey type."""
    from src.permissions import user_has_permission
    if user_has_permission("surveys.manage.all"):
        return True
    return any(
        t.get('can_manage', lambda: False)()
        for t in _SURVEY_TYPES.values()
    )
