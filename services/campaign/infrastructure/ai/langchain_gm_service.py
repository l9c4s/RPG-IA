"""
Implementação concreta de IGMService usando LangChain + GPT-4o.
"""

import asyncio
import json
import os

from langchain_core.chat_history import InMemoryChatMessageHistory
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
from langchain_community.vectorstores import PGVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from infrastructure.ai.prompts import GM_SYSTEM_PROMPT

# Store em memória do histórico de chat, chaveado por session_id
_session_store: dict[str, InMemoryChatMessageHistory] = {}


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatMessageHistory()
    return _session_store[session_id]


def _build_retriever(vector_db_url: str) -> BaseRetriever:
    """Constrói um PGVector retriever que busca em knowledge_chunks."""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    store = PGVector(
        connection_string=vector_db_url,
        embedding_function=embeddings,
        collection_name="knowledge_chunks",
    )
    return store.as_retriever(search_kwargs={"k": 8})


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
        RunnablePassthrough.assign(
            context=lambda x: format_docs(retriever.invoke(x["question"]))
        )
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
