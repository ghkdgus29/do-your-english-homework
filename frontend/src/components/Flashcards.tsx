import { useState } from 'react'
import { api, type Card } from '../api'
import { NyanProgress } from './Nyan'
import { useToast } from './Feedback'

/** 앞: 한국어 뜻 / 뒤: 영어 표현+예문. 몰라요 누른 카드는 이번 세션 끝에 한 번 더. */
export function Flashcards({ cards, onFinish }: { cards: Card[]; onFinish?: () => void }) {
  const [queue, setQueue] = useState(cards)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(0)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const total = cards.length

  if (total === 0) return <p className="center muted">카드가 없어요</p>

  const card = queue[0]
  if (!card) {
    return (
      <div className="panel center stack">
        <h2>ALL CLEAR!</h2>
        <p>{total}장 다 넘겼어요 ✨</p>
        {onFinish && (
          <button className="btn yellow" onClick={onFinish}>
            처음으로
          </button>
        )}
      </div>
    )
  }

  const answer = async (known: boolean) => {
    if (busy) return
    setBusy(true)
    try {
      await api.post(`/api/cards/${encodeURIComponent(card.key)}/grade`, { known })
    } catch (e) {
      toast(`저장 실패: ${(e as Error).message}`)
    }
    setFlipped(false)
    setQueue(([head, ...rest]) => (known ? rest : [...rest, head]))
    if (known) setDone((d) => d + 1)
    setBusy(false)
  }

  return (
    <div>
      <NyanProgress value={done / total} />
      <p className="muted center" style={{ marginTop: 8 }}>
        {done} / {total} {card.is_new && '· NEW'}
      </p>
      <div className={`flashcard ${flipped ? 'flipped' : ''}`} onClick={() => setFlipped((f) => !f)}>
        <div className="flashcard-inner">
          <div className="face front">
            <span className="label">{card.set_title}</span>
            <div className="frosting">{card.meaning}</div>
            <p className="muted" style={{ color: '#555', marginBottom: 0 }}>
              눌러서 뒤집기
            </p>
          </div>
          <div className="face back">
            <span className="label">{card.week_title}</span>
            <div className="phrase">{card.phrase}</div>
            {card.example && <div className="example">{card.example}</div>}
          </div>
        </div>
      </div>
      {flipped ? (
        <div className="grade-row">
          <button className="btn red" disabled={busy} onClick={() => answer(false)}>
            몰라요
          </button>
          <button className="btn green" disabled={busy} onClick={() => answer(true)}>
            알아요
          </button>
        </div>
      ) : (
        <button className="btn block yellow" onClick={() => setFlipped(true)}>
          정답 보기
        </button>
      )}
    </div>
  )
}
