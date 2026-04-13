"""
Implementação concreta de IGMService usando LangChain + GPT-4o.
"""

import asyncio
import json
import logging
import os
from typing import Any, List

from langchain_core.callbacks.manager import CallbackManagerForRetrieverRun
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from infrastructure.ai.prompts import GM_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Store em memória do histórico de chat, chaveado por session_id
_session_store: dict[str, InMemoryChatMessageHistory] = {}


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatMessageHistory()
    return _session_store[session_id]


class KnowledgeChunksRetriever(BaseRetriever):
    """
    Retriever que consulta a tabela `knowledge_chunks` diretamente via pgvector.
    Substitui o PGVector do LangChain que usava tabelas internas (langchain_pg_embedding)
    em vez da tabela customizada onde o pdf_ingestion salva os embeddings.
    """

    connection_string: str
    top_k: int = 8

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> List[Document]:
        from sqlalchemy import create_engine, text

        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        try:
            query_vector = embeddings.embed_query(query)
            vec_str = "[" + ",".join(str(x) for x in query_vector) + "]"

            engine = create_engine(self.connection_string)
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("""
                            SELECT content, rpg_system
                            FROM knowledge_chunks
                            WHERE embedding IS NOT NULL
                            ORDER BY embedding <=> :vec::vector
                            LIMIT :k
                        """),
                        {"vec": vec_str, "k": self.top_k},
                    ).fetchall()
                return [
                    Document(
                        page_content=row[0],
                        metadata={"rpg_system": row[1] or "unknown"},
                    )
                    for row in rows
                ]
            finally:
                engine.dispose()
        except Exception as exc:
            logger.warning("KnowledgeChunksRetriever falhou: %s", exc)
            return []

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> List[Document]:
        return await asyncio.to_thread(self._get_relevant_documents, query)


def _build_retriever(vector_db_url: str) -> BaseRetriever:
    """Constrói retriever que busca diretamente em knowledge_chunks (pgvector custom)."""
    return KnowledgeChunksRetriever(connection_string=vector_db_url, top_k=8)


def _build_gm_chain(retriever: BaseRetriever) -> RunnableWithMessageHistory:
    """Monta a chain do GM com histórico de conversa e RAG injetado."""
    llm = ChatOpenAI(
        model="gpt-4o",
        streaming=True,
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            GM_SYSTEM_PROMPT + "\n\n## CONTEXTO RECUPERADO DO CONHECIMENTO\n{context}"
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{question}"),
    ])

    def format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    chain = (
        RunnablePassthrough.assign(context=lambda x: format_docs(retriever.invoke(x["question"])) )
        | prompt
        | llm
        | StrOutputParser()
    )

    return RunnableWithMessageHistory(
        chain,
        _get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )


