import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { NyanTrail } from './Nyan'

const ToastContext = createContext<(msg: string) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ msg: string; id: number } | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const show = useCallback((msg: string) => {
    // id가 바뀌면 같은 메시지여도 팝 애니메이션이 다시 돈다
    setToast((prev) => ({ msg, id: (prev?.id ?? 0) + 1 }))
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setToast(null), 2200)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className="toast" role="status" key={toast.id}>
          {toast.msg}
        </div>
      )}
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

const CONFETTI_COLORS = ['#ff0000', '#ff9900', '#ffff00', '#33ff00', '#0099ff', '#6633ff', '#ff99ff']

export function Celebration({ onClose }: { onClose: () => void }) {
  return (
    <div className="celebration" onClick={onClose} role="dialog" aria-label="숙제 완료">
      {Array.from({ length: 40 }, (_, i) => (
        <span
          key={i}
          className="confetti"
          style={{
            left: `${(i * 37) % 100}%`,
            background: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
            animationDuration: `${1.5 + ((i * 7) % 10) / 5}s`,
            animationDelay: `${((i * 13) % 10) / 10}s`,
          }}
        />
      ))}
      <div className="fly" style={{ top: '18%' }}>
        <NyanTrail segments={14} scale={3} />
      </div>
      <div className="fly" style={{ top: '72%', animationDelay: '1.2s' }}>
        <NyanTrail segments={10} scale={2} />
      </div>
      <h1>MISSION<br />COMPLETE!</h1>
      <p>이번 주 숙제 끝! 🎉<br />냥캣이 자랑스러워해요</p>
      <p className="muted">화면을 누르면 닫혀요</p>
    </div>
  )
}
