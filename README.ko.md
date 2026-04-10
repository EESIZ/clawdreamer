# Dreamer

> https://github.com/JinHo-von-Choi/memento-mcp 프로젝트를 Openclaw에 적용하다가 실패하고 잠에 든 다음 날
  장원영이랑 버스타고 출근하는 꿈을 꾸다가 깼는데, 갑자기 아이디어가 떠오름

> AI 에이전트는 잠을 자지 않는다. 꿈도 꾸지 않는다. → 이게 사실 AI 에이전트의 가장 큰 문제

> 꿈을 꾼다는건, 자면서 기억들을 압축하고 정리하는 과정을 우연히 의식이 깨어나는 바람에 보게 되는 과정이라고 함
  즉, 이러한 과정을 AI에게 적용한다면 
   - AI의 기억방식을 무한히 늘리는 DB에 짱박는 방식이 아닌 수만년 진화한 생물의 뇌의 처리방식을 모방할 수 있지 않을까
> 그러면서 메모리로 인해 토큰을 무한히 잡아먹는 문제에서도 벗어날 수 있으면서
> 동시에 인간 기준에서 어느정도 허용할 수 있지만 인간스러우면서 완벽하진 않은 '기억력'을 만들어낼 수 있지 않을까?

요약 : 꿈이라는 과정은 = 인간 기억 DB 압축과정이라는 가설 → AI 봇에게도 유사한 기능을 추가해보자는 프로젝트

**Dreamer는 AI 에이전트에게 '꿈'을 선물한다.**

[OpenClaw](https://openclaw.ai)용으로 만들었지만, 마크다운 파일을 생성하는 어떤 시스템과도 연동 가능하다. - "아마도"

## 작동 원리

Claude의 도움을 받아 수면 신경과학 논문을 참고해
모델로 삼았다. 매일 밤, 사람의 뇌가 하는 것과 같은 3단계를 거친다.

### Phase 1: NREM -- "오늘 무슨 일이 있었지?"

NREM 수면 동안 해마는 하루의 사건들을 재생하고, 중요한 패턴만 골라 신피질로 전달한다. Dreamer도 같은 일을 한다:

- openclaw에서 생성하는 에피소드 파일 로드 (`YYYY-MM-DD.md` 및 `YYYY-MM-DD-slug.md`)
- 텍스트를 의미 단위로 분할
- 임베딩 유사도로 관련 청크를 클러스터링
- LLM이 각 클러스터를 핵심 사실로 압축
- 기존 기억과 중복 체크
- 새 시맨틱 기억을 LanceDB에 저장

날것의 경험이 들어가서, 압축된 지식이 나온다.

### Phase 2: REM -- "이건 내가 아는 것과 맞아?"

REM 수면은 새 기억과 기존 기억을 통합하는 시간이다 -- 모순을 해결하고, 연결을 강화한다. Dreamer의 REM 단계:

- **새** 기억과 **기존** 기억 사이의 충돌 탐지 (예상 복잡도 : O(N*M)) ← 뭔가 중간에 모듈을 잘 넣으면 최적화 가능한데 이정도가 내 한계인듯 
- 충돌 분류: `state_change` / `different_aspects` / `unrelated`
- **상태 변경**: 하나의 기억으로 병합 ("모델을 Claude로 변경" + 이전: "모델은 Gemini였음")
- **다른 측면**: 종합적인 기억으로 통합
- 중요도 감쇠 적용 -- 호출되지 않는 기억은 서서히 희미해진다
- 임계치 이하로 떨어진 기억은 소프트 삭제
- 처리된 에피소드는 아카이브로 이동

"저번 주에 설정 바꿨다고 했잖아요" 같은 일은 더 이상 없다.

### Phase 3: Dream Log -- "오늘 밤 무슨 꿈을 꿨지?"

매 사이클마다 마크다운 리포트가 생성된다: 뭘 만들었고, 뭘 병합했고, 뭘 잊었는지. 에이전트의 기억 관리에 대한 투명한 기록.

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 설정
cp .env.example .env
# .env에 OpenAI API 키 입력

# 3. 데이터 디렉토리 + LanceDB 테이블 초기화
python setup.py --example

# 4. 실행
python dreamer.py --verbose
```

setup 스크립트가 디렉토리 구조 생성, LanceDB `memories` 테이블 초기화(1536차원 벡터), 예제 에피소드 파일 생성까지 해준다.

## OpenClaw 연동

Dreamer는 [OpenClaw](https://openclaw.ai)의 메모리 시스템과 함께 동작하도록 설계되었다.

### 전제 조건

1. **OpenClaw Gateway** -- `memory-lancedb` 플러그인 활성화 필요
2. **LanceDB** -- 시맨틱 기억 벡터 저장소
3. **에피소드 파일** -- OpenClaw의 `session-memory` 훅이 자동 생성

### OpenClaw 설정

`openclaw.json`에서 메모리 플러그인을 활성화한다:

```json
{
  "plugins": {
    "slots": {
      "memory": "memory-lancedb"
    },
    "entries": {
      "memory-lancedb": {
        "enabled": true,
        "config": {
          "embedding": {
            "apiKey": "${OPENAI_API_KEY}",
            "model": "text-embedding-3-small"
          },
          "autoCapture": true,
          "autoRecall": true
        }
      }
    }
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "session-memory": {
          "enabled": true
        }
      }
    }
  }
}
```

각 설정의 역할:
- **memory-lancedb**: 시맨틱 기억을 1536차원 벡터로 LanceDB에 저장. 게이트웨이와 Dreamer가 같은 DB를 공유한다.
- **session-memory**: `/new` 명령 시 대화 요약을 에피소드 파일(`YYYY-MM-DD-slug.md`)로 저장하는 내부 훅. `memoryFlush`는 컨텍스트 윈도우 압축 시 `YYYY-MM-DD.md`로 기록.

### 데이터 흐름

```
사용자 <-> OpenClaw Gateway
              |
              |-- autoCapture --> LanceDB (시맨틱 기억)
              |                      ^
              |-- session-memory --> episodes/YYYY-MM-DD-slug.md  (/new 시)
              |-- memoryFlush ----> episodes/YYYY-MM-DD.md        (압축 시)
              |                      |
              |              02:00  session-flush (/new 자동 전송)
              |                      |
              |              03:00  Dreamer (NREM → REM → Dream Log)
              |                      |
              +-- autoRecall <---- LanceDB (정리 완료)
