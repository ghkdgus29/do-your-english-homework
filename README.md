# Do Your English Homework 🌈🐱

영어 수업 숙제를 하게 만드는 모바일 전용 웹사이트 (냥캣 키치 스타일).

- **어드민**이 매주 수업 사진을 올리면 Claude Agent SDK가 자동으로 분류·추출한다.
  - 외우기 자료(숙어·패턴) → 플래시카드 (간격 반복 SRS)
  - 숙제지 → 단어 뜻/문장 쓰기, 스크립트 녹음, 다이어리
- 단어 뜻은 추출할 때 한 번만 번역해 두고, 꾹 누르고 있는 동안만 보여준다 (본 횟수 기록).
- 녹음은 서버에 저장하지 않는다. 폰 공유 시트로 카톡에 보낸다. 안드로이드 webm은 서버 ffmpeg로 m4a로 변환만 한다.
- 멤버는 어드민이 발급한 개인 링크(`/join/<token>`)로 들어온다. 1년짜리 쿠키로 로그인이 유지되고, 링크를 재발급하면 기존 링크가 끊긴다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `app/` | FastAPI 백엔드 (uv, SQLModel + SQLite) |
| `app/extraction.py` | 사진 → JSON 추출 (Claude Agent SDK, Read 도구 + structured output) |
| `frontend/` | React + Vite SPA. 빌드 결과는 FastAPI가 정적 서빙 |
| `data/` | SQLite DB와 업로드 사진 (볼륨) |

## 로컬 개발

```bash
cp .env.example .env           # 값 채우고, COOKIE_SECURE=false
uv sync
uv run uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev   # http://localhost:5173 (/api는 8000으로 프록시)
```

- 로컬에서는 `claude` 로그인 상태나 `.env`의 `CLAUDE_CODE_OAUTH_TOKEN`으로 Claude를 호출한다.
- 마이크와 공유 시트는 HTTPS(또는 localhost)에서만 동작한다. 폰으로 테스트하려면 터널이 필요하다.

테스트: `uv run pytest`

## 배포

다른 프로젝트와 공유하는 게 없는 독립 스택이다([docker-compose.yml](docker-compose.yml)). 컨테이너는 `cloudflared` → `nginx` → 앱 세 개이고, 전용 네트워크를 쓰며 포트는 열지 않는다. HTTPS는 Cloudflare Tunnel이 맡는다. 녹음과 공유 시트가 HTTPS에서만 동작하기 때문이다.

`main`에 push하면 다음 순서로 진행된다.

1. 테스트
2. Docker Hub `:latest` 빌드·푸시
3. Tailscale + SSH로 홈랩 `~/do-your-english-homework`에 compose 파일과 `.env`를 쓰고 `docker compose up -d` 실행

### 처음 한 번만

1. **Cloudflare Tunnel 만들기**
   - Zero Trust → Networks → Tunnels → Create a tunnel(Cloudflared)로 터널을 만들고, 토큰을 복사한다.
   - 터널의 Route를 추가한다: `gloria-homework.site`, `www.gloria-homework.site` → `http://nginx:80`. nginx 설정은 [deploy/nginx.conf](deploy/nginx.conf)에 있고, www는 루트 도메인으로 리다이렉트된다.
2. **GitHub Secrets**
   - `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`
   - `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`: Tailscale OAuth 클라이언트. `tag:ci` 태그가 필요하다.
   - `SERVER_TS_IP`, `SSH_PRIVATE_KEY`: 홈랩의 `deploy` 유저
   - `ENV_FILE_CONTENT`: 서버 `.env` 전체
     ```
     ADMIN_PASSWORD=...
     SECRET_KEY=...
     CLAUDE_CODE_OAUTH_TOKEN=...
     TUNNEL_TOKEN=...
     ```

### 운영

- 서버에서 직접 다루기: `cd ~/do-your-english-homework && docker compose logs -f app` (`restart`, `down`도 같은 폴더에서). `.env`가 서버에 남아 있어서 그대로 동작한다.
- `~/do-your-english-homework/data`가 DB와 사진 볼륨이다. 백업 대상이다.
- 로그는 두 곳에 남는다. `docker compose logs`(컨테이너 재생성 시 사라짐, 서비스당 10MB×3으로 제한)와 `data/logs/app.log`(볼륨이라 남음, 10MB×6으로 로테이션. `LOG_MAX_MB`, `LOG_BACKUPS`로 조정).

## 사용 흐름

1. `https://<도메인>/admin`에 `ADMIN_PASSWORD`로 로그인하고 멤버를 추가한 뒤, 링크를 복사해 카톡으로 전달한다.
2. 수업이 끝나면 사진을 올린다. 1분쯤 뒤 `ready`가 되고, 추출이 이상하면 `재추출`하거나 `JSON 편집`으로 고친다.
3. 멤버는 링크로 들어와 숙제와 카드를 하고, 하단 REVIEW에서 복습할 때가 된 카드를 넘긴다.
