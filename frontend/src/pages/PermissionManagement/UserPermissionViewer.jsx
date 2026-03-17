import { useState, useEffect } from 'react';
import api from '../../utils/api';
import { Card, Spinner, SearchInput, SelectableList } from '../../components/shared';
import './PermissionManagement.css';

/**
 * UserPermissionViewer - Inspect a user's effective permissions
 *
 * Two-panel layout:
 *   Left:  permissions overview for the selected user
 *   Right: user selection list (using shared SelectableList)
 */
function UserPermissionViewer({ setMessage }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetails, setUserDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [permFilter, setPermFilter] = useState('');

  // Load initial user list
  useEffect(() => {
    searchUsers('');
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      searchUsers(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const searchUsers = async (query) => {
    try {
      const res = await api.get(`/api/permissions/users?search=${encodeURIComponent(query)}`);
      setSearchResults(res.data.users || []);
    } catch (error) {
      console.error('Error searching users:', error);
    }
  };

  const selectUser = async (user) => {
    setSelectedUser(user);
    setLoading(true);
    try {
      const res = await api.get(`/api/permissions/user/${user.uuid}/details`);
      setUserDetails(res.data);
    } catch (error) {
      setMessage({ text: 'Fehler beim Laden der Benutzerberechtigungen', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const filteredPermissions = userDetails?.merged_permissions?.filter(
    p => !permFilter ||
         p.id.toLowerCase().includes(permFilter.toLowerCase()) ||
         p.description.toLowerCase().includes(permFilter.toLowerCase()) ||
         p.module.toLowerCase().includes(permFilter.toLowerCase())
  ) || [];

  // Group filtered permissions by module
  const groupedPermissions = filteredPermissions.reduce((acc, perm) => {
    if (!acc[perm.module]) acc[perm.module] = [];
    acc[perm.module].push(perm);
    return acc;
  }, {});

  // Filter users for SelectableList
  const userItems = searchResults.map(u => ({
    key: u.uuid || u.id,
    label: u.username,
    _user: u,
  }));

  return (
    <div className="perm-viewer">
      

      {/* Left: User selection list */}
      <div className="perm-viewer__sidebar">
        <Card title="Benutzer auswählen">
          <SearchInput
            placeholder="Benutzername suchen..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            size="md"
          />
          <div className="perm-viewer__user-list">
            <SelectableList
              items={userItems}
              activeKey={selectedUser?.uuid || selectedUser?.id}
              onSelect={(key) => {
                const user = searchResults.find(u => (u.uuid || u.id) === key);
                if (user) selectUser(user);
              }}
              ariaLabel="Benutzer"
              size="sm"
              emptyMessage={searchTerm ? 'Keine Benutzer gefunden.' : 'Benutzer werden geladen...'}
            />
          </div>
        </Card>
      </div>

      {/* Right: Permissions overview */}
      <div className="perm-viewer__main">
        {!selectedUser ? (
          <Card>
            <p className="perm-empty">Wählen Sie einen Benutzer aus, um dessen Berechtigungen anzuzeigen.</p>
          </Card>
        ) : loading ? (
          <Spinner />
        ) : userDetails && (
          <>
            <Card className="perm-viewer__user-info">
              <div className="perm-viewer__user-header">
                <h2>{userDetails.user.username}</h2>
                {userDetails.is_super_admin && (
                  <span className="perm-badge perm-badge--super">Super Admin</span>
                )}
              </div>
            </Card>

            {/* Profiles */}
            <Card title="Zugewiesene Profile">
              {userDetails.profiles.length === 0 && !userDetails.is_super_admin ? (
                <p className="perm-empty">Keine Profile zugewiesen.</p>
              ) : (
                <div className="perm-viewer__profiles">
                  {userDetails.is_super_admin && (
                    <div className="perm-viewer__profile-item perm-viewer__profile-item--super">
                      <strong>Super Admin</strong>
                      <span className="perm-viewer__profile-source">Alle Berechtigungen (System)</span>
                    </div>
                  )}
                  {userDetails.profiles.map((p, idx) => (
                    <div key={idx} className="perm-viewer__profile-item">
                      <strong>{p.name}</strong>
                      <span className="perm-viewer__profile-source">
                        {p.source === 'direct' ? 'Direkt zugewiesen' : `Über Gruppe: ${p.source.replace('group:', '')}`}
                      </span>
                      <span className="perm-viewer__profile-count">
                        {p.permissions.length} Berechtigung{p.permissions.length !== 1 ? 'en' : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Merged Permissions */}
            <Card title="Effektive Berechtigungen">
              <SearchInput
                placeholder="Berechtigungen filtern..."
                value={permFilter}
                onChange={e => setPermFilter(e.target.value)}
                size="sm"
              />
              {userDetails.is_super_admin ? (
                <p className="perm-viewer__super-note">
                  Super Admin hat automatisch alle Berechtigungen.
                </p>
              ) : Object.keys(groupedPermissions).length === 0 ? (
                <p className="perm-empty">Keine Berechtigungen gefunden.</p>
              ) : (
                <div className="perm-viewer__perm-list">
                  {Object.entries(groupedPermissions).map(([module, perms]) => (
                    <div key={module} className="perm-viewer__module-group">
                      <h4 className="perm-viewer__module-name">{module}</h4>
                      {perms.map(perm => (
                        <div key={perm.id} className="perm-viewer__perm-item">
                          <span className="perm-viewer__perm-check">✔</span>
                          <div className="perm-viewer__perm-info">
                            <span className="perm-viewer__perm-id">{perm.id}</span>
                            <span className="perm-viewer__perm-desc">{perm.description}</span>
                            <span className="perm-viewer__perm-source">
                              Durch: {perm.granted_by.join(', ')}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

export default UserPermissionViewer;
