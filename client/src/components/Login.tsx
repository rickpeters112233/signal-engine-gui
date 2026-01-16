import { useAuth } from '../contexts/AuthContext'
import '../styles/animations.css'

const CornerBrackets = ({ color = '#666666' }: { color?: string }) => (
  <>
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '12px',
        height: '12px',
        borderTop: `2px solid ${color}`,
        borderLeft: `2px solid ${color}`,
      }}
    />
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: '12px',
        height: '12px',
        borderTop: `2px solid ${color}`,
        borderRight: `2px solid ${color}`,
      }}
    />
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        width: '12px',
        height: '12px',
        borderBottom: `2px solid ${color}`,
        borderLeft: `2px solid ${color}`,
      }}
    />
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        right: 0,
        width: '12px',
        height: '12px',
        borderBottom: `2px solid ${color}`,
        borderRight: `2px solid ${color}`,
      }}
    />
  </>
)

export default function Login() {
  const { connect, isLoading, error, clearError } = useAuth()

  const handleConnect = async () => {
    clearError()
    await connect()
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0a0a0a',
        backgroundImage:
          'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255, 255, 255, 0.02) 2px, rgba(255, 255, 255, 0.02) 4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        position: 'relative',
      }}
    >
      <div className="scanline" />

      <div
        style={{
          position: 'relative',
          border: '1px solid #666666',
          padding: '60px 50px',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          maxWidth: '480px',
          width: '100%',
          textAlign: 'center',
        }}
      >
        <CornerBrackets />

        {/* Logo/Header */}
        <div style={{ marginBottom: '40px' }}>
          <h1
            style={{
              margin: 0,
              fontSize: '2.5em',
              letterSpacing: '6px',
              textTransform: 'uppercase',
              color: '#00FF88',
              fontWeight: 'normal',
            }}
          >
            [ GESTALT ]
          </h1>
          <div
            style={{
              color: '#666666',
              fontSize: '0.85em',
              marginTop: '12px',
              letterSpacing: '3px',
              textTransform: 'uppercase',
            }}
          >
            Tactical Market Intelligence System
          </div>
        </div>

        {/* Divider */}
        <div
          style={{
            height: '1px',
            backgroundColor: '#333333',
            margin: '30px 0',
          }}
        />

        {/* Auth Section */}
        <div style={{ marginBottom: '30px' }}>
          <div
            style={{
              color: '#888888',
              fontSize: '0.9em',
              marginBottom: '25px',
              letterSpacing: '1px',
            }}
          >
            AUTHENTICATION REQUIRED
          </div>

          {/* Error Message */}
          {error && (
            <div
              style={{
                position: 'relative',
                border: '1px solid #FF4444',
                padding: '15px',
                marginBottom: '25px',
                backgroundColor: 'rgba(255, 68, 68, 0.1)',
              }}
            >
              <CornerBrackets color="#FF4444" />
              <div style={{ color: '#FF4444', fontSize: '0.9em' }}>{error}</div>
            </div>
          )}

          {/* Connect Button */}
          <button
            onClick={handleConnect}
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '18px 30px',
              backgroundColor: isLoading ? 'rgba(0, 255, 136, 0.1)' : 'rgba(0, 255, 136, 0.15)',
              border: '2px solid #00FF88',
              color: '#00FF88',
              fontSize: '1em',
              letterSpacing: '3px',
              textTransform: 'uppercase',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              position: 'relative',
              fontFamily: 'inherit',
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.currentTarget.style.backgroundColor = 'rgba(0, 255, 136, 0.25)'
                e.currentTarget.style.boxShadow = '0 0 20px rgba(0, 255, 136, 0.3)'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isLoading
                ? 'rgba(0, 255, 136, 0.1)'
                : 'rgba(0, 255, 136, 0.15)'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <CornerBrackets color="#00FF88" />
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
                <span className="status-pulse" style={{ color: '#00FF88' }}>
                  {String.fromCharCode(9679)}
                </span>
                CONNECTING...
              </span>
            ) : (
              'CONNECT WALLET'
            )}
          </button>
        </div>

        {/* MetaMask Info */}
        <div
          style={{
            color: '#555555',
            fontSize: '0.75em',
            letterSpacing: '1px',
          }}
        >
          <div style={{ marginBottom: '8px' }}>
            SIGNATURE VERIFICATION VIA METAMASK
          </div>
          <div style={{ color: '#444444' }}>
            Only whitelisted addresses may access this system
          </div>
        </div>
      </div>

      {/* Version/Footer */}
      <div
        style={{
          position: 'absolute',
          bottom: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          color: '#333333',
          fontSize: '0.7em',
          letterSpacing: '2px',
        }}
      >
        INTERNAL USE ONLY
      </div>
    </div>
  )
}
