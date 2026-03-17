# Survey Module - Database Models
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


# ── Association Tables ──────────────────────────────────────────────

survey_group_association = db.Table(
    'survey_group_association',
    db.Column('survey_id', db.Integer, db.ForeignKey('survey.id', ondelete='CASCADE')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE'))
)

question_group_association = db.Table(
    'question_group_association',
    db.Column('question_id', db.Integer, db.ForeignKey('survey_question.id', ondelete='CASCADE')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE'))
)

# Sharing templates with groups
template_share_group = db.Table(
    'template_share_group',
    db.Column('survey_id', db.Integer, db.ForeignKey('survey.id', ondelete='CASCADE')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE'))
)

# Sharing templates with individual users
template_share_user = db.Table(
    'template_share_user',
    db.Column('survey_id', db.Integer, db.ForeignKey('survey.id', ondelete='CASCADE')),
    db.Column('user_uuid', db.String, db.ForeignKey('user.uuid', ondelete='CASCADE'))
)


# ── Survey ──────────────────────────────────────────────────────────

class Survey(db.Model):
    """A survey created by a teacher/admin."""
    __tablename__ = 'survey'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    # Status: draft, active, closed, archived
    status = db.Column(db.String(20), nullable=False, default='draft')
    # Whether responses are anonymous
    anonymous = db.Column(db.Boolean, default=False)
    # Template flag – templates only hold questions, no group/time assignments
    is_template = db.Column(db.Boolean, default=False)
    # Template type: 'normal' for standard survey templates, 'teacher_evaluation'
    # for special survey teacher evaluation templates. Only meaningful when is_template=True.
    template_type = db.Column(db.String(30), nullable=False, default='normal')
    # Whether participants can edit their responses while the survey is active
    allow_edit_response = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    # Optional start/end for timed surveys
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=True)

    # Creator (FK to User)
    creator_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)
    creator = db.relationship('User', foreign_keys=[creator_uuid], backref=db.backref('created_surveys', lazy='dynamic'))

    # Groups that participate in this survey (M:N)
    groups = db.relationship(
        'Group',
        secondary=survey_group_association,
        backref=db.backref('surveys', lazy='dynamic')
    )

    # Template sharing: groups & individual users
    shared_with_groups = db.relationship(
        'Group',
        secondary=template_share_group,
        backref=db.backref('shared_templates', lazy='dynamic')
    )
    shared_with_users = db.relationship(
        'User',
        secondary=template_share_user,
        backref=db.backref('shared_templates', lazy='dynamic')
    )

    # Children
    questions = db.relationship('SurveyQuestion', back_populates='survey',
                                cascade='all, delete-orphan', order_by='SurveyQuestion.order')
    responses = db.relationship('SurveyResponse', back_populates='survey',
                                cascade='all, delete-orphan')

    def to_dict(self, include_questions=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'anonymous': self.anonymous,
            'is_template': self.is_template,
            'template_type': self.template_type,
            'allow_edit_response': self.allow_edit_response,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
            'starts_at': utc_isoformat(self.starts_at),
            'ends_at': utc_isoformat(self.ends_at),
            'creator_uuid': self.creator_uuid,
            'creator_name': self.creator.username if self.creator else None,
            'groups': [{'id': g.id, 'name': g.name} for g in self.groups],
            'response_count': len(self.responses),
            'shared_with_groups': [{'id': g.id, 'name': g.name} for g in self.shared_with_groups],
            'shared_with_users': [{'uuid': u.uuid, 'username': u.username} for u in self.shared_with_users],
            'is_deleted': self.is_deleted,
            'deleted_at': utc_isoformat(self.deleted_at),
            'deleted_by': self.deleted_by,
        }
        if include_questions:
            data['questions'] = [q.to_dict() for q in self.questions]
        return data


# ── Survey Question ─────────────────────────────────────────────────

class SurveyQuestion(db.Model):
    """
    A single question inside a survey.

    Supported question types (extensible):
      - text          : Free-text answer
      - single_choice : Radio – pick one
      - multiple_choice: Checkbox – pick many
      - rating        : Numeric scale (1-N)
      - yes_no        : Boolean choice
    """
    __tablename__ = 'survey_question'

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id', ondelete='CASCADE'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # Question type – kept as a string so new types can be added without migrations
    question_type = db.Column(db.String(30), nullable=False, default='text')
    # Display order
    order = db.Column(db.Integer, nullable=False, default=0)
    # Whether the question is required
    required = db.Column(db.Boolean, default=True)

    # ── Group-specific question support ──
    # If no groups assigned → question is shown to ALL groups in the survey.
    # If groups assigned → question is only shown to those specific groups.
    groups = db.relationship(
        'Group',
        secondary=question_group_association,
        backref=db.backref('survey_questions', lazy='dynamic')
    )

    # Extra config stored as JSON string (e.g. rating min/max, placeholder text)
    config_json = db.Column(db.Text, default='{}')

    # Excel export configuration stored as JSON.
    # Used by teacher evaluation templates to define how answers map to Excel output.
    # Structure: {
    #   "excel_output_type": "color_marker" | "option_text" | "custom_text_mapping",
    #   "color_mappings": { "<option_text>": "#RRGGBB", ... },
    #   "text_mappings": { "<option_text>": "Custom text", ... }
    # }
    excel_config_json = db.Column(db.Text, default='{}')

    survey = db.relationship('Survey', back_populates='questions')
    options = db.relationship('SurveyQuestionOption', back_populates='question',
                              cascade='all, delete-orphan', order_by='SurveyQuestionOption.order')
    answers = db.relationship('SurveyAnswer', back_populates='question',
                              cascade='all, delete-orphan')

    ALLOWED_TYPES = ['text', 'single_choice', 'multiple_choice', 'rating', 'yes_no']

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'question_type': self.question_type,
            'order': self.order,
            'required': self.required,
            'group_ids': [g.id for g in self.groups],
            'groups': [{'id': g.id, 'name': g.name} for g in self.groups],
            'config_json': self.config_json,
            'excel_config_json': self.excel_config_json,
            'options': [o.to_dict() for o in self.options],
        }


