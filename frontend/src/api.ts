export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' }
  if (body instanceof FormData || body instanceof Blob) {
    init.body = body
  } else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await fetch(path, init)
  if (!res.ok) {
    let msg = res.statusText
    try {
      const data = await res.json()
      msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, msg)
  }
  if (res.headers.get('content-type')?.includes('application/json')) return res.json()
  return (await res.blob()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}

// ---- 타입 ----

export type StudyItem = { phrase: string; meaning: string; example: string }
export type StudySet = { title: string; items: StudyItem[] }
export type HomeworkWord = { word: string; hint: string; meaning: string }
export type WeekContent = {
  week_title: string
  study_sets: StudySet[]
  homework: { title: string; words: HomeworkWord[]; script: string }
}

export type HomeworkStatus = { words: boolean; recording: boolean; diary: boolean; completed: boolean }
export type WordAnswer = { meaning: string; sentence: string; peeks?: number }
export type Answer = {
  words: Record<string, WordAnswer>
  diary: string
  recording_shared: boolean
  status: HomeworkStatus
}

export type WeekSummary = {
  id: number
  title: string
  homework_title: string
  created_at: string
  card_count: number
  status: HomeworkStatus
}

export type WeekDetail = { id: number; title: string; content: WeekContent; answer: Answer }

export type Card = StudyItem & {
  key: string
  week_title: string
  set_title: string
  is_new: boolean
  reps: number
}

export type Me = { id: number; name: string }

export type AdminWeek = {
  id: number
  title: string
  status: 'processing' | 'ready' | 'failed'
  error: string | null
  images: string[]
  content: WeekContent | null
  created_at: string
}

export type AdminMember = { id: number; name: string; token: string; created_at: string }
