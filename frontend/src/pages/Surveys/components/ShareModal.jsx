import { useState, useEffect, useMemo } from 'react';
import api from '../../../utils/api';
import { Modal, Button, SearchInput, CheckboxInput } from '../../../components/shared';
import '../Surveys.css';

/**
 * ShareModal – lets the template owner share with groups and/or individual users.
 *
 * @param {Object}   survey  – the template survey object (with shared_with_groups, shared_with_users)
 * @param {Function} onClose – close callback
 * @param {Function} onSaved – saved callback
 */
const ShareModal = ({ survey, onClose, onSaved }) => {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState(
    new Set((survey.shared_with_groups || []).map((g) => g.id))
  );
  const [selectedUsers, setSelectedUsers] = useState(
    new Set((survey.shared_with_users || []).map((u) => u.uuid))
  );
  const [searchGroup, setSearchGroup] = useState('');
  const [searchUser, setSearchUser] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('groups');

  useEffect(() => {
    loadOptions();
  }, []);

  const loadOptions = async () => {
    try {
      const [gRes, uRes] = await Promise.all([
        api.get('/api/surveys/groups'),
        api.get('/api/surveys/users'),
      ]);
      setGroups(gRes.data.groups || []);
      setUsers(uRes.data.users || []);
    } catch (err) {
      console.error('Error loading share options:', err);
    }
  };

  const filteredGroups = useMemo(() => {
    const term = searchGroup.toLowerCase().trim();
    if (!term) return groups;
    return groups.filter((g) => g.name.toLowerCase().includes(term));
  }, [groups, searchGroup]);

  const filteredUsers = useMemo(() => {
    const term = searchUser.toLowerCase().trim();
    if (!term) return users;
    return users.filter((u) => u.username.toLowerCase().includes(term));
  }, [users, searchUser]);

  const toggleGroup = (id) => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleUser = (uuid) => {
    setSelectedUsers((prev) => {
      const next = new Set(prev);
      if (next.has(uuid)) next.delete(uuid);
      else next.add(uuid);
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await api.put(`/api/surveys/${survey.id}/share`, {
        group_ids: [...selectedGroups],
        user_uuids: [...selectedUsers],
      });
      onSaved();
    } catch (err) {
      console.error('Error saving share:', err);
      setError(err.response?.data?.message || 'Fehler beim Speichern der Freigabe.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`Vorlage teilen: ${survey.title}`}
      onClose={onClose}
      size="md"
      footer={
        <>
          {error && <span style={{ color: '#ef4444', marginRight: 'auto', fontSize: '0.9em' }}>{error}</span>}
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>
            Freigabe speichern
          </Button>
        </>
      }
    >
      {/* Sub-tabs for groups vs users */}
      <div className="share-modal__tabs">
        <Button
          variant="ghost"
          className={`survey-tab ${activeTab === 'groups' ? 'survey-tab--active' : ''}`}
          onClick={() => setActiveTab('groups')}
        >
          Gruppen ({selectedGroups.size})
        </Button>
        <Button
          variant="ghost"
          className={`survey-tab ${activeTab === 'users' ? 'survey-tab--active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          Benutzer ({selectedUsers.size})
        </Button>
      </div>

      {activeTab === 'groups' && (
        <>
          <div className="group-modal__search">
            <SearchInput
              placeholder="Gruppe suchen…"
              value={searchGroup}
              onChange={(e) => setSearchGroup(e.target.value)}
              autoFocus
            />
          </div>
          <div className="group-modal__list">
            {filteredGroups.length === 0 ? (
              <div className="group-modal__empty">Keine Gruppen gefunden</div>
            ) : (
              filteredGroups.map((g) => (
                <label
                  key={g.id}
                  className={`group-modal__item ${selectedGroups.has(g.id) ? 'group-modal__item--selected' : ''}`}
                >
                  <CheckboxInput
                    checked={selectedGroups.has(g.id)}
                    onChange={() => toggleGroup(g.id)}
                  />
                  <span className="group-modal__item-name">{g.name}</span>
                </label>
              ))
            )}
          </div>
        </>
      )}

      {activeTab === 'users' && (
        <>
          <div className="group-modal__search">
            <SearchInput
              placeholder="Benutzer suchen…"
              value={searchUser}
              onChange={(e) => setSearchUser(e.target.value)}
              autoFocus
            />
          </div>
          <div className="group-modal__list">
            {filteredUsers.length === 0 ? (
              <div className="group-modal__empty">Keine Benutzer gefunden</div>
            ) : (
              filteredUsers.map((u) => (
                <label
                  key={u.uuid}
                  className={`group-modal__item ${selectedUsers.has(u.uuid) ? 'group-modal__item--selected' : ''}`}
                >
                  <CheckboxInput
                    checked={selectedUsers.has(u.uuid)}
                    onChange={() => toggleUser(u.uuid)}
                  />
                  <span className="group-modal__item-name">{u.username}</span>
                </label>
              ))
            )}
          </div>
        </>
      )}
    </Modal>
  );
};

export default ShareModal;
