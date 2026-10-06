import { Navigate, Outlet, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { RequireRole } from './components/RequireRole'
import { CandidateCabinet } from './pages/CandidateCabinet'
import { CandidateProfile } from './pages/CandidateProfile'
import { CompanyProfile } from './pages/CompanyProfile'
import { EmployerCabinet } from './pages/EmployerCabinet'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { NeedForm } from './pages/NeedForm'
import { Register } from './pages/Register'
import { Selection } from './pages/Selection'
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
              <Outlet />
            </RequireRole>
          }
        >
          <Route index element={<CandidateCabinet />} />
          <Route path="profile" element={<CandidateProfile />} />
        </Route>
        <Route
          path="employer"
          element={
            <RequireRole role="employer">
              <Outlet />
            </RequireRole>
          }
        >
          <Route index element={<EmployerCabinet />} />
          <Route path="company" element={<CompanyProfile />} />
          <Route path="needs/new" element={<NeedForm />} />
          <Route path="needs/:id" element={<NeedForm />} />
          <Route path="selections/:id" element={<Selection />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
