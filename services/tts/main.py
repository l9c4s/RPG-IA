"""
TTS Service — vozes dinâmicas por intenção narrativa.

Cada síntese recebe um `context` que descreve a intenção da cena
(ex: "combat", "mystery", "tavern", "villain_speech", "death").
O serviço mapeia esse contexto para um VoiceProfile com:
  - voice_id  : qual voz ElevenLabs usar
  - stability : 0-1 (alto = consistente, baixo = expressivo)
  - similarity_boost : fidelidade à voz original
  - style     : 0-1 exagero de estilo (eleven_multilingual_v2 suporta)
  - speed     : multiplicador de velocidade
"""

import hashlib
import io
import os
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MODEL_ID = "eleven_multilingual_v2"
TEXT_MAX_LENGTH = 4500

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 3600

MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = "rpg-audio"

# ─── Perfis de voz ───────────────────────────────────────────────────────────
#
# Cada perfil tem um voice_id e configurações de expressividade.
# Os voice_ids vêm de variáveis de ambiente — o usuário escolhe as vozes
# na plataforma ElevenLabs e configura os IDs no .env.
#
# Perfis disponíveis e seus papéis narrativos:
#
#  narrator       → narração neutra, mundo aberto, calmaria
#  combat         → batalha, perigo imediato — voz mais intensa
#  mystery        → dungeons, revelações, horror — instável, sussurrante
#  epic           → momentos épicos, clímax dramático — máxima expressão
#  tavern         → NPCs comuns, conversas leves — relaxado, afável
#  sage           → sábios, anciões, divindades — solene, controlado
#  villain        → antagonistas, discurso de ameaça — frio e perturbador
#  creature       → monstros, entidades — caótico, primitivo
#  death          → morte, lamento, tristeza profunda — lento, baixo
#  triumph        → vitória, celebração — energético


@dataclass
class VoiceProfile:
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    description: str = ""


def _load_profiles() -> dict[str, VoiceProfile]:
    """
    Carrega perfis a partir de variáveis de ambiente.
    Se um voice_id não estiver configurado, herda do perfil `narrator`.
    Isso garante fallback gracioso — basta configurar VOICE_NARRATOR_ID
    e o sistema funciona com um único ator de voz se necessário.
    """
    narrator_id = os.getenv("VOICE_NARRATOR_ID", os.getenv("GM_VOICE_ID", ""))
    combat_id    = os.getenv("VOICE_COMBAT_ID",   narrator_id)
    mystery_id   = os.getenv("VOICE_MYSTERY_ID",  narrator_id)
    epic_id      = os.getenv("VOICE_EPIC_ID",     narrator_id)
    tavern_id    = os.getenv("VOICE_TAVERN_ID",   os.getenv("NPC_VOICE_ID", narrator_id))
    sage_id      = os.getenv("VOICE_SAGE_ID",     narrator_id)
    villain_id   = os.getenv("VOICE_VILLAIN_ID",  os.getenv("VILLAIN_VOICE_ID", narrator_id))
    creature_id  = os.getenv("VOICE_CREATURE_ID", narrator_id)
    death_id     = os.getenv("VOICE_DEATH_ID",    narrator_id)
    triumph_id   = os.getenv("VOICE_TRIUMPH_ID",  narrator_id)

    return {
        # ── Narração e exploração ──────────────────────────────────────────
        "narrator": VoiceProfile(
            voice_id=narrator_id,
            stability=0.65, similarity_boost=0.75, style=0.0, speed=1.0,
            description="Narração neutra — exploração e mundo aberto",
        ),
        "mystery": VoiceProfile(
            voice_id=mystery_id,
            stability=0.30, similarity_boost=0.60, style=0.35, speed=0.90,
            description="Dungeons, horror, revelações obscuras — voz instável e lenta",
        ),
        "death": VoiceProfile(
            voice_id=death_id,
            stability=0.45, similarity_boost=0.70, style=0.20, speed=0.80,
            description="Morte, lamento, peso emocional — voz grave e lenta",
        ),

        # ── Ação e combate ────────────────────────────────────────────────
        "combat": VoiceProfile(
            voice_id=combat_id,
            stability=0.35, similarity_boost=0.70, style=0.55, speed=1.15,
            description="Combate ativo, perigo imediato — intenso e acelerado",
        ),
        "epic": VoiceProfile(
            voice_id=epic_id,
            stability=0.40, similarity_boost=0.80, style=0.75, speed=1.05,
            description="Clímax épico, momentos de virada — máxima expressão dramática",
        ),
        "triumph": VoiceProfile(
            voice_id=triumph_id,
            stability=0.50, similarity_boost=0.75, style=0.60, speed=1.10,
            description="Vitória, celebração, conquista — energético e elevado",
        ),

        # ── NPCs e personagens ────────────────────────────────────────────
        "tavern": VoiceProfile(
            voice_id=tavern_id,
            stability=0.70, similarity_boost=0.75, style=0.15, speed=1.05,
            description="NPCs comuns, tavernas, conversas cotidianas — relaxado",
        ),
        "sage": VoiceProfile(
            voice_id=sage_id,
            stability=0.80, similarity_boost=0.80, style=0.05, speed=0.92,
            description="Sábios, anciões, divindades — solene e controlado",
        ),
        "villain": VoiceProfile(
            voice_id=villain_id,
            stability=0.55, similarity_boost=0.85, style=0.45, speed=0.95,
            description="Antagonistas, ameaças — frio, calculado, perturbador",
        ),
        "creature": VoiceProfile(
            voice_id=creature_id,
            stability=0.15, similarity_boost=0.55, style=0.80, speed=1.0,
            description="Monstros, entidades — caótico e primitivo",
        ),
    }


