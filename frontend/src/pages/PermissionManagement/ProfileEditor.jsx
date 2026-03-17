import { useState, useEffect, useRef } from 'react';
import api from '../../utils/api';
import { Modal, Button, Spinner, TextInput, SearchInput, CheckboxInput, SelectableList } from '../../components/shared';
import './PermissionManagement.css';

/**
 * ProfileEditor – two-panel permission picker
 * Left: module list with selection state indicators
 * Right: permissions for the active module
 */
function ProfileEditor({ profile, allPermissions: allPermissionsProp, onSave, onClose }) {
  const [name, setName] = useState(profile?.name || '');
  const [description, setDescription] = useState(profile?.description || '');
  const [selectedPermissions, setSelectedPermissions] = useState(
    new Set(profile?.permissions?.map(p => p.id) || [])
  );
  const [allPermissions, setAllPermissions] = useState(allPermissionsProp || {});
  const [loadingPerms, setLoadingPerms] = useState(false);
  const [activeModule, setActiveModule] = useState(null);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);

  // Baseline snapshot – tracks the last committed/loaded state for dirty detection
  const baselineRef = useRef({
    name: profile?.name || '',
    description: profile?.description || '',
    permissions: new Set(profile?.permissions?.map(p => p.id) || []),
  });

  // Sync prop → state when parent finishes loading
  useEffect(() => {
    if (Object.keys(allPermissionsProp || {}).length > 0) {
      setAllPermissions(allPermissionsProp);
    }
  }, [allPermissionsProp]);

  // Self-fetch if prop is empty
  useEffect(() => {
    if (Object.keys(allPermissions).length === 0) {
      setLoadingPerms(true);
      api.get('/api/permissions/all')
        .then(res => setAllPermissions(res.data.permissions || {}))
        .catch(console.error)
        .finally(() => setLoadingPerms(false));
    }
  }, []);

  // Auto-select first module once permissions are available
  useEffect(() => {
    if (!activeModule && Object.keys(allPermissions).length > 0) {
      setActiveModule(Object.keys(allPermissions)[0]);
    }
  }, [allPermissions]);

  // Reset state AND baseline when profile prop changes (e.g. after save returns fresh server data)
  useEffect(() => {
    const newName = profile?.name || '';
    const newDesc = profile?.description || '';
    const newPerms = new Set(profile?.permissions?.map(p => p.id) || []);
    if (profile) {
      setName(newName);
      setDescription(newDesc);
    }
    setSelectedPermissions(newPerms);
    // Advance the baseline so the button goes back to disabled until the next change
    baselineRef.current = { name: newName, description: newDesc, permissions: newPerms };
  }, [profile]);

  /* ── Helpers ── */
  const getModuleState = (moduleName) => {
    const perms = allPermissions[moduleName] || [];
    if (perms.length === 0) return 'none';
    const count = perms.filter(p => selectedPermissions.has(p.id)).length;
    if (count === 0) return 'none';
    if (count === perms.length) return 'full';
    return 'partial';
  };

  const togglePermission = (permId) => {
    setSelectedPermissions(prev => {
      const next = new Set(prev);
      next.has(permId) ? next.delete(permId) : next.add(permId);
      return next;
    });
  };

  const toggleActiveModule = () => {
    if (!activeModule) return;
    const perms = filteredPerms;
    const allSelected = perms.every(p => selectedPermissions.has(p.id));
    setSelectedPermissions(prev => {
      const next = new Set(prev);
      perms.forEach(p => allSelected ? next.delete(p.id) : next.add(p.id));
      return next;
    });
  };

  /* ── Dirty detection ── */
  const setsEqual = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
  const isDirty =
    name !== baselineRef.current.name ||
    description !== baselineRef.current.description ||
    !setsEqual(selectedPermissions, baselineRef.current.permissions);

  const handleSave = async () => {
    if (!name.trim() || !isDirty) return;
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        description: description.trim(),
        permissions: Array.from(selectedPermissions),
      });
    } finally {
      setSaving(false);
    }
  };

  /* ── Derived data ── */
  const lc = search.toLowerCase();

  // Modules visible in left panel (filtered by search)
  const visibleModules = Object.entries(allPermissions).filter(([mod, perms]) =>
    !search ||
    mod.toLowerCase().includes(lc) ||
    perms.some(p => p.id.toLowerCase().includes(lc) || p.description.toLowerCase().includes(lc))
  );

  // Permissions shown in right panel
  const filteredPerms = activeModule
    ? (allPermissions[activeModule] || []).filter(
        p => !search ||
          activeModule.toLowerCase().includes(lc) ||
          p.id.toLowerCase().includes(lc) ||
          p.description.toLowerCase().includes(lc)
      )
    : [];

  const activeMod = activeModule;
  const activeAllSelected = filteredPerms.length > 0 && filteredPerms.every(p => selectedPermissions.has(p.id));
  const activeSomeSelected = filteredPerms.some(p => selectedPermissions.has(p.id));

  const totalSelected = selectedPermissions.size;

  return (
    <Modal
      title={profile ? `Profil bearbeiten: ${profile.name}` : 'Neues Profil erstellen'}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSave} disabled={!name.trim() || !isDirty} loading={saving}>
            {profile ? 'Speichern' : 'Erstellen'}
          </Button>
        </>
      }
    >
      <div className="perm-editor">
        {/* ── Top fields ── */}
        <div className="perm-editor__fields">
          <div className="perm-editor__field">
            <TextInput
              id="pe-name"
              label="Name"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="z.B. Umfragen-Manager"
              autoFocus
            />
          </div>
          <div className="perm-editor__field">
            <TextInput
              id="pe-desc"
              label="Beschreibung"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Optionale Beschreibung"
            />
          </div>
        </div>

        {/* ── Two-panel permission picker ── */}
        <div className="perm-picker">
          {/* Header row */}
          <div className="perm-picker__header">
            <span className="perm-picker__title">
              Berechtigungen <span className="perm-picker__count">{totalSelected} ausgewählt</span>
            </span>
            <SearchInput
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Module oder Berechtigungen suchen…"
              ariaLabel="Berechtigungen suchen"
              className="perm-picker__search"
            />
          </div>

          {loadingPerms ? (
            <div className="perm-picker__loading"><Spinner /></div>
          ) : visibleModules.length === 0 ? (
            <p className="perm-empty">
              {Object.keys(allPermissions).length === 0
                ? 'Keine Berechtigungen registriert. Stellen Sie sicher, dass der Backend-Server gestartet und initialisiert wurde.'
                : 'Keine Berechtigungen gefunden.'}
            </p>
          ) : (
            <div className="perm-picker__body">
              {/* Left: module list */}
              <div className="perm-picker__modules">
                <SelectableList
                  items={visibleModules.map(([mod]) => {
                    const permsInMod = allPermissions[mod] || [];
                    const selCount = permsInMod.filter(p => selectedPermissions.has(p.id)).length;
                    return {
                      key: mod,
                      label: mod,
                      badge: `${selCount}/${permsInMod.length}`,
                      state: getModuleState(mod),
                    };
                  })}
                  activeKey={activeMod}
                  onSelect={setActiveModule}
                  ariaLabel="Module"
                  size="sm"
                  emptyMessage="Keine Module gefunden"
                />
              </div>

              {/* Right: permission list */}
              <div className="perm-picker__perms" role="group" aria-label={`Berechtigungen für ${activeMod}`}>
                {!activeMod ? (
                  <p className="perm-empty">Modul auswählen</p>
                ) : filteredPerms.length === 0 ? (
                  <p className="perm-empty">Keine Berechtigungen gefunden.</p>
                ) : (
                  <>
                    {/* Select-all row */}
                    <label className="perm-picker__select-all">
                      <CheckboxInput
                        checked={activeAllSelected}
                        indeterminate={activeSomeSelected && !activeAllSelected}
                        onChange={toggleActiveModule}
                      />
                      <span>Alle in <strong>{activeMod}</strong> auswählen</span>
                    </label>
                    <div className="perm-picker__perm-list">
                      {filteredPerms.map(perm => (
                        <label key={perm.id} className="perm-picker__perm-row">
                          <CheckboxInput
                            checked={selectedPermissions.has(perm.id)}
                            onChange={() => togglePermission(perm.id)}
                          />
                          <span className="perm-picker__perm-info">
                            <span className="perm-picker__perm-id">{perm.id}</span>
                            <span className="perm-picker__perm-desc">{perm.description}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

export default ProfileEditor;
