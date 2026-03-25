# RPG-IA — AI Tabletop RPG Platform

> **Jogue RPG de mesa com um Mestre controlado por IA.** O GM aprende com cada PDF enviado para a plataforma — livros de regras, módulos, bestiários — e se torna mais inteligente para todos os jogadores.

---

## Sumário

- [O que é](#o-que-é)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Como rodar localmente](#como-rodar-localmente)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Serviços e portas](#serviços-e-portas)
- [Banco de dados](#banco-de-dados)
- [Sistema de vozes dinâmicas](#sistema-de-vozes-dinâmicas)
- [Knowledge Gate](#knowledge-gate)
- [Pipeline de PDF](#pipeline-de-pdf)
- [Multiplayer via WebSocket](#multiplayer-via-websocket)
- [Geração de imagens](#geração-de-imagens)
- [Como contribuir](#como-contribuir)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## O que é

RPG-IA é uma plataforma web onde grupos de amigos — ou jogadores solo — jogam RPG de mesa com um **Game Master controlado por Inteligência Artificial**.

O diferencial central é o **banco global de conhecimento**: qualquer PDF enviado por qualquer usuário (livro de regras, módulo de aventura, bestiário, lore de cenário) alimenta um banco vetorial compartilhado. Quanto mais material na plataforma, mais inteligente o GM fica — para todos.

**Casos de uso principais:**
- Grupo que quer jogar D&D 5e sem precisar de um GM humano disponível
- Jogador solo que quer experiência narrativa imersiva
- Teste de módulos e aventuras com GM automatizado
- Plataforma para comunidades de RPG compartilharem conhecimento

---

## Funcionalidades

### GM com IA
- Narração gerada por **GPT-4o** com contexto rico via RAG (Retrieval-Augmented Generation)
- Memória de conversa por sessão (últimas 10 interações)
- Memória longa por campanha com busca semântica
- Controle de NPCs com personalidade persistente
- Aplicação automática de regras via sistema de tags:
  - `[ROLAGEM:2d6+3]` — solicita rolagem de dados
  - `[ESTADO:hp=-5]` — atualiza status do personagem
  - `[IMAGEM:descrição da cena]` — dispara geração de imagem

### Síntese de voz dinâmica (ElevenLabs)
- **10 perfis de voz** com parâmetros distintos por contexto narrativo
- Seleção automática por palavras-chave no texto do GM
- Perfis: `narrator`, `combat`, `mystery`, `epic`, `villain`, `creature`, `death`, `triumph`, `sage`, `tavern`
- Vozes de NPC determinísticas por nome (mesmo NPC = mesma voz sempre)
- Cache Redis SHA-256 com TTL de 1h

### Geração de imagens (DALL·E 3)
- Retratos de personagens e NPCs
- Cenas e ambientes (widescreen)
- Mapas de localização estilo cartografia medieval

### Banco global de conhecimento (pgvector)
- Upload de PDFs via interface web ou API
- Extração de texto com **PyMuPDF**
- Chunking: 512 tokens com overlap de 64
- Embeddings: `text-embedding-3-small` (1536 dim)
- Busca por similaridade cosine (`<=>`) — top-8 por turno
- Processamento assíncrono via **Celery** (não bloqueia o usuário)

### Personagens D&D 5e
- Ficha completa: atributos, CA, HP, spell slots, inventário, habilidades
- Atualização em tempo real durante combate
- Level up com recálculo automático de proficiency bonus
- Condições (envenenado, prostrado, etc.)

### Multiplayer
- Até 6 jogadores humanos + AI companions por sessão
- WebSocket em tempo real: todos veem ações, rolagens e respostas do GM simultaneamente
- AI companions com personalidade JSON persistente

### Frontend dark fantasy
- Interface React 18 + TypeScript + Tailwind CSS com tema dark fantasy
- Painel de jogo com chat, ficha de personagem e mapa SVG interativo
- Drag & drop para upload de PDFs
- Indicador de status do Knowledge Gate

---

## Arquitetura

```
                         ┌─────────────┐
                         │   Nginx     │  80/443
                         │  (proxy)    │
                         └──────┬──────┘
                                │
              ┌─────────────────┼──────────────────┐
              │                 │                  │
       ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
       │  Frontend   │  │   Gateway    │  │  Campaign    │
       │  React/TS   │  │  :8000 Auth  │  │  :8002 GM AI │
       └─────────────┘  └──────┬───────┘  └──────┬───────┘
                               │                 │
              ┌────────────────┼─────────────────┤
              │                │                 │
    ┌─────────▼──────┐ ┌───────▼──────┐ ┌────────▼───────┐
    │ PDF Ingestion  │ │  Character   │ │  Image Gen     │
    │ :8001 + Celery │ │  :8003 CRUD  │ │  :8004 DALL·E  │
    └────────┬───────┘ └──────────────┘ └────────────────┘
             │
    ┌────────▼───────┐    ┌──────────────┐    ┌──────────────┐
    │   TTS Service  │    │  PostgreSQL  │    │    Redis     │
    │  :8005 Voices  │    │  + pgvector  │    │  + Celery    │
    └────────────────┘    └──────────────┘    └──────────────┘
                                                      │
                                             ┌────────▼───────┐
                                             │     MinIO      │
                                             │  PDFs + Media  │
                                             └────────────────┘
```

O **Gateway** centraliza autenticação JWT e roteia para os microserviços. O **Campaign Service** é o núcleo — recebe ações do jogador, executa o pipeline RAG, e dispara TTS e geração de imagem de forma assíncrona (fire-and-forget).

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend APIs | Python 3.12, FastAPI, Pydantic v2 |
| AI Orquestração | LangChain 0.2, LangChain-OpenAI |
| LLM | OpenAI GPT-4o |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Banco de dados | PostgreSQL 16 + pgvector |
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
RPG-IA/
├── docker-compose.yml              # 11 containers — toda a infra
├── .env.template                   # template de variáveis (copie para .env)
├── deploy.sh                       # script de deploy para VPS
│
├── nginx/
│   ├── nginx.conf                  # reverse proxy + SSL + rate limiting
│   └── ssl/                        # certificados Let's Encrypt (não commitar)
│
├── database/
│   ├── init.sql                    # extensões: uuid-ossp, vector
│   ├── schema.sql                  # 20 tabelas + índices ivfflat + views
│   └── migrations/                 # Alembic migrations
│
├── services/
│   ├── gateway/                    # auth JWT, registro, login
│   │   ├── main.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── pdf_ingestion/              # upload PDF + processamento Celery
│   │   ├── main.py                 # FastAPI: /upload, /sources, /knowledge/stats
│   │   ├── worker.py               # Celery: PDF → chunks → embeddings → DB
│   │   ├── global_knowledge_bank.py# Knowledge Gate + GlobalRetriever
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── campaign/                   # núcleo do GM AI
│   │   ├── main.py                 # FastAPI + WebSocket: /session/action, /ws/{id}
│   │   ├── gm_chain.py             # ConversationalRetrievalChain + GPT-4o
│   │   ├── prompts.py              # system prompt do GM
│   │   ├── state_parser.py         # parser de tags [ROLAGEM] [ESTADO] [IMAGEM]
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── character/                  # CRUD D&D 5e
│   │   ├── main.py                 # 11 endpoints: personagem, status, inventário, level up
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── tts/                        # síntese de voz dinâmica
│   │   ├── main.py                 # 10 perfis de voz por contexto narrativo
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── image_gen/                  # geração de imagens
│       ├── main.py                 # DALL·E 3: personagem, NPC, cena, mapa
│       ├── database.py
│       ├── requirements.txt
│       └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── api/
    │   │   ├── client.ts           # Axios + interceptors JWT
    │   │   └── types.ts            # interfaces TypeScript completas
    │   ├── hooks/
    │   │   ├── useAuth.ts          # login, register, logout
    │   │   └── useWebSocket.ts     # conexão WebSocket com auto-reconnect
    │   ├── components/
    │   │   ├── KnowledgeGate.tsx   # upload de PDFs + status do banco
    │   │   ├── GameSession.tsx     # interface principal de jogo
    │   │   ├── CharacterSheet.tsx  # ficha D&D 5e completa
    │   │   └── WorldMap.tsx        # mapa SVG interativo
    │   ├── pages/
    │   │   ├── Login.tsx
    │   │   ├── Register.tsx
    │   │   └── Dashboard.tsx       # listagem e criação de campanhas
    │   ├── App.tsx                 # roteamento React Router v6
    │   ├── main.tsx
    │   └── index.css               # classes Tailwind customizadas
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── Dockerfile
    └── nginx.conf
```

---

## Como rodar localmente

### Pré-requisitos
- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/)
- Chave da API [OpenAI](https://platform.openai.com/)
- Chave da API [ElevenLabs](https://elevenlabs.io/) (opcional para TTS)

### 1. Clone o repositório

```bash
git clone https://github.com/SEU_USUARIO/RPG-IA.git
cd RPG-IA
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.template .env
```

Edite o `.env` e preencha no mínimo:
```bash
OPENAI_API_KEY=sk-...
JWT_SECRET=gere_uma_string_aleatoria_de_32_chars
POSTGRES_PASSWORD=uma_senha_forte
MINIO_ACCESS_KEY=minio_user
MINIO_SECRET_KEY=minio_senha
```

### 3. Suba os containers

```bash
docker compose up -d
```

O primeiro boot pode demorar alguns minutos (download das imagens e build).

### 4. Verifique se está tudo rodando

```bash
docker compose ps
```

### 5. Acesse

| Interface | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Gateway | http://localhost:8000/docs |
| PDF Service | http://localhost:8001/docs |
| Campaign Service | http://localhost:8002/docs |
| Character Service | http://localhost:8003/docs |
| Image Service | http://localhost:8004/docs |
| TTS Service | http://localhost:8005/docs |
| Celery Flower | http://localhost:5555 |
| MinIO Console | http://localhost:9001 |

### 6. Libere o GM — envie o primeiro PDF

Antes de jogar, o Knowledge Gate precisa ser aberto. Acesse o frontend → **Biblioteca de Conhecimento** e faça upload de um PDF (ex: D&D 5e SRD, que é gratuito).

Você pode verificar o status pelo banco:
```bash
docker compose exec postgres psql -U rpg_user -d rpg_platform \
  -c "SELECT * FROM v_knowledge_status;"
```

---

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | Sim | Chave OpenAI (LLM + embeddings + DALL·E) |
| `JWT_SECRET` | Sim | Segredo JWT (mín. 32 chars) |
| `POSTGRES_PASSWORD` | Sim | Senha do PostgreSQL |
| `MINIO_ACCESS_KEY` | Sim | Usuário MinIO |
| `MINIO_SECRET_KEY` | Sim | Senha MinIO |
| `ELEVENLABS_API_KEY` | Não | Chave ElevenLabs (TTS desativado sem ela) |
| `VOICE_NARRATOR_ID` | Não | Voice ID ElevenLabs — narração padrão |
| `VOICE_COMBAT_ID` | Não | Voz para cenas de combate |
| `VOICE_MYSTERY_ID` | Não | Voz para dungeons e horror |
| `VOICE_EPIC_ID` | Não | Voz para momentos épicos |
| `VOICE_VILLAIN_ID` | Não | Voz para antagonistas |
| `VOICE_CREATURE_ID` | Não | Voz para monstros |
| `VOICE_DEATH_ID` | Não | Voz para cenas de morte/luto |
| `VOICE_TRIUMPH_ID` | Não | Voz para vitória/celebração |
| `VOICE_SAGE_ID` | Não | Voz para sábios e divindades |
| `VOICE_TAVERN_ID` | Não | Voz para NPCs comuns |
| `DOMAIN` | Não | Domínio para SSL (deploy em VPS) |

---

## Serviços e portas

| Serviço | Porta | Acesso |
|---|---|---|
| nginx | 80, 443 | público |
| frontend | 3000 | via nginx |
| gateway | 8000 | via nginx `/api/` |
| pdf_service | 8001 | via nginx `/api/books/` |
| campaign_service | 8002 | via nginx `/api/session/` |
| character_service | 8003 | via nginx `/api/characters/` |
| image_service | 8004 | interno |
| tts_service | 8005 | interno |
| postgres | 5432 | interno |
| redis | 6379 | interno |
| minio API | 9000 | interno (media via nginx `/media/`) |
| minio console | 9001 | direto |
| celery flower | 5555 | direto |

---

## Banco de dados

O schema completo está em [database/schema.sql](database/schema.sql). Tabelas principais:

```
Conhecimento (global, sem escopo de campanha):
  pdf_sources         — metadados dos PDFs enviados
  knowledge_chunks    — texto + embedding vector(1536) — índice ivfflat cosine

Jogo:
  users               — contas
  campaigns           — campanhas
  campaign_state      — estado persistente (JSONB)
  campaign_snapshots  — snapshots por sessão
  sessions            — sessões de jogo
  session_messages    — histórico completo
  characters          — PC, NPC, AI companion
  character_status    — HP, condições, spell slots (tempo real)
  character_attributes— atributos D&D (STR/DEX/CON/INT/WIS/CHA)
  character_inventory — itens e equipamentos
  character_abilities — habilidades, features, magias
  gm_memory           — memória longa do GM com embedding
  npcs                — NPCs do mundo
  locations           — locais e mapas
  dice_rolls          — log de rolagens
  generated_images    — URLs de imagens geradas
```

---

## Sistema de vozes dinâmicas

O TTS Service seleciona automaticamente o perfil de voz com base no **contexto narrativo** de cada fala. Cada perfil tem parâmetros diferentes no ElevenLabs:

| Perfil | Contexto | Estabilidade | Estilo | Velocidade |
|---|---|---|---|---|
| `narrator` | Exploração, mundo aberto | 0.65 | 0.00 | 1.00 |
| `mystery` | Dungeons, horror, revelações | 0.30 | 0.35 | 0.90 |
| `combat` | Batalha, perigo imediato | 0.35 | 0.55 | 1.15 |
| `epic` | Clímax, momentos de virada | 0.40 | 0.75 | 1.05 |
| `villain` | Antagonistas, ameaças | 0.55 | 0.45 | 0.95 |
| `creature` | Monstros, entidades | 0.15 | 0.80 | 1.00 |
| `death` | Morte, lamento, luto | 0.45 | 0.20 | 0.80 |
| `triumph` | Vitória, celebração | 0.50 | 0.60 | 1.10 |
| `sage` | Sábios, anciões, deuses | 0.80 | 0.05 | 0.92 |
| `tavern` | NPCs comuns, conversas | 0.70 | 0.15 | 1.05 |

O contexto pode ser fornecido explicitamente na chamada ou inferido automaticamente por palavras-chave no texto.

Cada perfil usa um `VOICE_*_ID` diferente configurado no `.env`. Se um ID não estiver configurado, o perfil herda do `VOICE_NARRATOR_ID` — basta um único ator de voz para o sistema funcionar.

---

## Knowledge Gate

Esta é a regra de negócio mais importante da plataforma:

```
knowledge_chunks VAZIA  →  GM BLOQUEADO
knowledge_chunks >= 1   →  GM LIBERADO
```

O gate é verificado antes de cada chamada ao LangChain. Se bloqueado, o endpoint retorna uma mensagem amigável pedindo que PDFs sejam enviados — sem consumir tokens da OpenAI.

Isso garante que o GM sempre tenha contexto para narrar com qualidade e consistência com o sistema de regras escolhido.

---

## Pipeline de PDF

```
Upload do usuário
  → Validação (PDF, tamanho máx 100MB)
  → Upload para MinIO
  → Registro em pdf_sources (status: processing)
  → Celery task enfileirada em "pdf_processing"
  → Retorno imediato com source_id (202 Accepted)

Worker Celery (assíncrono):
  → Download do PDF do MinIO
  → PyMuPDF extrai texto por página
  → RecursiveCharacterTextSplitter (512 tokens, overlap 64)
  → Embeddings em batches de 50 (respeita rate limit OpenAI)
  → Bulk insert em knowledge_chunks
  → pdf_sources.processed = True, chunk_count = N

Frontend faz polling em GET /sources/{id}/status
```

---

## Multiplayer via WebSocket

```
ws://localhost/ws/{session_id}/{player_id}
```

- Cada sessão suporta 1-6 jogadores humanos + AI companions
- Quando um jogador envia uma ação, o GM processa e faz broadcast para todos os conectados
- AI companions reagem automaticamente às decisões humanas com base em sua personalidade JSON
- Reconexão automática no frontend (até 5 tentativas com backoff)

---

## Geração de imagens

| Endpoint | Tipo | Tamanho | Prompt base |
|---|---|---|---|
| `/generate/character` | Retrato | 1024×1024 | upper body portrait, neutral dark background |
| `/generate/npc` | Retrato NPC | 1024×1024 | upper body portrait, facing slightly left |
| `/generate/scene` | Cena | 1792×1024 | wide establishing shot, cinematic composition |
| `/generate/map` | Mapa | 1024×1024 | top-down, hand-drawn parchment map style |

Todas as imagens são salvas no MinIO e servidas via nginx em `/media/images/`.

---

## Como contribuir

Contribuições são muito bem-vindas! O projeto está aberto para toda a comunidade.

### Formas de contribuir

- Reportar bugs e comportamentos inesperados
- Sugerir novas funcionalidades
- Melhorar a documentação
- Adicionar suporte a novos sistemas de RPG (além de D&D 5e)
- Melhorar o sistema prompt do GM
- Criar novos perfis de voz para contextos narrativos
- Otimizar queries pgvector
- Melhorar o frontend

### Passo a passo

1. **Fork** o repositório
2. Crie uma branch descritiva:
   ```bash
   git checkout -b feat/suporte-pathfinder
   # ou
   git checkout -b fix/knowledge-gate-race-condition
   ```
3. Faça suas alterações
4. Escreva/atualize testes se aplicável
5. Commit com mensagem clara:
   ```bash
   git commit -m "feat: adiciona suporte a fichas Pathfinder 2e"
   ```
6. Abra um **Pull Request** com:
   - Descrição do que foi feito e por quê
   - Screenshots ou logs se relevante
   - Como testar a mudança

### Convenções

- **Python**: seguir PEP 8, type hints em todas as funções, mensagens de erro em português
- **TypeScript**: tipos explícitos, sem `any`
- **Commits**: prefixos `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- **Endpoints FastAPI**: sempre usar `Depends(get_db)`, validar com Pydantic v2, erros em português

### Áreas que mais precisam de ajuda

| Área | O que fazer |
|---|---|
| Testes | O projeto não tem testes ainda — qualquer cobertura é bem-vinda |
| Pathfinder 2e | Adaptar ficha de personagem e prompts para Pathfinder |
| Sistema de combate | Automatizar mais o fluxo de iniciativa e turnos |
| Transcrição de voz | Adicionar STT (Speech-to-Text) para jogar por voz |
| Mobile | A UI ainda não é responsiva para mobile |
| Internacionalização | Suporte a inglês e espanhol além do português |
| Alembic migrations | Configurar e criar as migrations formais |

### Issues e discussões

- Use as **Issues** do GitHub para bugs e sugestões
- Para mudanças grandes, abra uma **Discussion** antes de começar a implementar
- Marque sua issue com as labels adequadas: `bug`, `enhancement`, `help wanted`, `good first issue`

---

## Roadmap

### v1.0 — Base (atual)
- [x] GM AI com RAG e memória de conversa
- [x] Bank global de conhecimento via PDFs
- [x] Síntese de voz dinâmica por contexto narrativo
- [x] Geração de imagens (personagens, cenas, mapas)
- [x] Multiplayer via WebSocket
- [x] Ficha D&D 5e completa
- [x] Deploy com Docker Compose

### v1.1 — Qualidade
- [ ] Testes unitários e de integração
- [ ] CI/CD com GitHub Actions
- [ ] Alembic migrations formais
- [ ] Logging centralizado (ex: Loki + Grafana)
- [ ] Rate limiting por usuário (não só por IP)

### v1.2 — Experiência de jogo
- [ ] STT (Speech-to-Text) — jogar por voz
- [ ] Iniciativa e sistema de turnos automatizado
- [ ] Mapas dinâmicos com fog of war
- [ ] Inventário arrastar-e-soltar
- [ ] Notificações push para multiplayer

### v2.0 — Expansão
- [ ] Suporte a Pathfinder 2e
- [ ] Suporte a Vampire: The Masquerade
- [ ] Sistema de campanhas públicas (compartilhar aventuras)
- [ ] Marketplace de PDFs da comunidade
- [ ] App mobile (React Native)
- [ ] Streaming de áudio em tempo real (sem aguardar geração completa)

---

## Comandos úteis

```bash
# Ver logs do GM em tempo real
docker compose logs -f campaign_service

# Ver fila de processamento de PDFs
docker compose logs -f celery_worker

# Acessar PostgreSQL
docker compose exec postgres psql -U rpg_user -d rpg_platform

# Status do banco de conhecimento
docker compose exec postgres psql -U rpg_user -d rpg_platform \
  -c "SELECT * FROM v_knowledge_status;"

# PDFs por sistema de RPG
docker compose exec postgres psql -U rpg_user -d rpg_platform \
  -c "SELECT rpg_system, COUNT(*) FROM knowledge_chunks GROUP BY rpg_system ORDER BY 2 DESC;"

# Rebuild de um serviço específico
docker compose build campaign_service && docker compose up -d campaign_service

# Deploy completo no VPS
bash deploy.sh
```

---

## Licença

Este projeto é distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para detalhes.

Você é livre para usar, modificar e distribuir — inclusive para fins comerciais — desde que mantenha o aviso de copyright.

---

<div align="center">

Feito com muito d20 e IA.
**Contribuições são bem-vindas — abra uma issue ou PR!**

</div>
