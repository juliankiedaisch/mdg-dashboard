import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../../utils/api';
import socketService from '../../utils/socket';
import { useUser } from '../../contexts/UserContext';
import { Button } from '../shared';
import './Layout.css';

function Layout({ children }) {
  const { user } = useUser();
  const [modules, setModules] = useState([]);
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [expandedModule, setExpandedModule] = useState(null);
  const [submenus, setSubmenus] = useState({});
  const [selectedSubmenuItem, setSelectedSubmenuItem] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  
  // Use ref to store current expandedModule for socket event handlers
  const expandedModuleRef = useRef(null);

  useEffect(() => {
    fetchModules();
    const socket = socketService.connect();

    socketService.on('module_message', (data) => {
      console.log('Module message received:', data);
      // Handle module messages
    });

    socketService.on('load_menu', () => {
      console.log('load_menu event received, reloading submenu...');
      // Reload submenu when load_menu event is received
      if (expandedModuleRef.current) {
        console.log('Reloading submenu for:', expandedModuleRef.current.name);
        loadSubmenu(expandedModuleRef.current);
      } else {
        console.log('No expanded module, skipping submenu reload');
      }
    });

    return () => {
      socketService.disconnect();
    };
  }, []);
  
  // Keep ref in sync with expandedModule state
  useEffect(() => {
    expandedModuleRef.current = expandedModule;
  }, [expandedModule]);

  const fetchModules = async () => {
    try {
      const response = await api.get('/api/modules');
      const fetchedModules = response.data.modules;
      setModules(fetchedModules);

      // Auto-expand the module matching the current URL and load its submenu
      const pathSegment = location.pathname.split('/')[1]; // e.g. "surveys" or "unify"
      if (pathSegment) {
        const matchedModule = fetchedModules.find((m) => m.name === pathSegment);
        if (matchedModule) {
          setExpandedModule(matchedModule);
          if (matchedModule.submenu_api && matchedModule.submenu_type === 'dynamic') {
            loadSubmenu(matchedModule);
          }
        }
      }
    } catch (error) {
      console.error('Failed to fetch modules:', error);
    }
  };

  const loadSubmenu = async (module) => {
    if (module.submenu_api && module.submenu_type === 'dynamic') {
      try {
        console.log(`Loading submenu from: ${module.submenu_api}`);
        const response = await api.get(module.submenu_api);
        console.log('Submenu response:', response.data);
        
        // Handle both array responses and object responses with groups property
        const submenuData = Array.isArray(response.data) ? response.data : (response.data.groups || []);
        
        setSubmenus(prev => ({
          ...prev,
          [module.name]: submenuData
        }));
        console.log(`Submenu loaded for ${module.name}:`, submenuData);
      } catch (error) {
        console.error(`Failed to fetch submenu for ${module.name}:`, error);
      }
    }
  };

  const toggleModule = async (module) => {
    if (expandedModule?.name === module.name) {
      // If already expanded, navigate to main module page (without selected item)
      setSelectedSubmenuItem(null);
      navigate(`/${module.name}`);
    } else {
      // Expand and load submenu
      setExpandedModule(module);
      setSelectedSubmenuItem(null);
      if (module.submenu_api) {
        await loadSubmenu(module);
      }
      navigate(`/${module.name}`);
    }
  };

  const loadSubmenuItem = (moduleName, item) => {
    // Track selected submenu item and navigate
    setSelectedSubmenuItem(item.id);
    // Use item's path if available, otherwise navigate with state
    if (item.path) {
      navigate(item.path);
    } else {
      navigate(`/${moduleName}`, { state: { selectedItem: item.id } });
    }
  };

  /**
   * Determine whether a submenu item is active based on the current URL.
   * Falls back to the manually-tracked selectedSubmenuItem for items without a path.
   */
  const isSubmenuItemActive = (item) => {
    if (item.path) {
      return location.pathname === item.path;
    }
    return selectedSubmenuItem === item.id;
  };

  const toggleMenu = () => {
    setIsCollapsed(!isCollapsed);
  };

  const handleLogout = async () => {
    try {
      await api.get('/api/logout');
      socketService.disconnect();
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout failed:', error);
      // Still redirect to login even if API call fails
      socketService.disconnect();
      window.location.href = '/login';
    }
  };

  return (
    <div className="container">
      <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`} id="sidebar">
        <Button variant="ghost" className="toggle-btn" onClick={toggleMenu}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M8.85719 3H15.1428C16.2266 2.99999 17.1007 2.99998 17.8086 3.05782C18.5375 3.11737 19.1777 3.24318 19.77 3.54497C20.7108 4.02433 21.4757 4.78924 21.955 5.73005C22.2568 6.32234 22.3826 6.96253 22.4422 7.69138C22.5 8.39925 22.5 9.27339 22.5 10.3572V13.6428C22.5 14.7266 22.5 15.6008 22.4422 16.3086C22.3826 17.0375 22.2568 17.6777 21.955 18.27C21.4757 19.2108 20.7108 19.9757 19.77 20.455C19.1777 20.7568 18.5375 20.8826 17.8086 20.9422C17.1008 21 16.2266 21 15.1428 21H8.85717C7.77339 21 6.89925 21 6.19138 20.9422C5.46253 20.8826 4.82234 20.7568 4.23005 20.455C3.28924 19.9757 2.52433 19.2108 2.04497 18.27C1.74318 17.6777 1.61737 17.0375 1.55782 16.3086C1.49998 15.6007 1.49999 14.7266 1.5 13.6428V10.3572C1.49999 9.27341 1.49998 8.39926 1.55782 7.69138C1.61737 6.96253 1.74318 6.32234 2.04497 5.73005C2.52433 4.78924 3.28924 4.02433 4.23005 3.54497C4.82234 3.24318 5.46253 3.11737 6.19138 3.05782C6.89926 2.99998 7.77341 2.99999 8.85719 3ZM6.35424 5.05118C5.74907 5.10062 5.40138 5.19279 5.13803 5.32698C4.57354 5.6146 4.1146 6.07354 3.82698 6.63803C3.69279 6.90138 3.60062 7.24907 3.55118 7.85424C3.50078 8.47108 3.5 9.26339 3.5 10.4V13.6C3.5 14.7366 3.50078 15.5289 3.55118 16.1458C3.60062 16.7509 3.69279 17.0986 3.82698 17.362C4.1146 17.9265 4.57354 18.3854 5.13803 18.673C5.40138 18.8072 5.74907 18.8994 6.35424 18.9488C6.97108 18.9992 7.76339 19 8.9 19H9.5V5H8.9C7.76339 5 6.97108 5.00078 6.35424 5.05118ZM11.5 5V19H15.1C16.2366 19 17.0289 18.9992 17.6458 18.9488C18.2509 18.8994 18.5986 18.8072 18.862 18.673C19.4265 18.3854 19.8854 17.9265 20.173 17.362C20.3072 17.0986 20.3994 16.7509 20.4488 16.1458C20.4992 15.5289 20.5 14.7366 20.5 13.6V10.4C20.5 9.26339 20.4992 8.47108 20.4488 7.85424C20.3994 7.24907 20.3072 6.90138 20.173 6.63803C19.8854 6.07354 19.4265 5.6146 18.862 5.32698C18.5986 5.19279 18.2509 5.10062 17.6458 5.05118C17.0289 5.00078 16.2366 5 15.1 5H11.5ZM5 8.5C5 7.94772 5.44772 7.5 6 7.5H7C7.55229 7.5 8 7.94772 8 8.5C8 9.05229 7.55229 9.5 7 9.5H6C5.44772 9.5 5 9.05229 5 8.5ZM5 12C5 11.4477 5.44772 11 6 11H7C7.55229 11 8 11.4477 8 12C8 12.5523 7.55229 13 7 13H6C5.44772 13 5 12.5523 5 12Z"
              fill="currentColor"
            />
          </svg>
        </Button>
        <div className="sidebar-menu">
          <ul>
            {modules.map((module, index) => (
              <li key={index}>
                <div 
                  className={`menu-item ${expandedModule?.name === module.name ? 'active' : ''}`}
                  onClick={() => toggleModule(module)}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" className="icon-inline">
                    <path d={module.icon} fill="currentColor" />
                  </svg>
                  <span>{module.label}</span>
                  {module.submenu_api && (
                    <svg 
                      width="16" 
                      height="16" 
                      viewBox="0 0 16 16" 
                      fill="currentColor" 
                      xmlns="http://www.w3.org/2000/svg"
                      className="submenu-toggle-icon"
                      style={{ 
                        marginLeft: 'auto',
                        transform: expandedModule?.name === module.name ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s'
                      }}
                    >
                      <path d="M8 11L3 6h10l-5 5z"/>
                    </svg>
                  )}
                </div>
                {/* Submenu items */}
                {expandedModule?.name === module.name && submenus[module.name] && (
                  <ul className="submenu">
                    {submenus[module.name].map((item) => (
                      <li key={item.id} className="submenu-item">
                        <div 
                          className={`submenu-link ${isSubmenuItemActive(item) ? 'active' : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            loadSubmenuItem(module.name, item);
                          }}
                        >
                          {item.name}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div className="user-info">
          <img src="/iserv-logo.png" alt="Logo" className="user-logo" />
          <p><b>{user?.username || 'Benutzer'}</b></p>
          <p><Button
            variant="ghost"
            className="logout-btn"
            onClick={handleLogout}
            title="Logout"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17 7L15.59 8.41L18.17 11H8V13H18.17L15.59 15.58L17 17L22 12L17 7ZM4 5H12V3H4C2.9 3 2 3.9 2 5V19C2 20.1 2.9 21 4 21H12V19H4V5Z" fill="currentColor"/>
            </svg>
          </Button></p>
        </div>
      </div>
      <div className="content" id="content">
        {children}
      </div>
      <div id="connection-lost-modal" className="modal-overlay" style={{ display: 'none' }}>
        <div className="modal-content">
          <p>Verbindung zum Server verloren. Bitte warten...</p>
        </div>
      </div>
    </div>
  );
}

export default Layout;
