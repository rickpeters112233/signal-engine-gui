import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { ethers } from 'ethers'

// Dynamically determine Auth API URL based on current location
const getAuthApiURL = () => {
  const protocol = window.location.protocol
  const host = window.location.host
  // In development, connect directly to localhost:8766
  // In production, connect through nginx proxy
  if (host.includes('localhost') || host.includes('127.0.0.1')) {
    return 'http://localhost:8766'
  }
  return `${protocol}//${host}`
}

const AUTH_API_URL = getAuthApiURL()
const STORAGE_KEY = 'gestalt_auth'

interface AuthState {
  isAuthenticated: boolean
  address: string | null
  isLoading: boolean
  error: string | null
}

interface AuthContextType extends AuthState {
  connect: () => Promise<void>
  disconnect: () => void
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface StoredAuth {
  address: string
  timestamp: number
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    address: null,
    isLoading: true,
    error: null,
  })

  // Check for existing session on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const parsed: StoredAuth = JSON.parse(stored)
        // Session expires after 24 hours
        const isExpired = Date.now() - parsed.timestamp > 24 * 60 * 60 * 1000
        if (!isExpired && parsed.address) {
          setState({
            isAuthenticated: true,
            address: parsed.address,
            isLoading: false,
            error: null,
          })
          return
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    }
    setState(prev => ({ ...prev, isLoading: false }))
  }, [])

  const connect = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }))

    try {
      // Check if MetaMask is installed
      if (!window.ethereum) {
        throw new Error('MetaMask is not installed. Please install MetaMask to continue.')
      }

      // Request account access
      const provider = new ethers.providers.Web3Provider(window.ethereum)
      const accounts = await provider.send('eth_requestAccounts', [])

      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts found. Please connect your wallet.')
      }

      const address = accounts[0].toLowerCase()
      const signer = provider.getSigner()

      // Step 1: Request challenge from server
      const challengeResponse = await fetch(`${AUTH_API_URL}/auth/challenge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address }),
      })

      if (!challengeResponse.ok) {
        const error = await challengeResponse.json()
        throw new Error(error.error || 'Failed to get challenge')
      }

      const { message } = await challengeResponse.json()

      // Step 2: Sign the message with MetaMask
      const signature = await signer.signMessage(message)

      // Step 3: Verify signature with server
      const verifyResponse = await fetch(`${AUTH_API_URL}/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address, signature }),
      })

      const verifyResult = await verifyResponse.json()

      if (!verifyResponse.ok || !verifyResult.authenticated) {
        throw new Error(verifyResult.error || 'Authentication failed')
      }

      // Store session
      const session: StoredAuth = {
        address: verifyResult.address,
        timestamp: Date.now(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session))

      setState({
        isAuthenticated: true,
        address: verifyResult.address,
        isLoading: false,
        error: null,
      })

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Authentication failed'
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }))
    }
  }, [])

  const disconnect = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setState({
      isAuthenticated: false,
      address: null,
      isLoading: false,
      error: null,
    })
  }, [])

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }))
  }, [])

  return (
    <AuthContext.Provider
      value={{
        ...state,
        connect,
        disconnect,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Extend Window interface for ethereum
declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>
      on: (event: string, callback: (...args: unknown[]) => void) => void
      removeListener: (event: string, callback: (...args: unknown[]) => void) => void
      isMetaMask?: boolean
    }
  }
}
