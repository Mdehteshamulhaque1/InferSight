import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './providers/AuthContext'
import { Layout } from '../components/layout/Layout'
import { Alerts } from '../pages/Alerts'
import { Dashboard } from '../pages/Dashboard'
import { DatasetDetail } from '../pages/DatasetDetail'
import { Datasets } from '../pages/Datasets'
import { Insights } from '../pages/Insights'
import { Landing } from '../pages/Landing'
import { Login } from '../pages/Login'
import { Register } from '../pages/Register'

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="auth-page">
        <div className="empty"><span className="spinner" /></div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/app"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="datasets/:id" element={<DatasetDetail />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="insights" element={<Insights />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
