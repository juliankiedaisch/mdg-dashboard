import React, { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import api from '../../utils/api';
import { Modal, Button, FormGroup, TextInput, Form } from '../../components/shared';
import AlertModal from './AlertModal';
import './Approvals.css';

const NewApprovalModal = ({ appId, onClose, onSuccess }) => {
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [maxTimeDifference, setMaxTimeDifference] = useState(0);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [groupSearch, setGroupSearch] = useState('');
  const [formData, setFormData] = useState({
    startDate: '',
    startTime: '',
    endDate: '',
    endTime: ''
  });
  const [loading, setLoading] = useState(false);
  const [alertMessage, setAlertMessage] = useState(null);

  useEffect(() => {
    // Request user and group data
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';
    const approvalsSocket = io(`${apiUrl}/approvals`, {
      withCredentials: true
    });

    approvalsSocket.emit('request_approval_infos');

    approvalsSocket.on('approval_infos', (data) => {
      setUsers(data.users || []);
      setGroups(data.groups || []);
      setMaxTimeDifference(parseInt(data.maxTimeDifference) || 0);
      initializeDefaultTimestamps();
    });

    return () => {
      approvalsSocket.disconnect();
    };
  }, []);

  const initializeDefaultTimestamps = () => {
    const now = new Date();
    const later = new Date(now.getTime() + 90 * 60 * 1000); // +90 minutes

    const pad = (n) => n.toString().padStart(2, '0');
    
    setFormData({
      startDate: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
      startTime: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
      endDate: `${later.getFullYear()}-${pad(later.getMonth() + 1)}-${pad(later.getDate())}`,
      endTime: `${pad(later.getHours())}:${pad(later.getMinutes())}`
    });
  };

  const addUser = (user) => {
    if (!selectedUsers.find(u => u.id === user.id)) {
      setSelectedUsers([...selectedUsers, user]);
      setUserSearch('');
    }
  };

  const removeUser = (userId) => {
    setSelectedUsers(selectedUsers.filter(u => u.id !== userId));
  };

  const addGroup = (group) => {
    if (!selectedGroups.find(g => g.id === group.id)) {
      setSelectedGroups([...selectedGroups, group]);
      setGroupSearch('');
    }
  };

  const removeGroup = (groupId) => {
    setSelectedGroups(selectedGroups.filter(g => g.id !== groupId));
  };

  const filteredUsers = users.filter(u => 
    u.name.toLowerCase().includes(userSearch.toLowerCase()) &&
    !selectedUsers.find(su => su.id === u.id)
  );

  const filteredGroups = groups.filter(g => 
    g.name.toLowerCase().includes(groupSearch.toLowerCase()) &&
    !selectedGroups.find(sg => sg.id === g.id)
  );

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (selectedUsers.length === 0 && selectedGroups.length === 0) {
      setAlertMessage('Bitte mindestens einen Benutzer oder eine Gruppe auswählen');
      return;
    }

    const start = new Date(`${formData.startDate}T${formData.startTime}`);
    const end = new Date(`${formData.endDate}T${formData.endTime}`);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      setAlertMessage('Ungültiges Datum oder Uhrzeit');
      return;
    }

    if (start >= end) {
      setAlertMessage('Der Startzeitpunkt muss vor dem Endzeitpunkt liegen');
      return;
    }

    const diffMs = end - start;
    const maxDiffMs = maxTimeDifference * 60 * 1000;

    if (diffMs > maxDiffMs) {
      setAlertMessage(`Der Zeitraum darf maximal ${maxTimeDifference / 60} Stunden betragen`);
      return;
    }

    const payload = {
      app_id: appId,
      user_ids: selectedUsers.map(u => u.id),
      group_ids: selectedGroups.map(g => g.id),
      start_time: start.toISOString(),
      end_time: end.toISOString()
    };

    try {
      setLoading(true);
      console.log('Submitting approval:', payload);
      const response = await api.post('/api/approvals/approvals', payload);
      console.log('Approval response:', response.data);
      
      if (response.data.status) {
        console.log('Approval created successfully');
        onSuccess();
      } else {
        console.error('Approval failed:', response.data.message);
        setAlertMessage(response.data.message);
        setLoading(false);
      }
    } catch (error) {
      console.error('Error creating approval:', error);
      console.error('Error response:', error.response?.data);
      setAlertMessage(error.response?.data?.message || 'Fehler beim Erstellen der Freigabe');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
    <Modal
      title="Neue Freigabe erstellen"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
          <Button loading={loading} onClick={handleSubmit}>
            {loading ? 'Speichere...' : 'Speichern'}
          </Button>
        </>
      }
    >
        <Form onSubmit={handleSubmit}>
          <FormGroup label="Gruppen hinzufügen:">
            <TextInput
              value={groupSearch}
              onChange={(e) => setGroupSearch(e.target.value)}
              placeholder="Gruppe eingeben..."
              disabled={loading}
              fullWidth
            />
            {groupSearch && filteredGroups.length > 0 && (
              <div className="suggestions-box">
                {filteredGroups.map(group => (
                  <div
                    key={group.id}
                    className="suggestion-item"
                    onClick={() => addGroup(group)}
                  >
                    {group.name}
                  </div>
                ))}
              </div>
            )}
            <div className="selected-items">
              {selectedGroups.map(group => (
                <div key={group.id} className="selected-item">
                  {group.name}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="btn-delete"
                    onClick={() => removeGroup(group.id)}
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          </FormGroup>

          <FormGroup label="Benutzer hinzufügen:">
            <TextInput
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              placeholder="Benutzer eingeben..."
              disabled={loading}
              fullWidth
            />
            {userSearch && filteredUsers.length > 0 && (
              <div className="suggestions-box">
                {filteredUsers.map(user => (
                  <div
                    key={user.id}
                    className="suggestion-item"
                    onClick={() => addUser(user)}
                  >
                    {user.name}
                  </div>
                ))}
              </div>
            )}
            <div className="selected-items">
              {selectedUsers.map(user => (
                <div key={user.id} className="selected-item">
                  {user.name}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="btn-delete"
                    onClick={() => removeUser(user.id)}
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          </FormGroup>

          <div className="form-row">
            <FormGroup label="Startdatum:" htmlFor="start-date">
              <TextInput
                type="date"
                id="start-date"
                value={formData.startDate}
                onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                required
                disabled={loading}
              />
            </FormGroup>
            <FormGroup label="Startzeit:" htmlFor="start-time">
              <TextInput
                type="time"
                id="start-time"
                value={formData.startTime}
                onChange={(e) => setFormData({ ...formData, startTime: e.target.value })}
                required
                disabled={loading}
              />
            </FormGroup>
          </div>

          <div className="form-row">
            <FormGroup label="Enddatum:" htmlFor="end-date">
              <TextInput
                type="date"
                id="end-date"
                value={formData.endDate}
                onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                required
                disabled={loading}
              />
            </FormGroup>
            <FormGroup label="Endzeit:" htmlFor="end-time">
              <TextInput
                type="time"
                id="end-time"
                value={formData.endTime}
                onChange={(e) => setFormData({ ...formData, endTime: e.target.value })}
                required
                disabled={loading}
              />
            </FormGroup>
          </div>
        </Form>
    </Modal>

      {alertMessage && (
        <AlertModal
          message={alertMessage}
          onClose={() => setAlertMessage(null)}
        />
      )}
    </>
  );
};

export default NewApprovalModal;
