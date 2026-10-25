import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type AdminMember, type AdminWeek } from '../api'
import { useToast } from '../components/Feedback'

function Login({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  return (
    <form
      className="panel stack"
      onSubmit={async (e) => {
        e.preventDefault()
        try {
          await api.post('/api/admin/login', { password })
          onLogin()
        } catch (err) {
          setError((err as Error).message)
        }
      }}
    >
      <h2>ADMIN LOGIN</h2>
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="비밀번호" />
      {error && <p className="error">{error}</p>}
      <button className="btn block">로그인</button>
    </form>
  )
}

function Upload({ onUploaded }: { onUploaded: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const submit = async () => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    setBusy(true)
    try {
      await api.post('/api/admin/weeks', form)
      setFiles([])
      toast('업로드 완료! 추출 시작')
      onUploaded()
    } catch (e) {
      toast((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel stack">
      <h2>NEW WEEK</h2>
      <p className="muted">수업 사진(외우기 자료 + 숙제지)을 한 번에 골라 주세요. Claude가 자동으로 분류·추출해요.</p>
      <input type="file" accept="image/*" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
      <button className="btn block yellow" disabled={busy || files.length === 0} onClick={submit}>
        {busy ? '업로드 중...' : `${files.length}장 올리기`}
      </button>
    </section>
  )
}

function WeekItem({ week, onChange }: { week: AdminWeek; onChange: () => void }) {
  const [editing, setEditing] = useState(false)
  const [json, setJson] = useState('')
  const toast = useToast()

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn()
      toast(ok)
      onChange()
    } catch (e) {
      toast((e as Error).message)
    }
  }

  return (
    <div className="panel stack">
      <div className="row spread">
        <h3 style={{ fontSize: 11 }}>
          #{week.id} {week.title}
        </h3>
        <span className={`status-${week.status}`}>{week.status}</span>
      </div>
      <div className="thumbs">
        {week.images.map((name) => (
          <a key={name} href={`/api/admin/weeks/${week.id}/images/${name}`} target="_blank" rel="noreferrer">
            <img src={`/api/admin/weeks/${week.id}/images/${name}`} alt={name} />
          </a>
        ))}
      </div>
      {week.error && <p className="error">{week.error}</p>}
      {week.status === 'processing' && <p className="spinner-text">CLAUDE IS READING...</p>}
      {week.content && (
        <p className="muted">
          세트 {week.content.study_sets.length}개 · 카드{' '}
          {week.content.study_sets.reduce((n, s) => n + s.items.length, 0)}장 · 단어{' '}
          {week.content.homework.words.length}개
        </p>
      )}
      {editing && (
        <>
          <textarea className="json-editor" value={json} onChange={(e) => setJson(e.target.value)} />
          <div className="row">
            <button
              className="btn small green"
              onClick={() => {
                let parsed: unknown
                try {
                  parsed = JSON.parse(json)
                } catch {
                  toast('JSON 문법 오류')
                  return
                }
                void act(() => api.put(`/api/admin/weeks/${week.id}/content`, parsed), '저장됨').then(() =>
                  setEditing(false),
                )
              }}
            >
              저장
            </button>
            <button className="btn small" onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </>
      )}
      {!editing && (
        <div className="row" style={{ flexWrap: 'wrap' }}>
          {week.status !== 'processing' && (
            <button
              className="btn small blue"
              onClick={() => act(() => api.post(`/api/admin/weeks/${week.id}/reextract`), '재추출 시작')}
            >
              재추출
            </button>
          )}
          {week.content && (
            <button
              className="btn small yellow"
              onClick={() => {
                setJson(JSON.stringify(week.content, null, 2))
                setEditing(true)
              }}
            >
              JSON 편집
            </button>
          )}
          <button
            className="btn small red"
            onClick={() =>
              confirm(`#${week.id} ${week.title}을(를) 삭제할까요? 멤버들의 답안·카드 기록도 지워져요.`) &&
              act(() => api.del(`/api/admin/weeks/${week.id}`), '삭제됨')
            }
          >
            삭제
          </button>
        </div>
      )}
    </div>
  )
}

function Members() {
  const [members, setMembers] = useState<AdminMember[]>([])
  const [name, setName] = useState('')
  const toast = useToast()
  const load = useCallback(() => api.get<AdminMember[]>('/api/admin/members').then(setMembers), [])
  useEffect(() => void load(), [load])

  const link = (m: AdminMember) => `${location.origin}/join/${m.token}`
  const copy = async (m: AdminMember) => {
    try {
      await navigator.clipboard.writeText(link(m))
      toast('링크 복사됨')
    } catch {
      toast('복사 실패 — 직접 길게 눌러 복사해 주세요')
    }
  }

  return (
    <section className="panel stack">
      <h2>MEMBERS</h2>
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!name.trim()) return
          await api.post('/api/admin/members', { name })
          setName('')
          void load()
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="이름" />
        <button className="btn small green">추가</button>
      </form>
      {members.map((m) => (
        <div key={m.id} className="stack" style={{ borderTop: '2px dashed #ffffff55', paddingTop: 10 }}>
          <div className="row spread">
            <strong>{m.name}</strong>
            <div className="row">
              <button className="btn small yellow" onClick={() => copy(m)}>
                링크 복사
              </button>
              <button
                className="btn small blue"
                onClick={async () => {
                  if (!confirm(`${m.name}의 링크를 새로 만들까요? 기존 링크와 로그인된 기기는 끊겨요.`)) return
                  await api.post(`/api/admin/members/${m.id}/regenerate`)
                  void load()
                }}
              >
                재발급
              </button>
              <button
                className="btn small red"
                onClick={async () => {
                  if (!confirm(`${m.name}을(를) 삭제할까요? 답안 기록도 지워져요.`)) return
                  await api.del(`/api/admin/members/${m.id}`)
                  void load()
                }}
              >
                ✕
              </button>
            </div>
          </div>
          <div className="link-box">{link(m)}</div>
        </div>
      ))}
    </section>
  )
}

export function AdminPage() {
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [weeks, setWeeks] = useState<AdminWeek[]>([])

  const load = useCallback(async () => {
    try {
      setWeeks(await api.get<AdminWeek[]>('/api/admin/weeks'))
      setAuthed(true)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setAuthed(false)
    }
  }, [])

  useEffect(() => void load(), [load])

  // 추출 중인 주차가 있으면 3초마다 갱신
  const processing = weeks.some((w) => w.status === 'processing')
  useEffect(() => {
    if (!processing) return
    const t = window.setInterval(load, 3000)
    return () => window.clearInterval(t)
  }, [processing, load])

  if (authed === null) return null
  if (!authed) return <Login onLogin={load} />

  return (
    <div>
      <div className="topbar">
        <a href="/" className="logo">
          ◀ HOME
        </a>
        <button
          className="btn small"
          onClick={async () => {
            await api.post('/api/admin/logout')
            setAuthed(false)
          }}
        >
          로그아웃
        </button>
      </div>
      <Upload onUploaded={load} />
      {weeks.map((w) => (
        <WeekItem key={w.id} week={w} onChange={load} />
      ))}
      <Members />
    </div>
  )
}
