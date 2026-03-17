/**
 * Shared constants for the Survey module.
 * Single source of truth – imported by all survey components.
 */

export const QUESTION_TYPES = [
  { value: 'text', label: 'Freitext' },
  { value: 'single_choice', label: 'Einfachauswahl' },
  { value: 'multiple_choice', label: 'Mehrfachauswahl' },
  { value: 'rating', label: 'Bewertung (1-5)' },
  { value: 'yes_no', label: 'Ja / Nein' },
];

export const QUESTION_TYPE_LABELS = {
  text: 'Freitext',
  single_choice: 'Einfachauswahl',
  multiple_choice: 'Mehrfachauswahl',
  rating: 'Bewertung',
  yes_no: 'Ja/Nein',
};

export const STATUS_LABELS = {
  draft: 'Entwurf',
  active: 'Aktiv',
  closed: 'Geschlossen',
  archived: 'Archiviert',
  template: 'Vorlage',
};

export const STATUS_LABELS_SPECIAL = {
  setup: 'Einrichtung',
  active: 'Aktiv',
  completed: 'Abgeschlossen',
  archived: 'Archiviert',
  phase1: 'Aktiv',
  phase2: 'Aktiv',
  phase3: 'Aktiv',
};

/**
 * Template types – distinguishes normal survey templates from
 * teacher evaluation templates used in special surveys.
 */
export const TEMPLATE_TYPES = {
  normal: 'Umfragevorlage',
  teacher_evaluation: 'Bewertungsvorlage',
};

/**
 * Excel output types for per-question export configuration.
 * Used in teacher evaluation templates.
 */
export const EXCEL_OUTPUT_TYPES = [
  { value: 'option_text', label: 'Optionstext (Standard)' },
  { value: 'color_marker', label: 'Farbliche Markierung (Name)' },
  { value: 'custom_text_mapping', label: 'Benutzerdefinierter Text' },
];