```

1. **대화 중**: 게이트웨이가 중요한 사실을 LanceDB에 자동 저장하고, 관련 기억을 자동 회상
2. **에피소드 생성**: `/new` 명령 시 session-memory 훅이 에피소드 파일 생성. 컨텍스트 압축 시 memoryFlush가 에피소드 파일 생성.
3. **매일 새벽 2시**: `session-flush`가 `/new`를 자동 전송하여 그날 대화를 에피소드로 저장
4. **매일 새벽 3시**: Dreamer가 에피소드를 읽고, 새 시맨틱 기억을 만들고, 기존 기억과 충돌을 해결하고, 오래된 기억을 정리
5. **다음 대화**: 게이트웨이가 정리된 기억을 LanceDB에서 회상

### 단독 사용 (OpenClaw 없이)

Dreamer는 마크다운 에피소드 파일을 생성하는 어떤 시스템과도 연동된다. episodes 디렉토리에 일별 파일을 작성하면 된다:

```
$DREAMER_HOME/episodes/2024-03-15.md
$DREAMER_HOME/episodes/2024-03-16.md
```

`python setup.py`로 LanceDB 테이블을 초기화한 후 실행.

## 설정

모든 설정은 `config.py`에 있으며, 환경변수로 오버라이드 가능:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DREAMER_HOME` | `~/.dreamer` | 데이터 루트 디렉토리 |
| `DREAMER_EMBEDDING_PROVIDER` | `openai` | `openai`, `ollama`, `sentence-transformers` |
| `DREAMER_EMBEDDING_DIM` | `1536` | 임베딩 모델에 맞게 설정 |
| `OPENAI_API_KEY` | (openai 사용 시 필수) | OpenAI 임베딩용 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 URL |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama 임베딩 모델 |
| `ST_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-transformers 모델 |
| `DREAMER_LLM_PROVIDER` | `openai` | `openai`, `ollama`, `minimax` |
| `OLLAMA_LLM_MODEL` | `qwen2.5:3b` | Ollama LLM 모델 (요약/분류용) |
| `MINIMAX_API_KEY` | (선택) | MiniMax LLM 사용 시 |

### 에러 알림

Dreamer는 AI 에이전트가 모르게 백그라운드에서 돌아가는 프로세스다. 장애 발생 시 에이전트가 아닌 **운영자**에게 직접 알림을 보낸다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DREAMER_ALERT_PROVIDER` | (비활성) | `telegram`, `slack`, `webhook` |
| `DREAMER_ALERT_TELEGRAM_BOT_TOKEN` | | 텔레그램 봇 토큰 |
| `DREAMER_ALERT_TELEGRAM_CHAT_ID` | | 알림 받을 텔레그램 채팅 ID |
| `DREAMER_ALERT_SLACK_WEBHOOK_URL` | | Slack incoming webhook URL |
| `DREAMER_ALERT_WEBHOOK_URL` | | 일반 webhook (POST JSON) |