# Carregado uma vez no startup
VOICE_PROFILES: dict[str, VoiceProfile] = {}


# Palavras-chave para inferência automática de contexto quando não fornecido
_CONTEXT_KEYWORDS: dict[str, list[str]] = {
    "combat":   ["ataca", "espada", "golpe", "sangue", "luta", "combate", "ferido",
                 "dano", "criatura avança", "dispara", "flecha", "magia ofensiva",
                 "hp", "morte iminente", "rola para"],
    "mystery":  ["sombra", "sussurro", "segredo", "maldição", "dungeon", "escuridão",
                 "porta tranca", "runa", "esqueleto", "presença estranha", "frio",
                 "horror", "visão", "sonho", "espírito"],
    "villain":  ["ameaça", "destruição", "não há esperança", "tolos", "dominação",
                 "poder absoluto", "esmagá", "render", "rendição", "obedeçam"],
    "epic":     ["lenda", "profecia", "destino", "herói", "sacrifício", "glória",
                 "épico", "mundo trêmulo", "forças do mal", "última batalha", "hora final"],
    "death":    ["morreu", "faleceu", "último suspiro", "alma partiu", "luto",
                 "tumba", "sepulcro", "chora", "adeus", "partiu para sempre"],
    "triumph":  ["vitória", "venceram", "derrotado", "recompensa", "celebra",
                 "sobreviveram", "heróis", "conquista", "missão cumprida"],
    "sage":     ["sábio diz", "anciã", "divindade", "profecia", "ensinamento",
                 "minha criança", "tempo é cíclico", "ouve bem", "há muito tempo"],
    "tavern":   ["estalagem", "taberna", "cerveja", "hospedeiro", "boas-vindas",
                 "sentem-se", "viajantes", "descansem", "boa noite", "mercador"],
    "creature": ["RRAARRGH", "rugido", "grunhido", "bestial", "garras", "fauces",
                 "monstro", "cria das trevas", "devorar"],
}


