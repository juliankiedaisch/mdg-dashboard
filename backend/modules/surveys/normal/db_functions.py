"""
Normal DB functions — re-export from src for canonical import paths.

Usage:
    from modules.surveys.normal.db_functions import create_survey
"""
from modules.surveys.src.db_functions import (
    create_survey,
    update_survey,
    delete_survey,
    add_question,
    update_question,
    delete_question,
    submit_response,
    get_survey_results,
    edit_survey_full,
    share_template,
    clone_from_template,
    save_as_template,
    grant_edit_response,
    revoke_edit_response,
)

__all__ = [
    'create_survey', 'update_survey', 'delete_survey',
    'add_question', 'update_question', 'delete_question',
    'submit_response', 'get_survey_results',
    'edit_survey_full', 'share_template', 'clone_from_template',
    'save_as_template', 'grant_edit_response', 'revoke_edit_response',
]