class LangchainGMService:
    """
    Serviço de GM implementado com LangChain + GPT-4o.
    Implementa IGMService via duck typing (Protocol).
    """

    def __init__(self, vector_db_url: str) -> None:
        self._vector_db_url = vector_db_url
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.85,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    async def process_turn(self, session_id: str, question: str) -> str:
        """Processa a ação de um jogador e retorna a resposta bruta do GM."""
        retriever = _build_retriever(self._vector_db_url)
        chain = _build_gm_chain(retriever)

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chain.invoke(
                {"question": question},
                config={"configurable": {"session_id": session_id}},
            ),
        )
        # RunnableWithMessageHistory com StrOutputParser retorna str
        return result if isinstance(result, str) else result.get("answer", "")

    async def generate_opening_narrative(
        self,
        campaign: dict,
        characters: list[dict],
        knowledge_context: str,
    ) -> str:
        """Gera a narrativa épica de abertura de uma campanha."""
        char_lines = "\n".join(
            "- {name}: Level {level} {character_class} {race}{ai}".format(
                name=c.get("name", "?"),
                level=c.get("level", 1),
                character_class=c.get("character_class", "?"),
                race=c.get("race", ""),
                ai=" [IA Companion]" if c.get("char_type") == "ai_companion" else "",
            )
            for c in characters
        )

        prompt = (
            "Você é um Mestre de RPG de mesa abrindo uma nova campanha.\n\n"
            f'Campanha: "{campaign["title"]}"\n'
            f'Sistema: {campaign["rpg_system"]}\n'
            f'Tom: {campaign.get("tone", "heroic")}\n'
            f'Dificuldade: {campaign.get("difficulty", "medium")}\n'
            f'Descrição: {campaign.get("description") or "Uma aventura clássica de fantasia"}\n\n'
            f"Aventureiros presentes:\n{char_lines}\n\n"
            f"Conhecimento do mundo disponível:\n{knowledge_context or 'Sem contexto específico.'}\n\n"
            "Narre a cena de abertura da campanha. Apresente o cenário, crie atmosfera e dê "
            "boas-vindas aos aventureiros pelo nome. Use a tag [IMAGEM:descrição] para sugerir "
            "a cena visual de abertura. Máximo 4 parágrafos. Seja épico, imersivo e envolvente."
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        return str(result.content).strip()

    async def generate_companion_reaction(
        self,
        companion: dict,
        gm_text: str,
        player_action: str,
    ) -> str:
        """Gera a reação in-character de um companheiro IA."""
        personality = (
            companion.get("personality_traits")
            or companion.get("backstory")
            or "Um aventureiro curioso e leal."
        )

        prompt = (
            f"Você é {companion.get('name', 'um companheiro')}, "
            f"um {companion.get('character_class', 'aventureiro')} {companion.get('race', '')}.\n"
            f"Personalidade: {personality}\n\n"
            f"O Mestre acabou de narrar:\n{gm_text[:500]}\n\n"
            f"Um companheiro de grupo fez:\n{player_action[:200]}\n\n"
            "Reaja de forma breve e na voz do seu personagem (máximo 2 frases curtas). "
            "Seja fiel à sua personalidade. Não repita o que o GM disse. "
            "Responda APENAS como seu personagem falaria ou reagiria."
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        return str(result.content).strip()

    async def generate_map_locations(self, campaign: dict) -> list[dict]:
        """Gera 6 locais para o mapa da campanha via GPT-4o."""
        prompt = (
            f"You are a fantasy world builder for a tabletop RPG campaign.\n"
            f'Campaign: "{campaign["title"]}"\n'
            f"System: {campaign['rpg_system']}\n"
            f"Description: {campaign.get('description') or 'A classic adventure'}\n"
            f"Tone: {campaign.get('tone', 'heroic')}\n\n"
            f"Create exactly 6 distinct, interesting locations for this campaign world.\n"
            f"Return ONLY a valid JSON array — no markdown, no extra text — with 6 objects, each containing:\n"
            f'  "id": unique string like "loc_1",\n'
            f'  "name": evocative location name,\n'
            f'  "description": 1-2 sentence description,\n'
            f'  "x": number 5-95 (horizontal position on map),\n'
            f'  "y": number 5-95 (vertical position on map),\n'
            f'  "type": one of "city", "dungeon", "wilderness", "landmark", "unknown",\n'
            f'  "is_current": true only for the first location,\n'
            f'  "discovered": true for the first 2 locations, false for the rest.\n'
            f"Spread locations across the full map area. Vary location types."
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)

    async def generate_ai_companion_archetype(self) -> dict:
        """Gera aleatoriamente um arquétipo de companheiro IA via GPT-4o."""
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import PromptTemplate

        parser = JsonOutputParser()

        prompt = PromptTemplate(
            template=(
                "You are a creative tabletop RPG character designer.\n"
                "Generate a completely original and random RPG companion character archetype.\n"
                "Be creative — avoid clichés, mix unexpected races and classes, invent unique names.\n"
                "Return ONLY a valid JSON object with exactly these fields:\n"
                "  \"name\": unique character name,\n"
                "  \"class\": RPG class (e.g. Fighter, Warlock, Druid, Paladin, Ranger, Monk...),\n"
                "  \"race\": fantasy race (e.g. Tiefling, Gnome, Dragonborn, Aasimar, Tabaxi...),\n"
                "  \"personality\": 1 sentence describing their personality traits,\n"
                "  \"backstory\": 1 sentence describing their origin and motivation.\n"
                "No markdown, no explanation, only the JSON object.\n\n"
                "Random seed for variety: {seed}"
            ),
            input_variables=["seed"],
        )

        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=1.0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        chain = prompt | llm | parser

        import random as _random
        seed = _random.randint(0, 999999)

        result = await asyncio.to_thread(chain.invoke, {"seed": seed})
        return result

    @staticmethod
    def _d20_tier(roll: int) -> str:
        if roll >= 16:
            return "SUCESSO CRÍTICO"
        if roll >= 10:
            return "SUCESSO NORMAL"
        if roll >= 5:
            return "FALHA"
        return "FALHA CRÍTICA"

    async def process_round(
        self,
        session_id: str,
        ordered_actions: list[dict],
        enemy_context: str = "",
        scene_context: str = "",
        loop_context: str = "",
    ) -> list[str]:
        """
        Processa um round completo em ordem de iniciativa.
        Recebe lista de ações ordenadas por d20 e retorna uma resposta do GM por ação ativa.
        O resultado narrativo é determinado pelo tier do d20 de cada personagem.
        enemy_context: string com HP atual dos inimigos vivos (injetada pelo combate).
        scene_context: última narração do GM — estado atual do mundo e posição do grupo.
        loop_context: instrução de intervenção narrativa quando loop detectado.
        """
        # Monta bloco de ações com tier explícito para o LLM
        actions_block = "\n".join(
            f"[{a['initiative_order']}] {a['character_name']} "
            f"(d20={a['d20_roll']} → {self._d20_tier(a['d20_roll'] or 0)}): {a['action_text']}"
            for a in ordered_actions
        )

        scene_block = ""
        if scene_context:
            scene_block = (
                "\n\n## ESTADO ATUAL DA CENA (narração anterior do GM)\n"
                "Esta é a situação do grupo ANTES deste round. Use como base de continuidade:\n"
                f"{scene_context}\n"
            )

        enemy_block = ""
        if enemy_context:
            enemy_block = (
                "\n\n## ESTADO ATUAL DOS INIMIGOS\n"
                "Use os HPs abaixo para narrar de forma precisa:\n"
                f"{enemy_context}\n"
            )

        # Injeta instrução de intervenção narrativa quando loop detectado
        loop_block = loop_context if loop_context else ""

        prompt = (
            "Você é o Mestre de um RPG de mesa. Um novo turno acaba de acontecer.\n"
            "As ações abaixo foram declaradas pelos jogadores e ordenadas pela rolagem de d20 "
            "(maior = age primeiro):\n\n"
            f"{actions_block}"
            f"{scene_block}"
            f"{enemy_block}"
            f"{loop_block}\n\n"
            "## REGRA FUNDAMENTAL — SEQUENCIALIDADE DO ROUND\n"
            "As ações acontecem em SEQUÊNCIA, não em paralelo. O personagem com maior d20 age PRIMEIRO "
            "e o resultado da sua ação ALTERA A CENA para os próximos.\n\n"
            "⚠️ OBRIGATÓRIO: Ao narrar a ação [2], considere o que aconteceu em [1]. "
            "Se o personagem [1] escapou, abriu uma porta, ou mudou o ambiente — o personagem [2] "
            "age nessa NOVA realidade. NUNCA narre [2] como se [1] não tivesse acontecido.\n\n"
            "## COERÊNCIA DE GRUPO\n"
            "Os personagens são um grupo que age no mesmo espaço físico. "
            "Se um personagem deixou uma área de perigo, os outros também estão saindo ou já saíram. "
            "Ações individuais devem refletir a posição e estado ATUAL do grupo, "
            "não uma realidade alternativa onde cada um está isolado.\n\n"
            "## TABELA DE RESULTADO POR D20 — OBRIGATÓRIO\n"
            "O resultado narrativo de CADA ação é determinado pelo valor do d20 do personagem:\n\n"
            "- **d20 = 16–20 (Sucesso Crítico):** A ação é executada com maestria. Além de funcionar "
            "perfeitamente, algo positivo adicional acontece — um aliado é beneficiado, "
            "o grupo ganha vantagem, o personagem encontra algo inesperado e útil. Narre de forma épica.\n\n"
            "- **d20 = 10–15 (Sucesso Normal):** A ação funciona exatamente como planejado. "
            "Narre o resultado de forma direta e satisfatória.\n\n"
            "- **d20 = 5–9 (Falha):** A ação não tem o efeito desejado neste turno. "
            "Narre a falha de forma VARIADA — evite repetir 'tropeça', 'cai no chão' ou 'deixa cair' "
            "se já foram usados neste round. Use alternativas: perde o timing, é distratído por um ruído, "
            "subestima a distância, hesita no momento errado, o ambiente dificulta o movimento, etc. "
            "Sem catástrofe — apenas a ação não funcionou desta vez.\n\n"
            "- **d20 = 1–4 (Falha Crítica):** A ação falha de forma dramática com consequência adicional. "
            "Mesmo aqui, varie: um aliado é afetado, um recurso é perdido, a posição é comprometida, "
            "ou a situação piora de forma inesperada. Evite sempre 'espada cai no chão'.\n\n"
            "IMPORTANTE: Use o d20 indicado após o nome de cada personagem para determinar o resultado. "
            "NÃO ignore o d20 — ele é a lei.\n\n"
            "Para CADA ação, escreva um parágrafo narrando o resultado conforme as regras acima. "
            "Separe cada resposta com '---' numa linha sozinha.\n"
            "Responda APENAS as narrações, uma por ação, na mesma ordem."
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        raw = str(result.content).strip()

        # Divide respostas pelo separador '---'
        parts = [p.strip() for p in raw.split("---") if p.strip()]

        # Garante que temos uma resposta por ação (padding se necessário)
        while len(parts) < len(ordered_actions):
            parts.append("O Mestre observa a cena em silêncio.")

        return parts[:len(ordered_actions)]

    async def generate_companion_action(
        self,
        companion: dict,
        scene_context: str,
    ) -> str:
        """
        Gera a ação que um companheiro IA tomaria neste turno.
        Retorna texto da ação (ex: 'Ataco o goblin com minha espada longa').
        """
        personality = (
            companion.get("personality_traits")
            or companion.get("backstory")
            or "Um aventureiro decidido e leal."
        )
        appearance = companion.get("appearance", "")

        prompt = (
            f"Você é {companion.get('name', 'um companheiro')}, "
            f"um {companion.get('character_class', 'aventureiro')} {companion.get('race', '')}.\n"
            f"Personalidade: {personality}\n"
            f"Aparência: {appearance}\n\n"
            "=== NARRATIVA RECENTE DO MESTRE ===\n"
            f"{scene_context}\n"
            "=== FIM DA NARRATIVA ===\n\n"
            "Com base na narrativa acima, declare em UMA frase curta e direta o que seu personagem "
            "faz AGORA. Use a primeira pessoa. Seja coerente com sua personalidade, classe e "
            "com o que está acontecendo na cena — se for exploração, explore; se for diálogo, "
            "interaja; se for combate, lute. Não invente inimigos ou situações que não existam "
            "na narrativa.\n"
            "Responda APENAS a declaração de ação, sem explicações adicionais."
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        return str(result.content).strip()

    async def generate_character_8bit(self, description: str) -> dict:
        """Gera conceito de personagem 8-bit a partir de uma descrição."""
        prompt = (
            "You are a prompt engineer for 8-bit pixel art RPG characters. "
            "Convert the short description below into a compact character concept and a DALL-E prompt. "
            "Return ONLY valid JSON with these fields: name, race, class, alignment, background, "
            "appearance, backstory, pixel_art_prompt. "
            "Do not add any explanation, markdown or extra text.\n\n"
            f"Description: {description}"
        )

        result = await asyncio.to_thread(self._llm.invoke, prompt)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            trimmed = raw[raw.find("{"):raw.rfind("}") + 1]
            return json.loads(trimmed)
