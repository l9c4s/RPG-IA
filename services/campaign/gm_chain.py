import os
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.schema import BaseRetriever
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from prompts import GM_SYSTEM_PROMPT


def build_gm_chain(retriever: BaseRetriever) -> ConversationalRetrievalChain:
    """
    Build and return a ConversationalRetrievalChain configured as an AI Game Master.

    Args:
        retriever: A LangChain-compatible retriever that searches the RPG knowledge base
                   (knowledge_chunks from the ingestion service).

    Returns:
        A ready-to-use ConversationalRetrievalChain with GPT-4o, windowed memory, and
        the GM system prompt injected via a custom combine-docs prompt.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        streaming=True,
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    memory = ConversationBufferWindowMemory(
        k=10,
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )

    # Build a QA prompt that injects the GM system prompt together with
    # the retrieved context and the conversation history.
    combine_docs_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(
                GM_SYSTEM_PROMPT
                + "\n\n## CONTEXTO RECUPERADO DO CONHECIMENTO\n{context}"
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": combine_docs_prompt},
        verbose=False,
    )

    return chain


def get_embeddings() -> OpenAIEmbeddings:
    """Return an OpenAIEmbeddings instance for encoding query vectors."""
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
