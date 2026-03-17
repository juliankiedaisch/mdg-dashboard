import { useState, useEffect } from 'react';
import api from '../../utils/api';
import { Card, Button, Spinner, SearchInput, SelectableList } from '../../components/shared';
import './PermissionManagement.css';

/**
 * ProfileAssignments - Assign profiles to users and groups
 */
function ProfileAssignments({ profiles, onUpdate, setMessage }) {
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [groupSearch, setGroupSearch] = useState('');
  const [allUsers, setAllUsers] = useState([]);
  const [allGroups, setAllGroups] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load users and groups when a profile is selected
  useEffect(() => {
    if (selectedProfile) {
      loadProfileDetails(selectedProfile.id);
    }
  }, [selectedProfile?.id]);

  // Search users
  useEffect(() => {
    const timer = setTimeout(() => {
      if (userSearch.length >= 1) {
        searchUsers(userSearch);
      } else {
        searchUsers('');
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [userSearch]);

  // Search groups
  useEffect(() => {
    const timer = setTimeout(() => {
      if (groupSearch.length >= 1) {
        searchGroups(groupSearch);
      } else {
        searchGroups('');
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [groupSearch]);

  const loadProfileDetails = async (profileId) => {
    try {
      setLoading(true);
      const res = await api.get(`/api/permissions/profiles/${profileId}`);
      const profile = res.data.profile;
      setUsers(profile.users || []);
      setGroups(profile.groups || []);
    } catch (error) {
      setMessage({ text: 'Fehler beim Laden der Profildetails', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const searchUsers = async (query) => {
    try {
      const res = await api.get(`/api/permissions/users?search=${encodeURIComponent(query)}`);
      setAllUsers(res.data.users || []);
    } catch (error) {
      console.error('Error searching users:', error);
    }
  };

  const searchGroups = async (query) => {
    try {
      const res = await api.get(`/api/permissions/groups?search=${encodeURIComponent(query)}`);
      setAllGroups(res.data.groups || []);
    } catch (error) {
      console.error('Error searching groups:', error);
    }
  };

  const handleAssignUsers = async (newUserIds) => {
    if (!selectedProfile) return;
    try {
      await api.post(`/api/permissions/profiles/${selectedProfile.id}/assign-users`, {
        user_ids: newUserIds
      });
      setMessage({ text: 'Benutzerzuweisungen aktualisiert', type: 'success' });
      loadProfileDetails(selectedProfile.id);
      onUpdate();
    } catch (error) {
      setMessage({ text: 'Fehler beim Zuweisen', type: 'error' });
    }
  };

  const handleAssignGroups = async (newGroupIds) => {
    if (!selectedProfile) return;
    try {
      await api.post(`/api/permissions/profiles/${selectedProfile.id}/assign-groups`, {
        group_ids: newGroupIds
      });
      setMessage({ text: 'Gruppenzuweisungen aktualisiert', type: 'success' });
      loadProfileDetails(selectedProfile.id);
      onUpdate();
    } catch (error) {
      setMessage({ text: 'Fehler beim Zuweisen', type: 'error' });
    }
  };

  const addUser = (user) => {
    if (users.find(u => u.id === user.id)) return;
    const newUsers = [...users, user];
    setUsers(newUsers);
    handleAssignUsers(newUsers.map(u => u.id));
  };

  const removeUser = (userId) => {
    const newUsers = users.filter(u => u.id !== userId);
    setUsers(newUsers);
    handleAssignUsers(newUsers.map(u => u.id));
  };

  const addGroup = (group) => {
    if (groups.find(g => g.id === group.id)) return;
    const newGroups = [...groups, group];
    setGroups(newGroups);
    handleAssignGroups(newGroups.map(g => g.id));
  };

  const removeGroup = (groupId) => {
    const newGroups = groups.filter(g => g.id !== groupId);
    setGroups(newGroups);
    handleAssignGroups(newGroups.map(g => g.id));
  };

  return (
    <div className="perm-assignments">
      <div className="perm-assignments__sidebar">
        <Card title="Profil auswählen">
          <div className="perm-assignments__profile-list">
            <SelectableList
              items={profiles.map(p => ({
                key: p.id,
                label: p.name,
                badge: `${p.permissions?.length || 0} Rechte`,
              }))}
              activeKey={selectedProfile?.id}
              onSelect={(key) => setSelectedProfile(profiles.find(p => p.id === key))}
              ariaLabel="Profile"
              size="sm"
              emptyMessage="Keine Profile vorhanden"
            />
          </div>
        </Card>
      </div>

      <div className="perm-assignments__content">
        {!selectedProfile ? (
          <Card>
            <p className="perm-empty">Wählen Sie ein Profil aus, um Zuweisungen zu verwalten.</p>
          </Card>
        ) : loading ? (
          <Spinner />
        ) : (
          <>
            <Card title={`Benutzer mit Profil "${selectedProfile.name}"`}>
              <div className="perm-assignments__search-section">
                <SearchInput
                  placeholder="Benutzer suchen..."
                  value={userSearch}
                  onChange={e => setUserSearch(e.target.value)}
                  className="perm-assignments__search"
                />
                {userSearch && allUsers.length > 0 && (
                  <div className="perm-assignments__dropdown">
                    {allUsers
                      .filter(u => !users.find(eu => eu.id === u.id))
                      .map(u => (
                        <Button
                          key={u.id}
                          variant="ghost"
                          className="perm-assignments__dropdown-item"
                          onClick={() => { addUser(u); setUserSearch(''); }}
                        >
                          {u.username}
                        </Button>
                      ))}
                  </div>
                )}
              </div>
              <div className="perm-assignments__tags">
                {users.map(u => (
                  <span key={u.id} className="perm-tag">
                    {u.username}
                    <Button variant="ghost" size="sm" className="perm-tag__remove" onClick={() => removeUser(u.id)}>×</Button>
                  </span>
                ))}
                {users.length === 0 && <span className="perm-empty-inline">Keine Benutzer zugewiesen</span>}
              </div>
            </Card>

            <Card title={`Gruppen mit Profil "${selectedProfile.name}"`}>
              <div className="perm-assignments__search-section">
                <SearchInput
                  placeholder="Gruppen suchen..."
                  value={groupSearch}
                  onChange={e => setGroupSearch(e.target.value)}
                  className="perm-assignments__search"
                />
                {groupSearch && allGroups.length > 0 && (
                  <div className="perm-assignments__dropdown">
                    {allGroups
                      .filter(g => !groups.find(eg => eg.id === g.id))
                      .map(g => (
                        <Button
                          key={g.id}
                          variant="ghost"
                          className="perm-assignments__dropdown-item"
                          onClick={() => { addGroup(g); setGroupSearch(''); }}
                        >
                          {g.name}
                        </Button>
                      ))}
                  </div>
                )}
              </div>
              <div className="perm-assignments__tags">
                {groups.map(g => (
                  <span key={g.id} className="perm-tag">
                    {g.name}
                    <Button variant="ghost" size="sm" className="perm-tag__remove" onClick={() => removeGroup(g.id)}>×</Button>
                  </span>
                ))}
                {groups.length === 0 && <span className="perm-empty-inline">Keine Gruppen zugewiesen</span>}
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

export default ProfileAssignments;
