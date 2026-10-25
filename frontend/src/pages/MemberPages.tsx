import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type Card, type Me, type WeekDetail, type WeekSummary } from '../api'
import { Flashcards } from '../components/Flashcards'
import { Homework } from '../components/Homework'
import { NyanCat, NyanTrail } from '../components/Nyan'

function Loading() {
  return (
    <div className="center" style={{ marginTop: 80 }}>
      <NyanTrail segments={4} scale={2} />
      <p className="spinner-text">LOADING...</p>
    </div>
  )
}

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setData(null)
    api.get<T>(path).then(setData, (e: Error) => setError(e.message))
  }, [path])
  return { data, error }
}

export function HomePage({ me }: { me: Me }) {
  const { data: weeks, error } = useLoad<WeekSummary[]>('/api/weeks')
  if (error) return <p className="error">{error}</p>
  if (!weeks) return <Loading />
  return (
    <div>
      <div className="center" style={{ margin: '24px 0 8px' }}>
        <NyanTrail segments={7} scale={3} />
        <h1 style={{ fontSize: 14, marginTop: 16 }}>DO YOUR ENGLISH HOMEWORK</h1>
        <p className="muted">{me.name}, 오늘도 한 칸만 하자 ✨</p>
      </div>
      {weeks.length === 0 && <p className="panel center">아직 올라온 수업이 없어요</p>}
      {weeks.map((w, i) => (
        <Link key={w.id} to={`/weeks/${w.id}`} className="panel week-card">
          <div className="row spread">
            <h3>{w.title}</h3>
            {i === 0 && <span className="badge">NEW</span>}
          </div>
          <p className="muted" style={{ margin: '6px 0 0' }}>
            {w.homework_title}
          </p>
          <div className="checks">
            <span className={`chip ${w.status.words ? 'done' : ''}`}>단어</span>
            <span className={`chip ${w.status.recording ? 'done' : ''}`}>녹음</span>
            <span className={`chip ${w.status.diary ? 'done' : ''}`}>다이어리</span>
            <span className="chip">카드 {w.card_count}</span>
            {w.status.completed && <span className="chip done">★ CLEAR</span>}
          </div>
        </Link>
      ))}
    </div>
  )
}

export function WeekPage({ me }: { me: Me }) {
  const { id } = useParams()
  const [tab, setTab] = useState<'homework' | 'cards'>('homework')
  const { data: week, error } = useLoad<WeekDetail>(`/api/weeks/${id}`)
  const [cards, setCards] = useState<Card[] | null>(null)
  const [round, setRound] = useState(0)

  useEffect(() => {
    if (tab === 'cards') api.get<Card[]>(`/api/cards?week_id=${id}`).then(setCards)
  }, [tab, id, round])

  if (error) return <p className="error">{error}</p>
  if (!week) return <Loading />
  return (
    <div>
      <div className="topbar">
        <Link to="/" className="logo">
          ◀ BACK
        </Link>
        <h1 style={{ fontSize: 12 }}>{week.title}</h1>
      </div>
      <div className="tabs">
        <button className={`btn ${tab === 'homework' ? 'active' : ''}`} onClick={() => setTab('homework')}>
          숙제
        </button>
        <button className={`btn ${tab === 'cards' ? 'active' : ''}`} onClick={() => setTab('cards')}>
          외우기
        </button>
      </div>
      {tab === 'homework' ? (
        <Homework week={week} memberName={me.name} />
      ) : cards ? (
        <Flashcards key={round} cards={cards} onFinish={() => setRound((r) => r + 1)} />
      ) : (
        <Loading />
      )}
    </div>
  )
}

export function ReviewPage() {
  const [round, setRound] = useState(0)
  const { data: cards, error } = useLoad<Card[]>(`/api/cards?round=${round}`)
  if (error) return <p className="error">{error}</p>
  if (!cards) return <Loading />
  return (
    <div>
      <div className="topbar">
        <h1 style={{ fontSize: 12 }}>REVIEW</h1>
        <span className="muted">오늘 복습할 카드 {cards.length}장</span>
      </div>
      {cards.length === 0 ? (
        <div className="panel center stack">
          <NyanCat scale={3} />
          <p>오늘 복습 끝! 내일 또 만나요</p>
        </div>
      ) : (
        <Flashcards key={round} cards={cards} onFinish={() => setRound((r) => r + 1)} />
      )}
    </div>
  )
}

export function JoinPage({ onJoined }: { onJoined: (me: Me) => void }) {
  const { token } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.post<Me>('/api/join', { token }).then(
      (me) => {
        onJoined(me)
        navigate('/', { replace: true })
      },
      (e: Error) => setError(e.message),
    )
  }, [token, navigate, onJoined])
  if (error) return <NoAccess message={error} />
  return <Loading />
}

export function NoAccess({ message }: { message?: string }) {
  return (
    <div className="center" style={{ marginTop: 80 }}>
      <NyanCat scale={4} />
      <h1 style={{ fontSize: 13, margin: '24px 0 12px' }}>WHO ARE YOU?</h1>
      <p>{message ?? '어드민에게 받은 개인 링크로 접속해 주세요'}</p>
    </div>
  )
}
