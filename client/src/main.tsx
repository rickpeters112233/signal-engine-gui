import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import Login from './components/Login.tsx'
import { AuthProvider, useAuth } from './contexts/AuthContext.tsx'

function AuthenticatedApp() {
  const { isAuthenticated, isLoading } = useAuth()

  // Show loading state
  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#0a0a0a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#00FF88',
          fontSize: '1.2em',
          letterSpacing: '3px',
        }}
      >
        <span className="status-pulse">{String.fromCharCode(9679)}</span>
        <span style={{ marginLeft: '10px' }}>INITIALIZING...</span>
      </div>
    )
  }

  // Show login if not authenticated
  if (!isAuthenticated) {
    return <Login />
  }

  // Show main app
  return <App />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  </React.StrictMode>,
)
