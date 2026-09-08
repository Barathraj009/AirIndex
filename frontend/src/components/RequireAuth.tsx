import { Navigate, useLocation } from 'react-router-dom'

export interface AuthCheckProps {
  children: React.ReactNode
}

export default function RequireAuth({ children }: AuthCheckProps) {
  const location = useLocation()
  const token = localStorage.getItem('airindex_access_token')
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}