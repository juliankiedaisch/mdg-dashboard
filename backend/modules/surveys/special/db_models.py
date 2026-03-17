"""
Special Survey DB models — canonical re-export.

Usage:
    from modules.surveys.special.db_models import SpecialSurvey
"""
from modules.surveys.src.db_models import (
    SpecialSurvey,
    SpecialSurveyStudent,
    SpecialSurveyParent,
    SpecialSurveyClassTeacher,
    SpecialSurveyStudentWish,
    SpecialSurveyTeacherEvaluation,
)

__all__ = [
    'SpecialSurvey',
    'SpecialSurveyStudent',
    'SpecialSurveyParent',
    'SpecialSurveyClassTeacher',
    'SpecialSurveyStudentWish',
    'SpecialSurveyTeacherEvaluation',
]