# ── Survey Question Option ──────────────────────────────────────────

class SurveyQuestionOption(db.Model):
    """An option for single_choice / multiple_choice questions."""
    __tablename__ = 'survey_question_option'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('survey_question.id', ondelete='CASCADE'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)

    question = db.relationship('SurveyQuestion', back_populates='options')

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'order': self.order,
        }


# ── Survey Response ──────────────────────────────────────────────────

class SurveyResponse(db.Model):
    """One user's complete response to a survey (container for answers)."""
    __tablename__ = 'survey_response'

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id', ondelete='CASCADE'), nullable=False)
    user_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # Per-user one-time edit grant (set by survey maintainer, reset after re-submission)
    edit_granted = db.Column(db.Boolean, default=False)

    survey = db.relationship('Survey', back_populates='responses')
    user = db.relationship('User', backref=db.backref('survey_responses', lazy='dynamic'))
    answers = db.relationship('SurveyAnswer', back_populates='response',
                              cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'survey_id': self.survey_id,
            'user_uuid': self.user_uuid,
            'submitted_at': utc_isoformat(self.submitted_at),
            'edit_granted': self.edit_granted,
            'answers': [a.to_dict() for a in self.answers],
        }


# ── Survey Answer ────────────────────────────────────────────────────

class SurveyAnswer(db.Model):
    """A single answer to a single question within a response."""
    __tablename__ = 'survey_answer'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('survey_question.id', ondelete='CASCADE'), nullable=False)

    # For text / rating answers
    answer_text = db.Column(db.Text, nullable=True)
    # For choice-based answers (stores selected option id)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('survey_question_option.id', ondelete='SET NULL'), nullable=True)
    # For multiple-choice: comma-separated option IDs (lightweight approach)
    selected_option_ids = db.Column(db.Text, nullable=True)

    response = db.relationship('SurveyResponse', back_populates='answers')
    question = db.relationship('SurveyQuestion', back_populates='answers')
    selected_option = db.relationship('SurveyQuestionOption', foreign_keys=[selected_option_id])

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'answer_text': self.answer_text,
            'selected_option_id': self.selected_option_id,
            'selected_option_ids': self.selected_option_ids,
        }


# ══════════════════════════════════════════════════════════════════════
#  SPECIAL SURVEY – New Class Composition (3-Phase Workflow)
# ══════════════════════════════════════════════════════════════════════

