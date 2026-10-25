import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useToast } from './Feedback'

function pickMimeType(): string | undefined {
  // iOS Safari는 mp4(aac), 안드로이드 크롬은 보통 webm(opus)만 된다
  for (const t of ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm']) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t
  }
  return undefined
}

function fmt(sec: number) {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

/** 녹음 → (webm이면 서버에서 m4a 변환) → 공유 시트로 카톡 전송. 녹음은 서버에 저장하지 않는다. */
export function Recorder({
  fileName,
  shared,
  onShared,
}: {
  fileName: string
  shared: boolean
  onShared: () => Promise<void>
}) {
  const [state, setState] = useState<'idle' | 'recording' | 'processing' | 'ready'>('idle')
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const toast = useToast()

  useEffect(
    () => () => {
      window.clearInterval(timer.current)
      recorder.current?.stream.getTracks().forEach((t) => t.stop())
    },
    [],
  )
  useEffect(() => () => void (url && URL.revokeObjectURL(url)), [url])

  const start = async () => {
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      toast('마이크 권한을 허용해 주세요')
      return
    }
    const mimeType = pickMimeType()
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      window.clearInterval(timer.current)
      setState('processing')
      let blob = new Blob(chunks, { type: rec.mimeType || mimeType || 'audio/webm' })
      if (!blob.type.includes('mp4')) {
        try {
          blob = await api.post<Blob>('/api/audio/convert', blob)
        } catch (e) {
          toast(`변환 실패: ${(e as Error).message}`)
          setState('idle')
          return
        }
      }
      setFile(new File([blob], `${fileName}.m4a`, { type: 'audio/mp4' }))
      setUrl(URL.createObjectURL(blob))
      setState('ready')
    }
    recorder.current = rec
    rec.start()
    setSeconds(0)
    timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    setState('recording')
  }

  const stop = () => recorder.current?.stop()

  const share = async () => {
    if (!file) return
    if (!navigator.canShare?.({ files: [file] })) {
      toast('이 브라우저는 파일 공유가 안 돼요. 다운로드해서 보내 주세요')
      return
    }
    try {
      await navigator.share({ files: [file], title: fileName })
      await onShared()
    } catch (e) {
      if ((e as Error).name !== 'AbortError') toast(`공유 실패: ${(e as Error).message}`)
    }
  }

  return (
    <div className="stack">
      {state === 'idle' && (
        <button className="btn block red" onClick={start}>
          ● 녹음 시작
        </button>
      )}
      {state === 'recording' && (
        <>
          <p className="center">
            <span className="rec-dot" />
            REC {fmt(seconds)}
          </p>
          <button className="btn block" onClick={stop}>
            ■ 녹음 끝
          </button>
        </>
      )}
      {state === 'processing' && <p className="center spinner-text">PROCESSING...</p>}
      {state === 'ready' && url && (
        <>
          <audio src={url} controls />
          <button className="btn block yellow" onClick={share}>
            💬 카톡으로 선생님께 보내기
          </button>
          <div className="row spread">
            <button className="btn small blue" onClick={() => setState('idle')}>
              다시 녹음
            </button>
            <a className="muted" href={url} download={`${fileName}.m4a`}>
              파일로 저장
            </a>
          </div>
        </>
      )}
      {shared && <p className="muted center">✅ 이번 주 녹음 보냈어요</p>}
    </div>
  )
}
