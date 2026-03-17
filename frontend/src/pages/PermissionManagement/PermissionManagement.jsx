import { useState, useEffect } from 'react';
import api from '../../utils/api';
import { useUser } from '../../contexts/UserContext';
import PageContainer from '../../components/PageContainer/PageContainer';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import Spinner from '../../components/Spinner/Spinner';
import MessageBox from '../../components/MessageBox/MessageBox';
import Modal from '../../components/Modal/Modal';
import Tabs from '../../components/Tabs/Tabs';
import ProfileEditor from './ProfileEditor';
import ProfileAssignments from './ProfileAssignments';
import UserPermissionViewer from './UserPermissionViewer';
import './PermissionManagement.css';

function PermissionManagement() {
  const { hasPermission } = useUser();
  const [activeTab, setActiveTab] = useState('profiles');
  const [profiles, setProfiles] = useState([]);
  const [allPermissions, setAllPermissions] = useState({});
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [editingProfile, setEditingProfile] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const [profilesRes, permsRes] = await Promise.all([
        api.get('/api/permissions/profiles'),
        api.get('/api/permissions/all'),
      ]);
      setProfiles(profilesRes.data.profiles || []);
      setAllPermissions(permsRes.data.permissions || {});
    } catch (error) {
      console.error('Error loading permission data:', error);
      setMessage({ text: 'Fehler beim Laden der Berechtigungsdaten', type: 'error' });
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleCreateProfile = async (data) => {
    try {
      await api.post('/api/permissions/profiles', data);
      setMessage({ text: 'Profil erfolgreich erstellt', type: 'success' });
      setShowCreateModal(false);
      loadData(true);
    } catch (error) {
      setMessage({ text: error.response?.data?.error || 'Fehler beim Erstellen', type: 'error' });
    }
  };

  const handleUpdateProfile = async (profileId, data) => {
    try {
      const res = await api.put(`/api/permissions/profiles/${profileId}`, data);
      setMessage({ text: 'Profil erfolgreich aktualisiert', type: 'success' });
      // Keep modal open in edit mode with fresh data from the server
      setEditingProfile(res.data.profile);
      loadData(true);
    } catch (error) {
      setMessage({ text: error.response?.data?.error || 'Fehler beim Aktualisieren', type: 'error' });
    }
  };

  const handleDeleteProfile = async (profileId) => {
    try {
      await api.delete(`/api/permissions/profiles/${profileId}`);
      setMessage({ text: 'Profil gelöscht', type: 'success' });
      setDeleteTarget(null);
      loadData(true);
    } catch (error) {
      setMessage({ text: error.response?.data?.error || 'Fehler beim Löschen', type: 'error' });
      setDeleteTarget(null);
    }
  };

  if (!hasPermission('permissions.manage')) {
    return (
      <PageContainer>
        <Card variant="header" title="Berechtigungsverwaltung" />
        <MessageBox text="Sie haben keine Berechtigung, diese Seite zu sehen." type="error" />
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer>
        <Card variant="header" title="Berechtigungsverwaltung" />
        <Spinner />
      </PageContainer>
    );
  }

  const tabs = [
    { id: 'profiles', label: 'Profile' },
    { id: 'assignments', label: 'Zuweisungen' },
    { id: 'viewer', label: 'Benutzer-Berechtigungen' },
  ];

  return (
    <PageContainer>
      <Card variant="header" title="Berechtigungsverwaltung" />
      {message && <MessageBox text={message.text} type={message.type} onClose={() => setMessage(null)} />}

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'profiles' && (
        <div className="perm-section">
          <div className="perm-section__header">
            <h2>Profile verwalten</h2>
            <Button variant="primary" onClick={() => { setEditingProfile(null); setShowCreateModal(true); }}>
              Neues Profil
            </Button>
          </div>

          {profiles.length === 0 ? (
            <Card><p className="perm-empty">Keine Profile vorhanden. Erstellen Sie ein neues Profil.</p></Card>
          ) : (
            <div className="perm-profiles-grid">
              {profiles.map(profile => (
                <Card key={profile.id} className="perm-profile-card">
                  <div className="perm-profile-card__header">
                    <h3>{profile.name}</h3>
                    <div className="perm-profile-card__actions">
                      <Button variant="ghost" size="sm" onClick={() => { setEditingProfile(profile); setShowCreateModal(true); }}>
                        Bearbeiten
                      </Button>
                      <Button variant="danger" size="sm" onClick={() => setDeleteTarget(profile)}>
                        Löschen
                      </Button>
                    </div>
                  </div>
                  {profile.description && <p className="perm-profile-card__desc">{profile.description}</p>}
                  <div className="perm-profile-card__stats">
                    <span className="perm-stat">
                      <strong>{profile.permissions?.length || 0}</strong> Berechtigungen
                    </span>
                    <span className="perm-stat">
                      <strong>{profile.users?.length || 0}</strong> Benutzer
                    </span>
                    <span className="perm-stat">
                      <strong>{profile.groups?.length || 0}</strong> Gruppen
                    </span>
                  </div>
                  {profile.permissions && profile.permissions.length > 0 && (
                    <div className="perm-profile-card__perms">
                      {profile.permissions.map(p => (
                        <span key={p.id} className="perm-badge" title={p.description}>
                          {p.id}
                        </span>
                      ))}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}

          {deleteTarget && (
            <Modal
              title="Profil löschen"
              onClose={() => setDeleteTarget(null)}
              size="sm"
              footer={
                <>
                  <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Abbrechen</Button>
                  <Button variant="danger" onClick={() => handleDeleteProfile(deleteTarget.id)}>Löschen</Button>
                </>
              }
            >
              <p className="perm-delete-warning">
                Möchten Sie das Profil <strong>{deleteTarget.name}</strong> wirklich löschen?
                Alle Zuweisungen zu Benutzern und Gruppen werden entfernt.
              </p>
            </Modal>
          )}

          {showCreateModal && (
            <ProfileEditor
              profile={editingProfile}
              allPermissions={allPermissions}
              onSave={editingProfile
                ? (data) => handleUpdateProfile(editingProfile.id, data)
                : handleCreateProfile
              }
              onClose={() => { setShowCreateModal(false); setEditingProfile(null); }}
            />
          )}
        </div>
      )}

      {activeTab === 'assignments' && (
        <ProfileAssignments
          profiles={profiles}
          onUpdate={loadData}
          setMessage={setMessage}
        />
      )}

      {activeTab === 'viewer' && (
        <UserPermissionViewer setMessage={setMessage} />
      )}
    </PageContainer>
  );
}

export default PermissionManagement;
