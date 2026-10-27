import { useEffect, useRef, useState } from 'react'
import { api, type Answer, type HomeworkStatus, type WeekDetail, type WordAnswer } from '../api'
import { Celebration, useToast } from './Feedback'
import { Recorder } from './Recorder'

const SECTION_DONE: Record<'words' | 'recording' | 'diary', string> = {
  words: '단어 클리어! ★',
  recording: '녹음 클리어! ★',
  diary: '다이어리 클리어! ★',
}

/** 입력이 멈추고 delay 후 저장 */
function useDebounced<T>(save: (v: T) => void, delay = 700) {
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (v: T) => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => save(v), delay)
  }
}

function PeekButton({ meaning, peeks, onPeek }: { meaning: string; peeks: number; onPeek: () => void }) {
  const [open, setOpen] = useState(false)
  const show = () => {
    if (!open) onPeek()
    setOpen(true)
  }
  const hide = () => setOpen(false)
  return (
    <button
      className="btn small blue peek"
      onPointerDown={show}
      onPointerUp={hide}
      onPointerLeave={hide}
      onPointerCancel={hide}
      onContextMenu={(e) => e.preventDefault()}
    >
      👀 꾹 눌러 뜻 보기{peeks > 0 && ` ×${peeks}`}
      {open && <span className="peek-bubble">{meaning}</span>}
    </button>
  )
}

function WordRow({
  index,
  word,
  hint,
  meaning,
  value,
  onChange,
  onPeek,
}: {
  index: number
  word: string
  hint: string
  meaning: string
  value: WordAnswer
  onChange: (idx: number, v: WordAnswer) => void
  onPeek: (idx: number) => void
}) {
  const [local, setLocal] = useState(value)
  const update = (patch: Partial<WordAnswer>) => {
    const next = { ...local, ...patch }
    setLocal(next)
    onChange(index, next)
  }
  return (
    <div className="word-block">
      <div className="word-head">
        <div>
          <span className="word">{word}</span>
          {hint && <span className="hint">({hint})</span>}
        </div>
        <PeekButton meaning={meaning} peeks={value.peeks ?? 0} onPeek={() => onPeek(index)} />
      </div>
      <div className="stack">
        <input
          placeholder="뜻"
          value={local.meaning}
          onChange={(e) => update({ meaning: e.target.value })}
          autoCapitalize="off"
        />
        <textarea
          placeholder={`"${word}"로 문장 만들기`}
          rows={2}
          value={local.sentence}
          onChange={(e) => update({ sentence: e.target.value })}
          autoCapitalize="sentences"
          spellCheck={false}
        />
      </div>
    </div>
  )
}

export function Homework({ week, memberName }: { week: WeekDetail; memberName: string }) {
  const [answer, setAnswer] = useState<Answer>(week.answer)
  const [diary, setDiary] = useState(week.answer.diary)
  const [celebrate, setCelebrate] = useState(false)
  const [saving, setSaving] = useState(false)
  const pendingWords = useRef<Record<string, WordAnswer>>({})
  const toast = useToast()
  const hw = week.content.homework
  const base = `/api/weeks/${week.id}`

  const prevStatus = useRef(week.answer.status)

  const apply = (next: Answer) => {
    const prev = prevStatus.current
    for (const k of ['words', 'recording', 'diary'] as const) {
      if (next.status[k] && !prev[k]) toast(SECTION_DONE[k])
    }
    if (next.status.completed && !prev.completed) setCelebrate(true)
    prevStatus.current = next.status
    setAnswer(next)
  }

  const call = async (fn: () => Promise<Answer>) => {
    setSaving(true)
    try {
      apply(await fn())
    } catch (e) {
      toast(`저장 실패: ${(e as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const flushWords = useDebounced<void>(() => {
    const words = pendingWords.current
    pendingWords.current = {}
    void call(() => api.put<Answer>(`${base}/answer`, { words }))
  })
  const saveDiary = useDebounced<string>((d) => void call(() => api.put<Answer>(`${base}/answer`, { diary: d })))

  const status: HomeworkStatus = answer.status
  const filled = hw.words.filter((_, i) => {
    const w = answer.words[String(i)]
    return w?.meaning?.trim() && w?.sentence?.trim()
  }).length

  return (
    <div>
      <p className="muted center">{hw.title}</p>

      <section className="panel">
        <div className="row spread">
          <h2>1. WORDS {status.words && '✓'}</h2>
          <span className="muted">
            {filled}/{hw.words.length}
          </span>
        </div>
        <p className="muted">뜻과 문장을 직접 써 보세요. 번역기 금지! 막히면 꾹 눌러 살짝만 보기.</p>
        {hw.words.map((w, i) => (
          <WordRow
            key={i}
            index={i}
            word={w.word}
            hint={w.hint}
            meaning={w.meaning}
            value={answer.words[String(i)] ?? { meaning: '', sentence: '' }}
            onChange={(idx, v) => {
              pendingWords.current[String(idx)] = { meaning: v.meaning, sentence: v.sentence }
              flushWords()
            }}
            onPeek={(idx) => void call(() => api.post<Answer>(`${base}/peek`, { index: idx }))}
          />
        ))}
      </section>

      <section className="panel">
        {hw.recording_type === 'answer' ? (
          <>
            <h2>2. ANSWER! {status.recording && '✓'}</h2>
            <p className="muted">질문에 영어로 대답하면서 녹음하세요. 대본 없이 말해 보기!</p>
            <ol className="script questions">
              {hw.questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </>
        ) : (
          <>
            <h2>2. READ ALOUD {status.recording && '✓'}</h2>
            <p className="muted">스크립트를 소리 내어 읽으면서 녹음하세요.</p>
            <p className="script">{hw.script}</p>
          </>
        )}
        <Recorder
          fileName={`${memberName}_${week.title}`.replace(/\s+/g, '_')}
          shared={answer.recording_shared}
          onShared={() => call(() => api.post<Answer>(`${base}/recording-shared`))}
        />
      </section>

      <section className="panel">
        <h2>3. DIARY {status.diary && '✓'}</h2>
        <p className="muted">자유롭게! 지난주에 한 일을 과거형으로 써 봐도 좋아요.</p>
        <textarea
          rows={8}
          value={diary}
          placeholder="Dear diary, ..."
          onChange={(e) => {
            setDiary(e.target.value)
            saveDiary(e.target.value)
          }}
          spellCheck={false}
        />
      </section>

      <p className="muted center">{saving ? '저장 중...' : '자동 저장돼요'}</p>
      {celebrate && <Celebration onClose={() => setCelebrate(false)} />}
    </div>
  )
}
