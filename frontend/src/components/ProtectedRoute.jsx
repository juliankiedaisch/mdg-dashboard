import { useLocation } from 'react-router-dom';

/**
 * ProtectedRoute - Wrapper component that protects routes from unauthenticated access
 * 
 * If the user is not authenticated, it:
 * 1. Stores the current URL (including query params and hash)
 * 2. Redirects to the backend OAuth login with the intended URL as a parameter
 * 
 * After successful authentication, the backend will redirect the user back to the original URL.
 * 
 * @param {Object} props - Component props
 * @param {boolean} props.isAuthenticated - Whether the user is authenticated
 * @param {boolean} props.isLoading - Whether authentication status is being checked
 * @param {React.ReactNode} props.children - The protected content to render if authenticated
 */
const ProtectedRoute = ({ isAuthenticated, isLoading, children }) => {
  const location = useLocation();

  if (isLoading) {
    return <div className="loading">Loading...</div>;
  }

  if (!isAuthenticated) {
    // Construct the full intended URL (path + search + hash)
    const intendedUrl = location.pathname + location.search + location.hash;
    
    // Don't redirect if we're already on the login page
    if (location.pathname === '/login') {
      return children;
    }
    
    // Build the OAuth login URL with the redirect parameter
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';
    const loginUrl = `${apiUrl}/api/login?redirect=${encodeURIComponent(intendedUrl)}`;
    
    // Redirect to backend OAuth login
    window.location.href = loginUrl;
    
    // Return null while redirecting
    return null;
  }

  // User is authenticated, render the protected content
  return children;
};

export default ProtectedRoute;
