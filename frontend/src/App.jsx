import { createContext, useContext, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import AdminDashboard from './pages/AdminDashboard'
import CustomerDetail from './pages/CustomerDetail'
import CustomerPortfolio from './pages/CustomerPortfolio'

export const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

function ProtectedRoute({ role, children }) {
  const { user, token } = useAuth()
  if (!token) return <Navigate to="/" replace />
  if (role && user?.role !== role) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/portfolio'} replace />
  }
  return children
}

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)

  function login(userData, tokenStr) {
    setUser(userData)
    setToken(tokenStr)
  }

  function logout() {
    setUser(null)
    setToken(null)
  }

  useEffect(() => {
    const handler = () => logout()
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

function LoginRedirect() {
  const { user, token } = useAuth()
  if (token) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/portfolio'} replace />
  }
  return <Login />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LoginRedirect />} />
          <Route path="/admin" element={
            <ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>
          } />
          <Route path="/admin/customer/:id" element={
            <ProtectedRoute role="admin"><CustomerDetail /></ProtectedRoute>
          } />
          <Route path="/portfolio" element={
            <ProtectedRoute role="customer"><CustomerPortfolio /></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