def _infer_context(text: str) -> str:
    """
    Infere o contexto narrativo a partir do conteúdo do texto.
    Faz contagem de palavras-chave e retorna o contexto com maior score.
    Fallback: 'narrator'.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for context, keywords in _CONTEXT_KEYWORDS.items():
        scores[context] = sum(1 for kw in keywords if kw in text_lower)

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "narrator"


def _select_npc_profile(npc_name: str, npc_type: str | None = None) -> VoiceProfile:
    """
    Seleciona perfil para NPC.
    - Se npc_type fornecido (villain, sage, creature...) usa perfil direto.
    - Caso contrário, determina pelo hash do nome (consistência por NPC).
    """
    profiles = VOICE_PROFILES
    if npc_type and npc_type in profiles:
        return profiles[npc_type]

    # Determinístico: mesmo NPC sempre usa o mesmo perfil entre tavern/sage/villain
    npc_pool = ["tavern", "sage", "villain", "mystery"]
    index = int(hashlib.sha256(npc_name.encode()).hexdigest(), 16) % len(npc_pool)
    return profiles[npc_pool[index]]


# ─── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TTS Service",
    description="Síntese de voz dinâmica por intenção narrativa — RPG-IA",
    version="2.0.0",
)


@app.on_event("startup")
async def startup_event() -> None:
    global VOICE_PROFILES
    VOICE_PROFILES = _load_profiles()
    logger.info("Perfis de voz carregados: %s", list(VOICE_PROFILES.keys()))

    minio_client = _get_minio_client()
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
            logger.info("Bucket '%s' criado.", MINIO_BUCKET)
    except S3Error as exc:
        logger.error("Erro MinIO no startup: %s", exc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_minio_client() -> Minio:
    return Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
                 secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE)


def _get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _cache_key(text: str, voice_id: str, stability: float, style: float) -> str:
    # Inclui parâmetros que afetam o resultado no cache key
    payload = f"{text}:{voice_id}:{stability:.2f}:{style:.2f}"
    return "tts:" + hashlib.sha256(payload.encode()).hexdigest()


def _object_name(cache_key: str) -> str:
    return f"audio/{cache_key.removeprefix('tts:')}.mp3"


async def _synthesize_audio(text: str, profile: VoiceProfile) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise HTTPException(500, "Chave ELEVENLABS_API_KEY não configurada.")
    if not profile.voice_id:
        raise HTTPException(500, "voice_id não configurado para este perfil.")

    url = ELEVENLABS_TTS_URL.format(voice_id=profile.voice_id)
    body = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": profile.stability,
            "similarity_boost": profile.similarity_boost,
            "style": profile.style,
            "use_speaker_boost": True,
        },
    }
    # speed via query param (suportado pela API v1)
    params = {}
    if profile.speed != 1.0:
        params["optimize_streaming_latency"] = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"xi-api-key": ELEVENLABS_API_KEY,
                     "Content-Type": "application/json",
                     "Accept": "audio/mpeg"},
            json=body,
        )

    if resp.status_code == 401:
        raise HTTPException(502, "Autenticação ElevenLabs falhou. Verifique ELEVENLABS_API_KEY.")
    if resp.status_code != 200:
        raise HTTPException(502, f"Erro ElevenLabs: status {resp.status_code}.")

    return resp.content


async def _upload_to_minio(object_name: str, audio_bytes: bytes) -> str:
    minio_client = _get_minio_client()
    try:
        minio_client.put_object(
            MINIO_BUCKET, object_name, io.BytesIO(audio_bytes),
            len(audio_bytes), content_type="audio/mpeg",
        )
    except S3Error as exc:
        logger.error("Erro upload MinIO: %s", exc)
        raise HTTPException(500, "Falha ao armazenar áudio.")
    return f"/media/{MINIO_BUCKET}/{object_name}"


async def _synthesize_and_cache(text: str, profile: VoiceProfile) -> str:
    key = _cache_key(text, profile.voice_id, profile.stability, profile.style)
    obj = _object_name(key)

    redis_client = _get_redis_client()
    try:
        cached = await redis_client.get(key)
        if cached:
            logger.info("Cache hit: %s (perfil stability=%.2f)", key[:16], profile.stability)
            return cached
    except Exception as exc:
        logger.warning("Redis indisponível (continuando sem cache): %s", exc)
    finally:
        await redis_client.aclose()

    audio_bytes = await _synthesize_audio(text, profile)
    audio_url = await _upload_to_minio(obj, audio_bytes)

    redis_client = _get_redis_client()
    try:
        await redis_client.set(key, audio_url, ex=CACHE_TTL)
    except Exception as exc:
        logger.warning("Erro ao cachear no Redis: %s", exc)
    finally:
        await redis_client.aclose()

    return audio_url


# ─── Models ───────────────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text: str
    context: Optional[str] = None   # narrator|combat|mystery|epic|tavern|sage|villain|creature|death|triumph
    # Se None, o contexto é inferido automaticamente pelo conteúdo do texto
    voice_id_override: Optional[str] = None  # força voice_id específico (ignora perfil)


class SynthesizeNPCRequest(BaseModel):
    text: str
    npc_name: str
    npc_type: Optional[str] = None  # villain|sage|tavern|creature|mystery
    context: Optional[str] = None   # sobrepõe npc_type para os parâmetros de voz


class AudioResponse(BaseModel):
    audio_url: str
    context_used: str
    voice_profile: str


class VoiceProfileInfo(BaseModel):
    name: str
    voice_id: str
    stability: float
    similarity_boost: float
    style: float
    speed: float
    description: str


class VoicesResponse(BaseModel):
    profiles: dict[str, VoiceProfileInfo]
    inference_keywords: dict[str, list[str]]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/synthesize", response_model=AudioResponse)
async def synthesize(request: SynthesizeRequest) -> AudioResponse:
    """
    Sintetiza narração. O contexto narrativo pode ser:
    - Fornecido explicitamente via `context`
    - Inferido automaticamente pelo conteúdo do texto

    Contextos disponíveis: narrator, combat, mystery, epic, tavern,
    sage, villain, creature, death, triumph
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(422, "O campo 'text' não pode estar vazio.")
    if len(text) > TEXT_MAX_LENGTH:
        raise HTTPException(422, f"Texto excede {TEXT_MAX_LENGTH} caracteres.")

    # Determinar contexto
    context = request.context or _infer_context(text)
    if context not in VOICE_PROFILES:
        raise HTTPException(422, f"Contexto '{context}' inválido. "
                            f"Disponíveis: {list(VOICE_PROFILES.keys())}")

    profile = VOICE_PROFILES[context]

    # Override de voice_id manual (ex: GM quer usar voz específica num momento)
    if request.voice_id_override:
        from dataclasses import replace
        profile = replace(profile, voice_id=request.voice_id_override)

    logger.info("Síntese: contexto='%s' | stability=%.2f | style=%.2f | chars=%d",
                context, profile.stability, profile.style, len(text))

    audio_url = await _synthesize_and_cache(text, profile)
    return AudioResponse(
        audio_url=audio_url,
        context_used=context,
        voice_profile=profile.description,
    )


