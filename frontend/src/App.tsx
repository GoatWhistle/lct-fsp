import { Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { RequireRole } from './components/RequireRole'
import { CandidateCabinet } from './pages/CandidateCabinet'
import { EmployerCabinet } from './pages/EmployerCabinet'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { VerifyEmail } from './pages/VerifyEmail'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="register" element={<Register />} />
        <Route path="verify-email" element={<VerifyEmail />} />
        <Route path="login" element={<Login />} />
        <Route
          path="candidate"
          element={
            <RequireRole role="candidate">
              <CandidateCabinet />
            </RequireRole>
          }
        />
        <Route
          path="employer"
          element={
            <RequireRole role="employer">
              <EmployerCabinet />
            </RequireRole>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
