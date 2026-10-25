import type { CSSProperties } from 'react'

// 직접 찍은 팝타르트 고양이 픽셀아트 (32x18 그리드)
const W = 32
const H = 18
const COLORS: Record<string, string> = {
  k: '#000000',
  t: '#ffcc99',
  p: '#ff99ff',
  s: '#ff3399',
  g: '#999999',
  w: '#ffffff',
  r: '#ff9999',
}

function buildGrid(): string[][] {
  const grid = Array.from({ length: H }, () => Array<string>(W).fill(''))
  const fill = (x: number, y: number, w: number, h: number, c: string) => {
    for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) grid[j][i] = c
  }
  // 꼬리
  fill(0, 8, 6, 4, 'k')
  fill(1, 9, 5, 2, 'g')
  // 다리
  for (const x of [6, 10, 19, 24]) {
    fill(x, 13, 3, 4, 'k')
    fill(x + 1, 13, 1, 3, 'g')
  }
  // 빵 + 프로스팅
  fill(6, 0, 19, 15, 'k')
  fill(5, 1, 21, 13, 'k')
  fill(6, 1, 19, 13, 't')
  fill(8, 2, 15, 11, 'p')
  fill(7, 3, 17, 9, 'p')
  for (const [x, y] of [[9, 4], [13, 3], [17, 5], [11, 7], [15, 9], [20, 3], [9, 10], [19, 8], [13, 11]])
    fill(x, y, 1, 1, 's')
  // 머리
  fill(20, 3, 3, 3, 'k')
  fill(28, 3, 3, 3, 'k')
  fill(19, 6, 13, 9, 'k')
  fill(20, 5, 11, 11, 'k')
  fill(21, 4, 1, 2, 'g')
  fill(29, 4, 1, 2, 'g')
  fill(20, 6, 11, 9, 'g')
  fill(21, 5, 9, 10, 'g')
  // 눈, 코, 입, 볼
  fill(22, 8, 2, 2, 'k')
  fill(22, 8, 1, 1, 'w')
  fill(27, 8, 2, 2, 'k')
  fill(27, 8, 1, 1, 'w')
  fill(25, 10, 1, 1, 'k')
  fill(22, 12, 7, 1, 'k')
  fill(22, 11, 1, 1, 'k')
  fill(25, 11, 1, 1, 'k')
  fill(28, 11, 1, 1, 'k')
  fill(20, 10, 2, 2, 'r')
  fill(29, 10, 2, 2, 'r')
  return grid
}

const GRID = buildGrid()

export function NyanCat({ scale = 3, style }: { scale?: number; style?: CSSProperties }) {
  const rects = []
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const c = GRID[y][x]
      if (c) rects.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={COLORS[c]} />)
    }
  return (
    <svg
      className="nyan"
      width={W * scale}
      height={H * scale}
      viewBox={`0 0 ${W} ${H}`}
      shapeRendering="crispEdges"
      style={style}
      aria-hidden
    >
      {rects}
    </svg>
  )
}

function Rainbow() {
  return (
    <div className="rainbow">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <span key={i} />
      ))}
    </div>
  )
}

/** 무지개 꼬리 + 냥캣. segments = 무지개 조각 수 */
export function NyanTrail({ segments = 6, scale = 2 }: { segments?: number; scale?: number }) {
  return (
    <div className="trail">
      {Array.from({ length: segments }, (_, i) => (
        <Rainbow key={i} />
      ))}
      <NyanCat scale={scale} />
    </div>
  )
}

export function Starfield() {
  // 고정 위치로 한 번만 뿌린다
  const stars = [
    [8, 6], [72, 12], [40, 22], [88, 34], [15, 45], [60, 52], [30, 68], [82, 74], [50, 86], [10, 92], [92, 94], [66, 4],
  ]
  return (
    <div className="starfield" aria-hidden>
      {stars.map(([x, y], i) => (
        <div key={i} className="star" style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${(i % 4) * 0.3}s` }} />
      ))}
    </div>
  )
}

/** 진행률(0~1)만큼 무지개가 뻗는 진행바 */
export function NyanProgress({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value))
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(pct * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="trail" style={{ width: `calc((100% - 64px) * ${pct} + 12px)` }}>
        {Array.from({ length: 30 }, (_, i) => (
          <Rainbow key={i} />
        ))}
      </div>
      <div style={{ position: 'absolute', top: 0, left: `calc((100% - 64px) * ${pct})` }}>
        <NyanCat scale={2} />
      </div>
    </div>
  )
}
