import asyncio
import os
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.retrievers import BaseRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from prompts import GM_SYSTEM_PROMPT

# In-memory store for chat histories keyed by session_id
_session_store: dict = {}


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatMessageHistory()
    return _session_store[session_id]


def build_gm_chain(retriever: BaseRetriever):
    """
    Build and return a RunnableWithMessageHistory chain configured as an AI Game Master.
    Compatible with langchain >= 1.0.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        streaming=True,
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(
                GM_SYSTEM_PROMPT + "\n\n## CONTEXTO RECUPERADO DO CONHECIMENTO\n{context}"
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )

    def format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    chain = (
        RunnablePassthrough.assign(context=lambda x: format_docs(retriever.invoke(x["question"])))
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


async def generate_opening_narrative(
    campaign: dict,
    characters: list[dict],
    knowledge_context: str,
) -> str:
    """
    Generate the campaign opening narration using GPT-4o.

    Parameters
    ----------
    campaign : dict with keys title, rpg_system, description, tone, difficulty
    characters : list of character dicts (name, character_class, race, char_type, …)
    knowledge_context : pre-retrieved RAG context (may be empty string)
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.85,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

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

    result = await asyncio.to_thread(llm.invoke, prompt)
    return str(result.content).strip()


async def generate_companion_reaction(
    companion: dict,
    gm_text: str,
    player_action: str,
) -> str:
    """
    Generate a short in-character reaction from an AI companion.

    Parameters
    ----------
    companion : character dict (name, character_class, race, personality_traits, backstory, …)
    gm_text   : the GM's last narration (first 500 chars used)
    player_action : the human player's last action (first 200 chars used)
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    personality = (
        companion.get("personality_traits")
        or companion.get("backstory")
        or "Um aventureiro curioso e leal."
    )

    prompt = (
        f"Você é {companion.get('name', 'um companheiro')}, "
        f"um {companion.get('character_class', 'aventureiro')} {companion.get('race', '')}.\\n"
        f"Personalidade: {personality}\\n\\n"
        f"O Mestre acabou de narrar:\\n{gm_text[:500]}\\n\\n"
        f"Um companheiro de grupo fez:\\n{player_action[:200]}\\n\\n"
        "Reaja de forma breve e na voz do seu personagem (máximo 2 frases curtas). "
        "Seja fiel à sua personalidade. Não repita o que o GM disse. "
        "Responda APENAS como seu personagem falaria ou reagiria."
    )

    result = await asyncio.to_thread(llm.invoke, prompt)
    return str(result.content).strip()


def get_embeddings() -> OpenAIEmbeddings:
    """Return an OpenAIEmbeddings instance for encoding query vectors."""
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
