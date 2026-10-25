import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api, type Me } from './api'
import { Starfield } from './components/Nyan'
import { ToastProvider } from './components/Feedback'
import { AdminPage } from './pages/AdminPage'
import { HomePage, JoinPage, NoAccess, ReviewPage, WeekPage } from './pages/MemberPages'

function BottomNav() {
  const [due, setDue] = useState(0)
  const { pathname } = useLocation()
  useEffect(() => {
    api.get<{ count: number }>('/api/cards/due-count').then((r) => setDue(r.count), () => {})
  }, [pathname])
  return (
    <nav className="bottomnav">
      <NavLink to="/" end>
        HOME
      </NavLink>
      <NavLink to="/review">
        REVIEW{due > 0 && <span className="badge">{due}</span>}
      </NavLink>
    </nav>
  )
}

function MemberApp() {
  // undefined = 확인 중, null = 로그인 안 됨
  const [me, setMe] = useState<Me | null | undefined>(undefined)
  useEffect(() => {
    // /join이 먼저 끝났으면 늦게 온 401로 덮어쓰지 않는다
    api.get<Me>('/api/me').then(setMe, () => setMe((prev) => prev ?? null))
  }, [])
  const onJoined = useCallback((m: Me) => setMe(m), [])

  return (
    <Routes>
      <Route path="/join/:token" element={<JoinPage onJoined={onJoined} />} />
      <Route
        path="*"
        element={
          me === undefined ? null : me === null ? (
            <NoAccess />
          ) : (
            <>
              <Routes>
                <Route path="/" element={<HomePage me={me} />} />
                <Route path="/weeks/:id" element={<WeekPage me={me} />} />
                <Route path="/review" element={<ReviewPage />} />
                <Route path="*" element={<NoAccess message="없는 페이지예요" />} />
              </Routes>
              <BottomNav />
            </>
          )
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Starfield />
        <Routes>
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<MemberApp />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}
