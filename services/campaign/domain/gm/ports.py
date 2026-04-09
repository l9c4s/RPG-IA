from typing import Protocol


class IGMService(Protocol):
    """
    Porta de saída para o serviço de IA do Game Master.
    O domínio depende desta interface; a infra (LangChain) a implementa.
    """

    async def process_turn(self, session_id: str, question: str) -> str:
        """
        Processa a ação de um jogador e retorna a resposta bruta do GM.
        A resposta pode conter tags [ROLAGEM:], [ESTADO:], [IMAGEM:].
        """
        ...

    async def generate_opening_narrative(
        self,
        campaign: dict,
        characters: list[dict],
        knowledge_context: str,
    ) -> str:
        """Gera a narrativa de abertura de uma campanha."""
        ...

    async def generate_companion_reaction(
        self,
        companion: dict,
        gm_text: str,
        player_action: str,
    ) -> str:
        """Gera a reação in-character de um companheiro IA."""
        ...

    async def generate_map_locations(self, campaign: dict) -> list[dict]:
        """Gera 6 locais para o mapa da campanha. Retorna lista de dicts."""
        ...

    async def generate_character_8bit(self, description: str) -> dict:
        """Gera conceito de personagem 8-bit a partir de uma descrição."""
        ...

    async def generate_ai_companion_archetype(self) -> dict:
        """Gera aleatoriamente um arquétipo de companheiro IA (name, class, race, personality, backstory)."""
        ...

    async def process_round(
        self,
        session_id: str,
        ordered_actions: list[dict],
    ) -> list[str]:
        """
        Processa um round completo em ordem de iniciativa.

        Recebe lista de dicts: [{character_name, action_text, d20_roll, initiative_order, is_pass}]
        Retorna lista de respostas do GM (uma por ação ativa, na mesma ordem).
        O GM pode incluir [ROLAGEM:] se decidir rolar dado para o outcome da ação.
        Ações de passe são ignoradas (GM não narra).
        """
        ...

    async def generate_companion_action(
        self,
        companion: dict,
        scene_context: str,
    ) -> str:
        """
        Gera a ação que um companheiro IA tomaria neste turno.
        Retorna texto da ação (ex: 'Ataca o goblin com sua espada').
        """
        ...


class IKnowledgeRetriever(Protocol):
    """
    Porta de saída para o serviço de conhecimento (RAG).
    """

    async def check_gate(self) -> bool:
        """
        Verifica se o banco de conhecimento tem chunks suficientes.
        Retorna True se o GM está liberado para jogar.
        """
        ...

    async def get_context(self, query: str) -> str:
        """
        Busca e retorna um contexto RAG para a query fornecida.
        Retorna string vazia em caso de falha.
        """
        ...
