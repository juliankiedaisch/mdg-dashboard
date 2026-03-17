import { useState } from 'react';
import api from '../../../utils/api';
import { Modal, Button, FormGroup, TextInput, SelectInput, CheckboxInput } from '../../../components/shared';
import GroupSelectModal from './GroupSelectModal';
import { QUESTION_TYPES } from '../surveyConstants';
import '../Surveys.css';

const NewQuestionModal = ({ surveyId, groups, onClose, onAdded, onAddLocal }) => {
  const [text, setText] = useState('');
  const [questionType, setQuestionType] = useState('text');
  const [required, setRequired] = useState(true);
  const [groupIds, setGroupIds] = useState([]);
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showGroupModal, setShowGroupModal] = useState(false);

  const handleTypeChange = (newType) => {
    setQuestionType(newType);
    if (['single_choice', 'multiple_choice'].includes(newType) && options.length === 0) {
      setOptions([{ text: '' }, { text: '' }]);
    }
    if (!['single_choice', 'multiple_choice'].includes(newType)) {
      setOptions([]);
    }
  };

  const addOption = () => setOptions([...options, { text: '' }]);

  const updateOption = (idx, value) => {
    const updated = [...options];
    updated[idx] = { text: value };
    setOptions(updated);
  };

  const removeOption = (idx) => setOptions(options.filter((_, i) => i !== idx));

  const handleSubmit = async () => {
    if (!text.trim()) {
      setError('Fragetext ist erforderlich.');
      return;
    }

    if (['single_choice', 'multiple_choice'].includes(questionType)) {
      const nonEmpty = options.filter((o) => o.text.trim());
      if (nonEmpty.length < 2) {
        setError('Mindestens 2 Optionen erforderlich.');
        return;
      }
    }

    setLoading(true);
    setError('');

    const questionData = {
      text: text.trim(),
      question_type: questionType,
      required,
      group_ids: groupIds,
      options: options
        .filter((o) => o.text.trim())
        .map((o, i) => ({ text: o.text.trim(), order: i })),
    };

    // Local mode: return data without API call
    if (onAddLocal) {
      onAddLocal(questionData);
      setLoading(false);
      return;
    }

    try {
      await api.post(`/api/surveys/${surveyId}/questions`, questionData);
      onAdded();
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Hinzufügen.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="Neue Frage hinzufügen"
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading}>Hinzufügen</Button>
        </>
      }
    >
      {error && <div style={{ color: '#ef4444', marginBottom: '12px' }}>{error}</div>}

      <FormGroup label="Fragetext" required>
        <TextInput
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Frage eingeben..."
          fullWidth
        />
      </FormGroup>

      <div className="survey-form-row">
        <FormGroup label="Typ">
          <SelectInput
            value={questionType}
            onChange={(e) => handleTypeChange(e.target.value)}
            fullWidth
          >
            {QUESTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </SelectInput>
        </FormGroup>

        <FormGroup label="Nur für Gruppen" hint="Leer = alle Gruppen">
          <div className="group-picker group-picker--compact">
            <Button variant="secondary" onClick={() => setShowGroupModal(true)}>
              Gruppen…
            </Button>
            {groupIds.length > 0 && (
              <div className="group-picker__tags">
                {groupIds.map((id) => {
                  const g = groups.find((gr) => gr.id === id);
                  return g ? <span key={id} className="group-picker__tag group-picker__tag--sm">{g.name}</span> : null;
                })}
              </div>
            )}
          </div>
        </FormGroup>
      </div>

      <FormGroup label="Pflichtfrage">
        <CheckboxInput
          label="Antwort erforderlich"
          checked={required}
          onChange={(e) => setRequired(e.target.checked)}
        />
      </FormGroup>

      {['single_choice', 'multiple_choice'].includes(questionType) && (
        <FormGroup label="Optionen">
          <div className="option-list">
            {options.map((opt, idx) => (
              <div key={idx} className="option-row">
                <TextInput
                  value={opt.text}
                  onChange={(e) => updateOption(idx, e.target.value)}
                  placeholder={`Option ${idx + 1}`}
                  fullWidth
                />
                <Button variant="danger" size="sm" onClick={() => removeOption(idx)}>✕</Button>
              </div>
            ))}
            <Button variant="ghost" size="sm" onClick={addOption}>+ Option</Button>
          </div>
        </FormGroup>
      )}

      {showGroupModal && (
        <GroupSelectModal
          groups={groups}
          selectedIds={groupIds}
          onConfirm={(ids) => { setGroupIds(ids); setShowGroupModal(false); }}
          onClose={() => setShowGroupModal(false)}
          title="Gruppen für Frage"
        />
      )}
    </Modal>
  );
};

export default NewQuestionModal;
