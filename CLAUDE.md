# AI Tabletop RPG Platform

Plataforma de RPG de mesa assistida por IA com GM inteligente, geração de voz via ElevenLabs,
imagens via DALL·E 3 e banco global de embeddings alimentado por PDFs enviados pelos usuários.

---

## Stack completa

| Camada | Tecnologia |
|---|---|
| Backend APIs | Python 3.12, FastAPI, Pydantic v2 |
| AI Orquestração | LangChain 0.2, LangChain-OpenAI |
| LLM | OpenAI GPT-4o |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Banco de dados | PostgreSQL 16 + extensão pgvector |
| Fila assíncrona | Redis 7 + Celery 5 |
| Worker monitor | Celery Flower (porta 5555) |
| Armazenamento | MinIO (S3-compatible) |
| TTS | ElevenLabs API (eleven_multilingual_v2) |
| Geração de imagem | OpenAI DALL·E 3 |
| PDF processing | PyMuPDF (fitz) |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| WebSocket | FastAPI WebSocket (multiplayer real-time) |
| Proxy / SSL | Nginx + Certbot (Let's Encrypt) |
| Containers | Docker + Docker Compose |
| Deploy | VPS Ubuntu 22.04 LTS |

---

## Estrutura do projeto

```
/
├── docker-compose.yml              # 11 containers — toda a infra
├── .env                            # segredos (nunca commitar)
├── .env.template                   # template público
├── CLAUDE.md                       # este arquivo
│
├── nginx/
│   ├── nginx.conf                  # reverse proxy + SSL + rate limiting
│   └── ssl/                        # certificados Let's Encrypt
│
├── database/
│   ├── init.sql                    # extensões (uuid-ossp, vector)
│   ├── schema.sql                  # schema completo
│   └── migrations/                 # Alembic migrations
│
├── services/
│   ├── gateway/                    # API Gateway — auth, roteamento, WebSocket broker
│   │   ├── main.py
│   │   ├── auth.py                 # JWT
│   │   └── Dockerfile
│   │
│   ├── pdf_ingestion/              # Upload PDF + Celery worker
│   │   ├── main.py                 # FastAPI — /upload, /sources, /knowledge/stats
│   │   ├── worker.py               # Celery task: PDF → chunks → embeddings → DB
│   │   ├── global_knowledge_bank.py # Gate + GlobalRetriever
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── campaign/                   # GM AI — LangChain RAG
│   │   ├── main.py                 # FastAPI — /session/action, /ws/{session_id}
│   │   ├── gm_chain.py             # ConversationalRetrievalChain setup
│   │   ├── prompts.py              # GM system prompt, templates
│   │   ├── state_parser.py         # Parseia resposta do GM (rolls, state updates)
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── character/                  # CRUD personagens + status D&D
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── tts/                        # ElevenLabs TTS
│   │   ├── main.py                 # /synthesize, /synthesize/npc
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── image_gen/                  # DALL·E 3
│       ├── main.py                 # /generate/character, /npc, /scene, /map
│       ├── requirements.txt
│       └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── types/
    │   │   └── index.ts            # Todos os 30+ tipos TypeScript centralizados
    │   ├── lib/
    │   │   ├── constants.ts        # RPG_SYSTEMS, RACES, CLASSES, SKILLS, CONDITIONS, etc.
    │   │   └── utils.ts            # cn(), dndModifier(), formatModifier(), formatDate()
    │   ├── contexts/
    │   │   └── AuthContext.tsx     # AuthProvider global + useAuthContext()
    │   ├── api/
    │   │   ├── client.ts           # Instâncias axios (apiClient, apiClientMultipart)
    │   │   ├── auth.ts             # authApi { login, register, me }
    │   │   ├── campaigns.ts        # campaignApi { list, get, create, delete, ... }
    │   │   ├── characters.ts       # characterApi { list, get, create, update, ... }
    │   │   ├── knowledge.ts        # knowledgeApi { getStats, listSources, upload, ... }
    │   │   ├── session.ts          # sessionApi { getOrCreate, getHistory, sendAction }
    │   │   ├── types.ts            # Re-export de ../types (retrocompatibilidade)
    │   │   └── index.ts            # Re-export de todos os módulos de API
    │   ├── hooks/
    │   │   ├── useAuth.ts          # Wrapper fino sobre useAuthContext()
    │   │   ├── useWebSocket.ts     # Conexão WS com auto-reconnect (5 tentativas, ping 25s)
    │   │   └── useLocalStorage.ts  # Hook genérico tipado com sync cross-tab
    │   ├── components/
    │   │   ├── ui/                 # Primitivos reutilizáveis
    │   │   │   ├── Button.tsx      # variant, size, isLoading, leftIcon, rightIcon
    │   │   │   ├── Input.tsx       # label, error, helperText, ARIA completo
    │   │   │   ├── Modal.tsx       # portal, focus trap, ESC/click-outside fecha
    │   │   │   ├── Badge.tsx       # 6 variantes (default/success/warning/danger/info/condition)
    │   │   │   ├── Spinner.tsx     # SVG animado, 3 tamanhos
    │   │   │   ├── Skeleton.tsx    # + SkeletonCard, SkeletonTable
    │   │   │   └── index.ts        # Re-export de todos os primitivos
    │   │   ├── layout/
    │   │   │   ├── AppLayout.tsx   # Navbar reutilizável (brand, links, logout)
    │   │   │   └── AuthLayout.tsx  # Layout centralizado para login/register
    │   │   ├── ErrorBoundary.tsx   # Class component — captura erros de render
    │   │   ├── CharacterCreationModal.tsx  # Wizard 3 passos (usa Modal + Button + Input)
    │   │   ├── CharacterSheet.tsx  # Ficha D&D completa (usa Spinner + Badge)
    │   │   ├── GameSession.tsx     # Chat WebSocket em tempo real
    │   │   ├── KnowledgeGate.tsx   # Upload PDF + gestão de fontes
    │   │   └── WorldMap.tsx        # Mapa SVG interativo
    │   ├── pages/
    │   │   ├── Login.tsx           # Usa AuthLayout + Input + Button
    │   │   ├── Register.tsx        # Usa AuthLayout + Input + Button
    │   │   ├── Dashboard.tsx       # Usa AppLayout + Button + Badge + Modal + Skeleton
    │   │   └── Lobby.tsx           # Usa AppLayout + Button + Badge + Spinner
    │   ├── __tests__/
    │   │   ├── setup.ts
    │   │   ├── useAuth.test.ts
    │   │   └── useWebSocket.test.ts
    │   ├── App.tsx                 # Wrapped em ErrorBoundary + AuthProvider
    │   ├── main.tsx
    │   └── index.css               # Tailwind directives + tema dark fantasy
    └── Dockerfile
```

---

## Banco de dados — tabelas principais

### Tabelas de conhecimento (CORE)

```sql
-- Todo PDF enviado por qualquer usuário alimenta essa tabela
-- É o banco global de embeddings — sem escopo de campanha
pdf_sources         -- metadados dos PDFs (título, sistema, tipo, status)
knowledge_chunks    -- chunks de texto + embedding vector(1536)
                    -- índice: ivfflat cosine, lists=100

-- View de status do banco
v_knowledge_status  -- total_chunks, gm_is_ready (bool), sistemas cobertos
```

### Tabelas de jogo

```sql
users               -- contas da plataforma
campaigns           -- campanhas (título, dificuldade, tom, capítulo atual)
campaign_state      -- estado persistente (quests, mundo, cena atual) — JSONB
campaign_snapshots  -- snapshots por sessão para rollback
campaign_players    -- jogadores humanos e IA por campanha
sessions            -- sessões de jogo
session_messages    -- histórico de mensagens (player + GM)
characters          -- personagens (PC, NPC, AI companion)
character_status    -- HP, spell slots, condições — atualizado em tempo real
character_attributes -- STR/DEX/CON/INT/WIS/CHA, CA, proficiências
character_inventory  -- itens, equipamentos, moeda
character_abilities  -- habilidades, features, magias
gm_memory           -- memória longa do GM com embedding (busca semântica)
npcs                -- NPCs do mundo
locations           -- locais e mapas
dice_rolls          -- log de rolagens
generated_images    -- URLs das imagens geradas (personagens, cenas, mapas)
```

---

## Regras de negócio CRÍTICAS

### 1. Knowledge Gate — regra mais importante
```
knowledge_chunks vazia → GM BLOQUEADO (retorna mensagem, não chama LLM)
knowledge_chunks com >= 1 chunk → GM LIBERADO

Checar ANTES de cada chamada ao LangChain chain.
Função: check_gate(db) em services/pdf_ingestion/global_knowledge_bank.py
```

### 2. Banco global — sem escopo
```
Todo PDF → uma única tabela knowledge_chunks
NÃO existe separação por campanha, usuário ou escopo
O GM busca em TODOS os chunks disponíveis via cosine similarity
Mais PDFs na plataforma = GM mais inteligente para TODOS
```

### 3. Pipeline de PDF (Celery worker)
```
Upload → MinIO → Celery queue "pdf_processing"
Worker: PyMuPDF extrai texto → RecursiveCharacterTextSplitter (512 tokens, overlap 64)
      → OpenAI embed_documents em batches de 50
      → bulk insert em knowledge_chunks
      → atualiza pdf_sources.processed = True
Retorna source_id imediatamente. Cliente faz polling em /sources/{id}/status
```

### 4. RAG por turno do GM
```
Player action (texto ou voz transcrita)
→ embed_query(action)
→ SELECT top-8 FROM knowledge_chunks ORDER BY embedding <=> query_vector
→ formata contexto
→ injeta no prompt do LangChain chain
→ GPT-4o gera resposta
→ parseia [ROLAGEM:], [ESTADO:], [IMAGEM:] tags
→ dispara TTS (ElevenLabs) e imagem (DALL·E) se necessário
```

### 5. Multiplayer
```
Sessão suporta 1-6 jogadores humanos + jogadores IA (AI companions)
WebSocket por sessão: /ws/{session_id}/{player_id}
Todos recebem broadcast das ações, resultados de dados, e respostas do GM
Jogadores IA têm personalidade JSON persistente e reagem às decisões humanas
```

---

## Variáveis de ambiente necessárias

```bash
# PostgreSQL
POSTGRES_PASSWORD=

# MinIO
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=

# OpenAI (LLM + embeddings + DALL·E 3)
OPENAI_API_KEY=

# ElevenLabs (TTS)
ELEVENLABS_API_KEY=
GM_VOICE_ID=          # voice ID do narrador principal
NPC_VOICE_ID=         # voice ID padrão para NPCs
VILLAIN_VOICE_ID=     # voice ID para vilões

# Auth
JWT_SECRET=           # mínimo 32 chars aleatórios

# Domínio (nginx SSL)
DOMAIN=
```

---

## Serviços e portas internas

| Serviço | Porta | Acesso externo |
|---|---|---|
| nginx | 80, 443 | público |
| gateway | 8000 | via nginx /api/ |
| pdf_service | 8001 | via nginx /api/books/ |
| campaign_service | 8002 | via nginx /api/session/ |
| character_service | 8003 | via nginx /api/characters/ |
| image_service | 8004 | interno |
| tts_service | 8005 | interno |
| postgres | 5432 | interno |
| redis | 6379 | interno |
| minio API | 9000 | interno (media via nginx) |
| minio console | 9001 | direto (restringir por IP) |
| celery flower | 5555 | direto (restringir por IP) |

---

## Comandos úteis

```bash
# Subir tudo
docker compose up -d

# Ver logs do GM
docker compose logs -f campaign_service

# Ver fila de processamento de PDFs
docker compose logs -f celery_worker

# Acessar postgres diretamente
docker compose exec postgres psql -U rpg_user -d rpg_platform

# Verificar status do banco de conhecimento
docker compose exec postgres psql -U rpg_user -d rpg_platform \
  -c "SELECT * FROM v_knowledge_status;"

# Contar chunks por sistema de RPG
docker compose exec postgres psql -U rpg_user -d rpg_platform \
  -c "SELECT rpg_system, COUNT(*) FROM knowledge_chunks GROUP BY rpg_system ORDER BY 2 DESC;"

# Rodar migrations
docker compose exec gateway alembic upgrade head

# Rebuild um serviço específico
docker compose build campaign_service && docker compose up -d campaign_service

# Deploy completo no VPS
bash deploy.sh
```

---

## Padrões de código

### FastAPI endpoints
```python
# Sempre usar Depends(get_db) para injeção de sessão DB
# Sempre validar com Pydantic models
# Retornar erros com HTTPException e mensagens em português (UX do usuário)
# Rotas internas entre serviços via httpx.AsyncClient com timeout=30.0
```

### LangChain
```python
# Model: sempre "gpt-4o" (nunca hardcode outra versão)
# Embeddings: sempre "text-embedding-3-small"
# Chain: ConversationalRetrievalChain com ConversationBufferWindowMemory(k=10)
# RAG: top_k=8, search_type="similarity"
# Streaming: sempre True para respostas do GM (melhor UX)
```

### Celery tasks
```python
# Sempre bind=True, max_retries=3, task_acks_late=True
# Bulk insert para chunks (nunca inserir um a um)
# Processar embeddings em batches de 50 (respeita rate limit OpenAI)
# Logar progresso a cada batch
```

### pgvector queries
```python
# Sempre usar <=> (cosine distance), não <-> (L2) nem <#> (inner product)
# Índice IVFFlat com lists=100 (bom até ~1M chunks)
# Acima de 1M chunks: migrar para HNSW
# Cast explícito: embedding <=> :vec::vector
```

### TTS (ElevenLabs)
```python
# Cache por hash SHA256 do (texto + voice_id) no Redis — TTL 1h
# Limitar texto a 4500 chars por chamada
# NPCs: voz determinística por hash do nome (mesmo NPC = mesma voz sempre)
# Modelos: eleven_multilingual_v2 (padrão), eleven_turbo_v2 (mais rápido)
```

### Imagens (DALL·E 3)
```python
# Sempre incluir "No text, no watermarks" no final do prompt
# Personagens: "upper body portrait, facing slightly left, neutral dark background"
# Cenas: "wide establishing shot, cinematic composition"
# Mapas: "top-down view, hand-drawn parchment map style, aged paper texture"
# Salvar em MinIO e retornar URL relativa /media/images/...
```

### Frontend (React + TypeScript)
```typescript
// Tipos: sempre importar de src/types (nunca de api/types diretamente)
// Constantes RPG: sempre importar de src/lib/constants (RPG_SYSTEMS, RACES, etc.)
// Utilitários: cn() para classes, dndModifier() para modificadores D&D
// Auth: sempre via useAuth() (wrapper de AuthContext) — nunca acessar localStorage direto
// API: usar módulos de domínio (campaignApi, characterApi, etc.) — nunca apiClient direto
// Componentes UI: sempre usar primitivos de src/components/ui antes de criar novos
// Layouts: AppLayout para páginas autenticadas, AuthLayout para login/register
// Erros de render: ErrorBoundary já está no root — não duplicar
// Lazy loading: todas as páginas são lazy-loaded via React.lazy() em App.tsx
// Sem dependências novas sem aprovação — usar apenas o que está no package.json
```

---

## Skills disponíveis

Skills são conjuntos de regras especializadas invocáveis pelo Claude Code via `/skill-name`.
Ficam em `.agents/skills/` e são carregadas automaticamente quando relevantes.

### `vercel-react-best-practices`
**Quando usar:** ao escrever, revisar ou refatorar componentes React/TypeScript deste projeto.

68 regras de performance organizadas por prioridade:

| Prioridade | Categoria | Prefixo | Exemplos |
|---|---|---|---|
| 1 — CRÍTICO | Eliminar waterfalls | `async-` | Promise.all para operações independentes |
| 2 — CRÍTICO | Bundle size | `bundle-` | Import direto (sem barrel), dynamic imports |
| 3 — ALTO | Performance server | `server-` | React.cache(), paralelizar fetches |
| 4 — MÉDIO-ALTO | Data fetching client | `client-` | Deduplicar listeners, versionar localStorage |
| 5 — MÉDIO | Otimizar re-renders | `rerender-` | memo, useRef para valores transientes |
| 6 — MÉDIO | Rendering | `rendering-` | Suspense, content-visibility, JSX estático |
| 7 — BAIXO-MÉDIO | JS performance | `js-` | Map/Set O(1), early exit, RegExp hoistado |
| 8 — BAIXO | Padrões avançados | `advanced-` | useLatest, init-once, event handler refs |

Regras individuais em `.agents/skills/vercel-react-best-practices/rules/`.
Guia completo compilado em `.agents/skills/vercel-react-best-practices/AGENTS.md`.

---

## Contexto de produto

**O que é:** Plataforma web onde jogadores criam campanhas de RPG de mesa com um GM
controlado por IA. O GM narra histórias, aplica regras, controla NPCs, gera voz e imagens.

**Diferencial principal:** O GM aprende com cada PDF enviado para a plataforma.
Qualquer livro de regras, módulo de aventura, manual de cenário ou material homebrew
enviado por qualquer usuário alimenta o banco global e torna o GM mais inteligente
para toda a plataforma.

**Tipos de PDF aceitos:**
- Livros de regras (D&D 5e PHB, Pathfinder, etc.)
- Módulos e aventuras prontas
- Lore e materiais de mundo/cenário
- Bestiários e livros de monstros
- Suplementos e sourcebooks
- Material homebrew e custom

**Usuário típico:** Grupo de amigos que quer jogar RPG sem precisar de um GM humano,
ou jogador solo que quer uma experiência narrativa imersiva.
