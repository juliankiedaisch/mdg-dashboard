import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../components/shared';

function Login() {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);

  useEffect(() => {
    // Check if there's an error parameter (from failed OAuth)
    const errorParam = searchParams.get('error');
    
    if (errorParam) {
      // Show error message instead of redirecting again
      setError('Authentication failed. Please try again.');
      return;
    }

    // Redirect to OAuth login
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';
    window.location.href = `${apiUrl}/api/login`;
  }, [searchParams]);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  return (
    <div className="modal-overlay" style={{ display: 'flex' }}>
      <div className="modal-content">
        <h2>MDG Dashboard</h2>
        {error ? (
          <>
            <p style={{ color: '#d32f2f', marginBottom: '1rem' }}>{error}</p>
            <Button
              variant="primary"
              onClick={() => window.location.href = `${apiUrl}/api/login`}
            >
              Try Again
            </Button>
          </>
        ) : (
          <>
            <p>Redirecting to login...</p>
            <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#666' }}>
              If you are not redirected automatically, please{' '}
              <a href={`${apiUrl}/api/login`}>click here</a>.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default Login;