@app.post("/synthesize/npc", response_model=AudioResponse)
async def synthesize_npc(request: SynthesizeNPCRequest) -> AudioResponse:
    """
    Sintetiza fala de NPC com perfil determinístico por nome + tipo.
    O mesmo NPC sempre usa os mesmos parâmetros de voz.
    """
    text = request.text.strip()
    npc_name = request.npc_name.strip()

    if not text:
        raise HTTPException(422, "O campo 'text' não pode estar vazio.")
    if not npc_name:
        raise HTTPException(422, "O campo 'npc_name' não pode estar vazio.")
    if len(text) > TEXT_MAX_LENGTH:
        raise HTTPException(422, f"Texto excede {TEXT_MAX_LENGTH} caracteres.")

    # Contexto pode sobrepor tipo do NPC (ex: vilão em momento épico)
    context = request.context
    if context and context in VOICE_PROFILES:
        profile = VOICE_PROFILES[context]
        ctx_used = context
    else:
        profile = _select_npc_profile(npc_name, request.npc_type)
        ctx_used = request.npc_type or "auto"

    logger.info("NPC '%s': perfil '%s' | stability=%.2f", npc_name, ctx_used, profile.stability)

    audio_url = await _synthesize_and_cache(text, profile)
    return AudioResponse(
        audio_url=audio_url,
        context_used=ctx_used,
        voice_profile=profile.description,
    )


@app.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    """Lista todos os perfis de voz configurados e suas palavras-chave de inferência."""
    profiles_info = {
        name: VoiceProfileInfo(
            name=name,
            voice_id=p.voice_id,
            stability=p.stability,
            similarity_boost=p.similarity_boost,
            style=p.style,
            speed=p.speed,
            description=p.description,
        )
        for name, p in VOICE_PROFILES.items()
    }
    return VoicesResponse(
        profiles=profiles_info,
        inference_keywords=_CONTEXT_KEYWORDS,
    )


@app.get("/health")
async def health() -> dict:
    configured = sum(1 for p in VOICE_PROFILES.values() if p.voice_id)
    return {"status": "ok", "profiles_configured": configured}
