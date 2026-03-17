import { createContext, useContext } from 'react';

/**
 * UserContext - Provides user authentication, role checking, and permission checking
 */

// Role constants matching backend globals.py OIDC_*_CLAIM values

const UserContext = createContext(null);

export const UserProvider = ({ children, user }) => {

  /**
   * Check if user has a specific granular permission.
   * Super Admin always returns true.
   * 
   * @param {string|string[]} permission - Permission ID(s) to check
   * @returns {boolean} True if user has the permission
   */
  const hasPermission = (permission) => {
    if (!user) return false;
    
    // Super Admin has all permissions
    if (user.is_super_admin) return true;
    
    if (!user.permissions) return false;
    
    if (typeof permission === 'string') {
      return user.permissions.includes(permission);
    }
    
    if (Array.isArray(permission)) {
      return permission.some(p => user.permissions.includes(p));
    }
    
    return false;
  };

  // Helper function to check if user is admin (legacy - prefer hasPermission)
  const isAdmin = () => user?.is_super_admin;

  const value = {
    user,
    hasPermission,
    isAdmin,
    permissions: user?.permissions || [],
    isSuperAdmin: user?.is_super_admin || false
  };

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
};

export const useUser = () => {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};

export default UserContext;