class SpecialSurvey(db.Model):
    """
    A special survey for forming new class compositions.
    After activation, all roles participate simultaneously:
    Students select wishes, Parents confirm, Teachers evaluate.
    Status: setup → active → completed → archived.
    Completed/archived surveys can be reactivated back to active.
    """
    __tablename__ = 'special_survey'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    creator_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)
    grade_level = db.Column(db.String(50), nullable=False)  # e.g. "5", "6a", etc.

    # 0 = setup, 1+ = active (kept for backward compat)
    current_phase = db.Column(db.Integer, nullable=False, default=0)
    # setup, active, completed, archived
    status = db.Column(db.String(20), nullable=False, default='setup')

    # Reference to a standard survey template used for teacher evaluation questions.
    # This allows configurable teacher questions without code changes.
    teacher_survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=True)

    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_uuid], backref=db.backref('created_special_surveys', lazy='dynamic'))
    teacher_survey = db.relationship('Survey', foreign_keys=[teacher_survey_id])
    students = db.relationship('SpecialSurveyStudent', back_populates='special_survey',
                               cascade='all, delete-orphan', order_by='SpecialSurveyStudent.class_name')
    parents = db.relationship('SpecialSurveyParent', back_populates='special_survey',
                              cascade='all, delete-orphan')
    class_teachers = db.relationship('SpecialSurveyClassTeacher', back_populates='special_survey',
                                     cascade='all, delete-orphan')
    wishes = db.relationship('SpecialSurveyStudentWish', back_populates='special_survey',
                             cascade='all, delete-orphan')
    evaluations = db.relationship('SpecialSurveyTeacherEvaluation', back_populates='special_survey',
                                  cascade='all, delete-orphan')

    def to_dict(self, include_details=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'creator_uuid': self.creator_uuid,
            'creator_name': self.creator.username if self.creator else None,
            'grade_level': self.grade_level,
            'current_phase': self.current_phase,
            'status': self.status,
            'teacher_survey_id': self.teacher_survey_id,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
            'is_deleted': self.is_deleted,
            'deleted_at': utc_isoformat(self.deleted_at),
            'deleted_by': self.deleted_by,
            'student_count': len(self.students),
            'parent_count': len(self.parents),
            'class_teacher_count': len(self.class_teachers),
        }
        if include_details:
            classes = {}
            for s in self.students:
                classes.setdefault(s.class_name, []).append(s.to_dict())
            data['classes'] = classes
            data['parents'] = [p.to_dict() for p in self.parents]
            data['class_teachers'] = [ct.to_dict() for ct in self.class_teachers]
            # Build teachers-per-class map
            teachers_by_class = {}
            for ct in self.class_teachers:
                teachers_by_class.setdefault(ct.class_name, []).append(ct.to_dict())
            data['teachers_by_class'] = teachers_by_class
            # Build wish summary
            wish_map = {}
            for w in self.wishes:
                wish_map[w.student_id] = w.to_dict()
            data['wishes'] = wish_map
            # Build evaluation summary
            eval_map = {}
            for e in self.evaluations:
                eval_map[e.student_id] = e.to_dict()
            data['evaluations'] = eval_map
        return data


class SpecialSurveyStudent(db.Model):
    """A student record imported from CSV for a special survey."""
    __tablename__ = 'special_survey_student'

    id = db.Column(db.Integer, primary_key=True)
    special_survey_id = db.Column(db.Integer, db.ForeignKey('special_survey.id', ondelete='CASCADE'), nullable=False)
    account = db.Column(db.String(255), nullable=False)  # username from CSV
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    class_name = db.Column(db.String(100), nullable=False)  # from Klasse/Information
    user_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=True)  # linked DB user if found

    special_survey = db.relationship('SpecialSurvey', back_populates='students')
    user = db.relationship('User', foreign_keys=[user_uuid])

    def to_dict(self):
        return {
            'id': self.id,
            'account': self.account,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'class_name': self.class_name,
            'user_uuid': self.user_uuid,
            'display_name': f"{self.first_name} {self.last_name}",
        }


class SpecialSurveyParent(db.Model):
    """A parent account imported from CSV for a special survey."""
    __tablename__ = 'special_survey_parent'

    id = db.Column(db.Integer, primary_key=True)
    special_survey_id = db.Column(db.Integer, db.ForeignKey('special_survey.id', ondelete='CASCADE'), nullable=False)
    account = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    user_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=True)

    special_survey = db.relationship('SpecialSurvey', back_populates='parents')
    user = db.relationship('User', foreign_keys=[user_uuid])

    def to_dict(self):
        return {
            'id': self.id,
            'account': self.account,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'user_uuid': self.user_uuid,
            'display_name': f"{self.first_name} {self.last_name}",
        }


