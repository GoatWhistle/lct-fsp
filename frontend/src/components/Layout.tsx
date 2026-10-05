import { Link, Outlet, useNavigate } from 'react-router'
import { useAuth } from '../auth/context'

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <>
      <header className="header">
        <Link to="/" className="logo">
          Подбор ФСП
        </Link>
        <nav className="nav">
          {user ? (
            <>
              <span className="muted">{user.email}</span>
              <button type="button" className="link-button" onClick={handleLogout}>
                Выйти
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Войти</Link>
              <Link to="/register" className="button button-small">
                Регистрация
              </Link>
            </>
          )}
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </>
  )
}