설정 예시 (Telegram):
```bash
export DREAMER_ALERT_PROVIDER=telegram
export DREAMER_ALERT_TELEGRAM_BOT_TOKEN=123456:ABC-DEF
export DREAMER_ALERT_TELEGRAM_CHAT_ID=your_chat_id
```

에러 발생 시 이런 메시지를 받는다:
> :skull: **Dreamer Error**
> HTTPError: HTTP Error 429: Too Many Requests

### 튜닝 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `CLUSTER_SIMILARITY` | 0.75 | 청크 클러스터링 임계치 |
| `DEDUP_SIMILARITY` | 0.90 | 이 이상 유사하면 중복으로 스킵 |
| `CONTRADICTION_SIMILARITY` | 0.70 | 충돌 탐지 임계치 |
| `IMPORTANCE_DECAY_RATE` | 0.05 | 일일 중요도 감쇠율 |
| `SOFT_DELETE_THRESHOLD` | 0.15 | 이 이하면 삭제 |
| `MAX_EPISODES_PER_RUN` | 7 | 사이클당 최대 처리 일수 |
| `MAX_NEW_MEMORIES` | 20 | 사이클당 최대 신규 기억 수 |

### 디렉토리 구조

```
$DREAMER_HOME/
  episodes/           # 입력: 일별 마크다운 파일 (YYYY-MM-DD.md, YYYY-MM-DD-slug.md)
  episodes/archive/   # 처리 완료된 에피소드
  lancedb/            # LanceDB 벡터 DB (게이트웨이와 공유)
  dream-log/          # 출력: 매일 밤 정리 리포트
  memory-archive/     # 백업: 병합 전 기억 스냅샷
  workspace/          # 선택: 참조 문서 (컨텍스트 연결용)
    docs/             # 자동 생성되는 참조 문서
    skills/           # 스킬 정의 (SKILL.md)
```

## session-flush (자동 에피소드 생성)

대화가 짧아서 `memoryFlush`가 발동되지 않는 날에도 에피소드가 누락되지 않도록, 매일 새벽 2시에 `/new` 명령을 자동 전송하는 스크립트다. Dreamer(새벽 3시) 실행 전에 그날의 대화를 에피소드 파일로 확보한다.

```bash
# systemd timer 등록 (examples/ 참고)
sudo systemctl enable --now session-flush.timer
```

## 에피소드 파일 형식

에피소드는 `YYYY-MM-DD.md` 또는 `YYYY-MM-DD-slug.md` 형식의 마크다운 파일이다. AI 에이전트의 하루 경험을 자유롭게 기록한다:

```markdown
# 세션 노트 - 2024-03-15

## 배포 관련 논의
Docker Compose + nginx 리버스 프록시 구조로 결정.
DB는 PostgreSQL 16, pgvector 확장 사용.

## API 연동
결제 API 연결 완료. POST /v1/charges
속도 제한: 100 req/min. Bearer 토큰 인증.
```

## 크론잡 실행

```bash
# 예시: 매일 새벽 3시 실행
0 3 * * * cd /path/to/dreamer && python3 dreamer.py --verbose >> dream-log/cron.log 2>&1
```

또는 `examples/` 디렉토리의 systemd timer를 사용.

## 아키텍처

```
에피소드 파일 (YYYY-MM-DD.md / YYYY-MM-DD-slug.md)
        |
        v
   +---------+
   |  NREM   |  분할 -> 임베딩 -> 클러스터링 -> 요약 -> 저장
   +----+----+
        | created_ids
        v
   +---------+
   |   REM   |  충돌 탐지 -> 병합/통합 -> 감쇠 -> 정리
   +----+----+
        |
        v
   +---------+
   |Dream Log|  리포트 생성
   +---------+
```

## 요구 사항

- Python 3.10+
- 임베딩 제공자 (택 1):
  - OpenAI API 키 (`text-embedding-3-small`)
  - [Ollama](https://ollama.com) 로컬 실행 (`nomic-embed-text`)
  - `pip install sentence-transformers` (`all-MiniLM-L6-v2`)
- LLM 제공자 (택 1):
  - OpenAI API 키 (`gpt-4.1-nano`)
  - [Ollama](https://ollama.com) 로컬 실행 (`qwen2.5:3b` 등)
  - MiniMax API 키

## 라이선스

MIT
