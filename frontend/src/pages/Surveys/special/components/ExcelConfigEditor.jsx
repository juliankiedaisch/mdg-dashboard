import { useState, useEffect } from 'react';
import { FormGroup, SelectInput, TextInput, Button } from '../../../../components/shared';
import { EXCEL_OUTPUT_TYPES } from '../../surveyConstants';
import '../../Surveys.css';

/**
 * Per-question Excel export configuration editor.
 * Used in teacher evaluation templates to define how each question's
 * answer appears in the generated Excel export.
 *
 * Props:
 *  - config          : object (parsed excel_config_json)
 *  - onChange         : (newConfig) => void
 *  - questionType    : string (single_choice, yes_no, etc.)
 *  - options         : array of { text } — the question's options (for choice types)
 */
const ExcelConfigEditor = ({ config = {}, onChange, questionType, options = [] }) => {
  const outputType = config.excel_output_type || '';
  const colorMappings = config.color_mappings || {};
  const textMappings = config.text_mappings || {};

  // Determine which answer values to show in the mapping UI
  const getAnswerValues = () => {
    if (questionType === 'yes_no') {
      return ['Ja', 'Nein'];
    }
    if (['single_choice', 'multiple_choice'].includes(questionType)) {
      return options.filter((o) => o.text.trim()).map((o) => o.text.trim());
    }
    if (questionType === 'rating') {
      return ['1', '2', '3', '4', '5'];
    }
    return [];
  };

  const answerValues = getAnswerValues();
  const hasOptions = answerValues.length > 0;

  const updateOutputType = (newType) => {
    const newConfig = { ...config, excel_output_type: newType || undefined };
    // Clear irrelevant mappings when switching type
    if (newType !== 'color_marker') delete newConfig.color_mappings;
    if (newType !== 'custom_text_mapping') delete newConfig.text_mappings;
    // Initialize empty mappings
    if (newType === 'color_marker' && !newConfig.color_mappings) newConfig.color_mappings = {};
    if (newType === 'custom_text_mapping' && !newConfig.text_mappings) newConfig.text_mappings = {};
    onChange(newConfig);
  };

  const updateColorMapping = (answerText, color) => {
    const newMappings = { ...colorMappings, [answerText]: color };
    onChange({ ...config, color_mappings: newMappings });
  };

  const updateTextMapping = (answerText, text) => {
    const newMappings = { ...textMappings, [answerText]: text };
    onChange({ ...config, text_mappings: newMappings });
  };

  // Color presets for quick selection
  const COLOR_PRESETS = [
    { label: 'Grün', value: '#92D050' },
    { label: 'Gelb', value: '#FFC000' },
    { label: 'Orange', value: '#FF8C00' },
    { label: 'Rot', value: '#FF4444' },
    { label: 'Blau', value: '#5B9BD5' },
    { label: 'Grau', value: '#A6A6A6' },
  ];

  return (
    <div className="excel-config-editor">
      <div className="excel-config-editor__header">
        <span className="excel-config-editor__title">📊 Excel-Export Konfiguration</span>
      </div>

      <FormGroup label="Excel-Ausgabetyp">
        <SelectInput
          value={outputType}
          onChange={(e) => updateOutputType(e.target.value)}
          fullWidth
        >
          <option value="">Standard (Optionstext)</option>
          {EXCEL_OUTPUT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </SelectInput>
      </FormGroup>

      {/* Color Marker Configuration */}
      {outputType === 'color_marker' && hasOptions && (
        <div className="excel-config-editor__mappings">
          <p className="excel-config-editor__hint">
            Definieren Sie eine Farbe pro Antwortoption. Der Name des Schülers wird in der Excel-Datei
            entsprechend eingefärbt.
          </p>
          {answerValues.map((val) => (
            <div key={val} className="excel-config-editor__mapping-row">
              <span className="excel-config-editor__answer-label">{val}</span>
              <div className="excel-config-editor__color-picker">
                <input
                  type="color"
                  value={colorMappings[val] || '#FFFFFF'}
                  onChange={(e) => updateColorMapping(val, e.target.value)}
                  className="excel-config-editor__color-input"
                />
                <div className="excel-config-editor__color-presets">
                  {COLOR_PRESETS.map((preset) => (
                    <button
                      key={preset.value}
                      type="button"
                      className={`excel-config-editor__color-preset ${colorMappings[val] === preset.value ? 'excel-config-editor__color-preset--active' : ''}`}
                      style={{ backgroundColor: preset.value }}
                      onClick={() => updateColorMapping(val, preset.value)}
                      title={preset.label}
                    />
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Custom Text Mapping Configuration */}
      {outputType === 'custom_text_mapping' && hasOptions && (
        <div className="excel-config-editor__mappings">
          <p className="excel-config-editor__hint">
            Definieren Sie einen benutzerdefinierten Text pro Antwortoption, der in der
            Excel-Datei anstelle des Optionstexts angezeigt wird.
          </p>
          {answerValues.map((val) => (
            <div key={val} className="excel-config-editor__mapping-row">
              <span className="excel-config-editor__answer-label">{val}</span>
              <TextInput
                value={textMappings[val] || ''}
                onChange={(e) => updateTextMapping(val, e.target.value)}
                placeholder={`Text für "${val}"`}
                fullWidth
              />
            </div>
          ))}
        </div>
      )}

      {/* Info for text questions */}
      {outputType && !hasOptions && questionType === 'text' && (
        <p className="excel-config-editor__hint">
          Freitextfragen werden immer als Text in die Excel-Datei exportiert.
          Die Konfiguration ist nur für Auswahltypen relevant.
        </p>
      )}

      {/* Option text is the default – no additional config needed */}
      {outputType === 'option_text' && (
        <p className="excel-config-editor__hint">
          Die gewählte Option wird direkt als Text in die Excel-Zelle geschrieben.
        </p>
      )}
    </div>
  );
};

export default ExcelConfigEditor;