class SpecialSurveyClassTeacher(db.Model):
    """Maps a teacher to a class within a special survey."""
    __tablename__ = 'special_survey_class_teacher'

    id = db.Column(db.Integer, primary_key=True)
    special_survey_id = db.Column(db.Integer, db.ForeignKey('special_survey.id', ondelete='CASCADE'), nullable=False)
    class_name = db.Column(db.String(100), nullable=False)
    teacher_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)

    special_survey = db.relationship('SpecialSurvey', back_populates='class_teachers')
    teacher = db.relationship('User', foreign_keys=[teacher_uuid])

    __table_args__ = (
        db.UniqueConstraint('special_survey_id', 'class_name', 'teacher_uuid', name='uq_special_class_teacher'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'class_name': self.class_name,
            'teacher_uuid': self.teacher_uuid,
            'teacher_name': self.teacher.username if self.teacher else None,
        }


class SpecialSurveyStudentWish(db.Model):
    """Stores a student's two wishes and selected parent (Phase 1 & 2)."""
    __tablename__ = 'special_survey_student_wish'

    id = db.Column(db.Integer, primary_key=True)
    special_survey_id = db.Column(db.Integer, db.ForeignKey('special_survey.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('special_survey_student.id', ondelete='CASCADE'), nullable=False)
    wish1_student_id = db.Column(db.Integer, db.ForeignKey('special_survey_student.id'), nullable=True)
    wish2_student_id = db.Column(db.Integer, db.ForeignKey('special_survey_student.id'), nullable=True)
    selected_parent_id = db.Column(db.Integer, db.ForeignKey('special_survey_parent.id'), nullable=True)
    parent_confirmed = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)  # locked once parent confirms

    special_survey = db.relationship('SpecialSurvey', back_populates='wishes')
    student = db.relationship('SpecialSurveyStudent', foreign_keys=[student_id],
                              backref=db.backref('wish', uselist=False))
    wish1_student = db.relationship('SpecialSurveyStudent', foreign_keys=[wish1_student_id])
    wish2_student = db.relationship('SpecialSurveyStudent', foreign_keys=[wish2_student_id])
    selected_parent = db.relationship('SpecialSurveyParent', foreign_keys=[selected_parent_id])

    __table_args__ = (
        db.UniqueConstraint('special_survey_id', 'student_id', name='uq_special_student_wish'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'wish1_student_id': self.wish1_student_id,
            'wish1_name': self.wish1_student.first_name + ' ' + self.wish1_student.last_name if self.wish1_student else None,
            'wish2_student_id': self.wish2_student_id,
            'wish2_name': self.wish2_student.first_name + ' ' + self.wish2_student.last_name if self.wish2_student else None,
            'selected_parent_id': self.selected_parent_id,
            'selected_parent_name': self.selected_parent.first_name + ' ' + self.selected_parent.last_name if self.selected_parent else None,
            'parent_confirmed': self.parent_confirmed,
            'locked': self.locked,
        }


class SpecialSurveyTeacherEvaluation(db.Model):
    """
    Teacher evaluation of a student (Phase 3).
    Links to a SurveyResponse from the teacher survey template for configurable questions.
    Also stores denormalized key fields for quick access / export.
    """
    __tablename__ = 'special_survey_teacher_evaluation'

    id = db.Column(db.Integer, primary_key=True)
    special_survey_id = db.Column(db.Integer, db.ForeignKey('special_survey.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('special_survey_student.id', ondelete='CASCADE'), nullable=False)
    teacher_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)

    # Denormalized fields for quick export (also stored in survey response)
    performance = db.Column(db.String(20), nullable=True)  # weak, normal, strong
    challenging_child = db.Column(db.Boolean, default=False)
    communication_intensive_parents = db.Column(db.Boolean, default=False)
    special_social_behavior = db.Column(db.Boolean, default=False)
    additional_notes = db.Column(db.Text, nullable=True)

    # Optional link to a standard survey response for the configurable template
    survey_response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id'), nullable=True)

    special_survey = db.relationship('SpecialSurvey', back_populates='evaluations')
    student = db.relationship('SpecialSurveyStudent', foreign_keys=[student_id])
    teacher = db.relationship('User', foreign_keys=[teacher_uuid])
    survey_response = db.relationship('SurveyResponse', foreign_keys=[survey_response_id])

    __table_args__ = (
        db.UniqueConstraint('special_survey_id', 'student_id', name='uq_special_teacher_eval'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'teacher_uuid': self.teacher_uuid,
            'teacher_name': self.teacher.username if self.teacher else None,
            'performance': self.performance,
            'challenging_child': self.challenging_child,
            'communication_intensive_parents': self.communication_intensive_parents,
            'special_social_behavior': self.special_social_behavior,
            'additional_notes': self.additional_notes,
            'survey_response_id': self.survey_response_id,
        }
