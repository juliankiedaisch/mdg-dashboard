import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file from parent directory (project root) or current directory
  // In Docker build, .env is in current directory; in dev, it's in parent
  let env = loadEnv(mode, path.resolve(__dirname, '..'), '')
  
  // If no env vars found, try current directory (Docker build scenario)
  if (!env.BACKEND_HOST) {
    env = loadEnv(mode, __dirname, '')
  }
  
  const frontendHost = env.FRONTEND_HOST || 'localhost'
  const frontendPort = parseInt(env.FRONTEND_PORT || '3000')
  const backendHost = env.BACKEND_HOST || 'localhost'
  const backendPort = parseInt(env.BACKEND_PORT || '5000')
  const isProduction = env.PRODUCTION === 'True' || env.PRODUCTION === 'true'
  
  // Determine protocol based on PRODUCTION flag
  const protocol = isProduction ? 'https' : 'http'
  const apiUrl = isProduction
    ? `${protocol}://${backendHost}` 
    : (backendPort === 80 ? `${protocol}://${backendHost}` : `${protocol}://${backendHost}:${backendPort}`)
  
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',  // Bind to all interfaces to allow network access
      port: frontendPort,
      proxy: {
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/static': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/socket.io': {
          target: apiUrl,
          changeOrigin: true,
          ws: true,
        }
      }
    },
    // Make env variables available to the app (only VITE_ prefixed ones by default)
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl),
      'import.meta.env.VITE_SOCKET_URL': JSON.stringify(apiUrl)
    }
  }
})
