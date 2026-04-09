"""
Casos de uso do sistema de rounds coletivos.

Fluxo:
  StartRoundUseCase      → cria round, solicita ações dos AI companions
  SubmitActionUseCase    → recebe ação de um jogador; quando todos submeteram,
                           dispara ResolveRoundUseCase automaticamente
  ResolveRoundUseCase    → rola d20, ordena por iniciativa, persiste, broadcast
  ProcessGMTurnUseCase   → envia ações ao GM em ordem; persiste respostas;
                           encerra o round
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from application.round.dtos import (
    InitiativeEntryDTO,
    RoundActionResultDTO,
    RoundResolutionDTO,
    RoundStateDTO,
    StartRoundDTO,
    SubmitActionDTO,
    SubmitActionResultDTO,
)
from domain.gm.ports import IGMService, IKnowledgeRetriever
from domain.round.entity import Round, RoundAction
from domain.round.repository import IRoundRepository
from domain.round.value_objects import RoundStatus
from domain.session.entity import SessionMessage
from domain.session.repository import IMessageRepository, ISessionRepository
from domain.session.value_objects import MessageRole
from infrastructure.ai.state_parser import parse_gm_response
from infrastructure.external.image_client import CharacterServiceClient

logger = logging.getLogger(__name__)


class StartRoundUseCase:
    """
    Inicia um novo round coletivo para a sessão.

    1. Valida que não existe round ativo.
    2. Cria Round com status 'collecting'.
    3. Broadcast 'round_started' para todos os jogadores.
    4. Dispara geração de ações para AI companions em background.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        session_repo: ISessionRepository,
        character_client: CharacterServiceClient,
        gm_service: IGMService,
        ws_broadcast_fn=None,
    ) -> None:
        self._rounds = round_repo
        self._sessions = session_repo
        self._characters = character_client
        self._gm = gm_service
        self._ws_broadcast = ws_broadcast_fn

    async def execute(self, dto: StartRoundDTO) -> RoundStateDTO:
        # Valida sessão
        session = await self._sessions.get_by_id(dto.session_id)
        if session is None:
            raise ValueError(f"Sessão {dto.session_id} não encontrada.")

        # Garante que não há round ativo
        existing = await self._rounds.get_active_by_session(dto.session_id)
        if existing is not None:
            raise ValueError(
                f"Já existe um round ativo (round {existing.round_number}, "
                f"status '{existing.status.value}') para esta sessão."
            )

        # Número do próximo round
        last_number = await self._rounds.get_last_round_number(dto.session_id)
        round_ = Round.create(session_id=dto.session_id, round_number=last_number + 1)
        await self._rounds.save(round_)

        # Lista todos os personagens da campanha
        party = await self._characters.list_campaign_characters(str(session.campaign_id))
        human_players = [c for c in party if c.get("char_type") != "ai_companion"]
        ai_companions = [c for c in party if c.get("char_type") == "ai_companion"]
        expected_count = len(party)

        # Broadcast: informa todos que o round começou
        if self._ws_broadcast:
            asyncio.create_task(
                self._ws_broadcast(
                    str(dto.session_id),
                    {
                        "type": "round_started",
                        "payload": {
                            "round_id": str(round_.id),
                            "round_number": round_.round_number,
                            "expected_players": len(human_players),
                            "timeout_seconds": 60,
                        },
                    },
                )
            )

        # Gera ações dos AI companions em background (não bloqueia os humanos)
        if ai_companions:
            asyncio.create_task(
                self._generate_ai_actions(round_, ai_companions, dto, expected_count)
            )

        return RoundStateDTO(
            round_id=str(round_.id),
            session_id=str(dto.session_id),
            round_number=round_.round_number,
            status=round_.status.value,
            submitted_count=0,
            expected_count=expected_count,
        )

    async def _generate_ai_actions(
        self,
        round_: Round,
        companions: list[dict],
        dto: StartRoundDTO,
        expected_count: int,
    ) -> None:
        """Gera e persiste ações de AI companions; se todos submeteram, resolve o round."""
        from infrastructure.database.connection import AsyncSessionLocal
        from infrastructure.repositories.round_repository import RoundRepository

        session_str = str(dto.session_id)
        scene_context = f"Round {round_.round_number} da sessão."

        for companion in companions:
            try:
                action_text = await self._gm.generate_companion_action(
                    companion=companion,
                    scene_context=scene_context,
                )
                action = RoundAction.create(
                    round_id=round_.id,
                    session_id=dto.session_id,
                    character_name=companion.get("name", "Companion"),
                    is_ai=True,
                    is_pass=False,
                    character_id=UUID(str(companion["id"])) if companion.get("id") else None,
                    action_text=action_text,
                )
                async with AsyncSessionLocal() as db:
                    repo = RoundRepository(db)
                    await repo.save_action(action)
                    await db.commit()

                if self._ws_broadcast:
                    await self._ws_broadcast(
                        session_str,
                        {
                            "type": "action_submitted",
                            "payload": {
                                "character_name": companion.get("name"),
                                "is_pass": False,
                                "is_ai": True,
                                "action_text": action_text,
                            },
                        },
                    )
            except Exception as exc:
                logger.warning(
                    "Falha ao gerar ação do companion %s: %s",
                    companion.get("name"),
                    exc,
                )

        # Verifica se agora todos submeteram (AI pode ter sido o último)
        async with AsyncSessionLocal() as db:
            repo = RoundRepository(db)
            current_round = await repo.get_by_id(round_.id)
            if current_round and current_round.all_submitted(expected_count):
                submit_uc = SubmitActionUseCase.__new__(SubmitActionUseCase)
                submit_uc._rounds = repo
                submit_uc._sessions = None
                submit_uc._characters = self._characters
                submit_uc._ws_broadcast = self._ws_broadcast
                await submit_uc._trigger_resolution(current_round, dto.session_id, db)
                await db.commit()


class SubmitActionUseCase:
    """
    Recebe a ação de um jogador para o round atual.

    1. Valida que o round está em 'collecting'.
    2. Valida que o personagem ainda não submeteu.
    3. Persiste a RoundAction.
    4. Broadcast 'action_submitted' (sem revelar o texto da ação).
    5. Se todos submeteram → dispara ResolveRoundUseCase.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        session_repo: ISessionRepository,
        character_client: CharacterServiceClient,
        ws_broadcast_fn=None,
    ) -> None:
        self._rounds = round_repo
        self._sessions = session_repo
        self._characters = character_client
        self._ws_broadcast = ws_broadcast_fn

    async def execute(self, dto: SubmitActionDTO) -> SubmitActionResultDTO:
        # Busca round ativo
        round_ = await self._rounds.get_active_by_session(dto.session_id)
        if round_ is None:
            raise ValueError("Não há round ativo para esta sessão.")

        if round_.status != RoundStatus.COLLECTING:
            raise ValueError(
                f"O round está em '{round_.status.value}', não é mais possível submeter ações."
            )

        if round_.character_already_submitted(dto.character_id):
            raise ValueError(
                f"O personagem {dto.character_name} já submeteu uma ação neste round."
            )

        # Cria e persiste a ação
        action = RoundAction.create(
            round_id=round_.id,
            session_id=dto.session_id,
            character_name=dto.character_name,
            is_ai=dto.is_ai,
            is_pass=dto.is_pass,
            player_id=dto.player_id,
            character_id=dto.character_id,
            action_text=dto.action_text,
        )
        await self._rounds.save_action(action)
        round_.actions.append(action)

        # Broadcast: personagem submeteu
        # Para AI companions revelamos o texto imediatamente; para humanos mantemos oculto até o initiative board
        if self._ws_broadcast:
            asyncio.create_task(
                self._ws_broadcast(
                    str(dto.session_id),
                    {
                        "type": "action_submitted",
                        "payload": {
                            "character_name": dto.character_name,
                            "is_pass": dto.is_pass,
                            "is_ai": dto.is_ai,
                            "action_text": dto.action_text if dto.is_ai else None,
                        },
                    },
                )
            )

        # Verifica se todos submeteram
        party = await self._characters.list_campaign_characters(str(dto.campaign_id))
        expected_count = len(party)
        all_done = round_.all_submitted(expected_count)

        if all_done:
            await self._trigger_resolution(round_, dto.session_id, None)

        return SubmitActionResultDTO(
            action_id=str(action.id),
            round_id=str(round_.id),
            round_number=round_.round_number,
            submitted_count=len(round_.actions),
            expected_count=expected_count,
            all_submitted=all_done,
        )

    async def _trigger_resolution(self, round_: Round, session_id: UUID, db) -> None:
        """Dispara a resolução do round quando todos submeteram."""
        from infrastructure.database.connection import AsyncSessionLocal

        async def _run():
            try:
                async with AsyncSessionLocal() as new_db:
                    from infrastructure.repositories.round_repository import RoundRepository
                    repo = RoundRepository(new_db)
                    resolve_uc = ResolveRoundUseCase(
                        round_repo=repo,
                        ws_broadcast_fn=self._ws_broadcast,
                    )
                    await resolve_uc.execute(round_.id)
                    await new_db.commit()
            except Exception as exc:
                logger.error("Falha na resolução do round %s: %s", round_.id, exc)

        asyncio.create_task(_run())


class ResolveRoundUseCase:
    """
    Fase de resolução: rola d20 para cada ação e ordena por iniciativa.

    1. Transita round para 'resolving'.
    2. Rola d20 para cada ação.
    3. Persiste os rolls.
    4. Broadcast 'initiative_board' com a ordem revelada.
    5. Dispara ProcessGMTurnUseCase.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        ws_broadcast_fn=None,
    ) -> None:
        self._rounds = round_repo
        self._ws_broadcast = ws_broadcast_fn

    async def execute(self, round_id: UUID) -> RoundResolutionDTO:
        round_ = await self._rounds.get_by_id(round_id)
        if round_ is None:
            raise ValueError(f"Round {round_id} não encontrado.")

        # Transita para resolving
        round_.start_resolving()
        await self._rounds.save(round_)

        # Rola iniciativa e ordena
        ordered = round_.roll_initiative()

        # Persiste rolls em cada ação
        for action in ordered:
            await self._rounds.update_action(action)

        await self._rounds.save(round_)

        # Monta initiative board para broadcast
        board = [
            InitiativeEntryDTO(
                character_name=a.character_name,
                is_ai=a.is_ai,
                d20_roll=a.d20_roll or 0,
                initiative_order=a.initiative_order or 0,
                action_text=a.action_text,
                is_pass=a.is_pass,
                character_id=str(a.character_id) if a.character_id else None,
            )
            for a in ordered
        ]

        if self._ws_broadcast:
            asyncio.create_task(
                self._ws_broadcast(
                    str(round_.session_id),
                    {
                        "type": "initiative_board",
                        "payload": {
                            "round_number": round_.round_number,
                            "initiative": [
                                {
                                    "character_name": e.character_name,
                                    "is_ai": e.is_ai,
                                    "d20_roll": e.d20_roll,
                                    "initiative_order": e.initiative_order,
                                    "action_text": e.action_text,
                                    "is_pass": e.is_pass,
                                }
                                for e in board
                            ],
                        },
                    },
                )
            )

        dto = RoundResolutionDTO(
            round_id=str(round_.id),
            round_number=round_.round_number,
            initiative_board=board,
        )

        # Dispara GM processing em background
        asyncio.create_task(self._dispatch_gm(round_id))

        return dto

    async def _dispatch_gm(self, round_id: UUID) -> None:
        from infrastructure.database.connection import AsyncSessionLocal
        from infrastructure.repositories.round_repository import RoundRepository
        from infrastructure.repositories.session_repository import MessageRepository
        import os
        from infrastructure.ai.langchain_gm_service import LangchainGMService
        from infrastructure.external.knowledge_client import KnowledgeClient

        vector_db_url = os.getenv(
            "VECTOR_DB_URL",
            "postgresql+psycopg2://rpg_user:change_me_strong_password@postgres:5432/rpg_platform",
        )

        try:
            async with AsyncSessionLocal() as db:
                repo = RoundRepository(db)
                msg_repo = MessageRepository(db)
                gm = LangchainGMService(vector_db_url)
                knowledge = KnowledgeClient()
                process_uc = ProcessGMTurnUseCase(
                    round_repo=repo,
                    message_repo=msg_repo,
                    gm_service=gm,
                    knowledge_retriever=knowledge,
                    ws_broadcast_fn=self._ws_broadcast,
                )
                await process_uc.execute(round_id)
                await db.commit()
        except Exception as exc:
            logger.error("Falha no ProcessGMTurnUseCase para round %s: %s", round_id, exc)


class ProcessGMTurnUseCase:
    """
    Fase de GM: processa as ações em ordem de iniciativa.

    1. Envia todas as ações ao GM via process_round().
    2. Para cada resposta, parseia tags [ROLAGEM:], [ESTADO:], [IMAGEM:].
    3. Persiste respostas em round_actions e session_messages.
    4. Broadcast 'gm_round_response' por ação.
    5. Transita round para 'completed'.
    6. Broadcast 'round_completed'.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        message_repo: IMessageRepository,
        gm_service: IGMService,
        knowledge_retriever: IKnowledgeRetriever,
        ws_broadcast_fn=None,
    ) -> None:
        self._rounds = round_repo
        self._messages = message_repo
        self._gm = gm_service
        self._knowledge = knowledge_retriever
        self._ws_broadcast = ws_broadcast_fn

    async def execute(self, round_id: UUID) -> list[RoundActionResultDTO]:
        round_ = await self._rounds.get_by_id(round_id)
        if round_ is None:
            raise ValueError(f"Round {round_id} não encontrado.")

        if round_.status != RoundStatus.GM_PROCESSING:
            raise ValueError(
                f"Round está em '{round_.status.value}', esperado 'gm_processing'."
            )

        # Knowledge gate
        gate_open = await self._knowledge.check_gate()
        if not gate_open:
            raise PermissionError("GM bloqueado: banco de conhecimento vazio.")

        # Prepara ações ativas (não-passe) em ordem de iniciativa
        active_actions = [a for a in round_.sorted_by_initiative() if not a.is_pass]

        if not active_actions:
            # Todos passaram — narra brevemente e encerra
            round_.complete()
            await self._rounds.save(round_)
            if self._ws_broadcast:
                await self._ws_broadcast(
                    str(round_.session_id),
                    {"type": "round_completed", "payload": {"round_number": round_.round_number}},
                )
            return []

        # Chama o GM com todas as ações de uma vez
        ordered_payload = [
            {
                "character_name": a.character_name,
                "action_text": a.action_text,
                "d20_roll": a.d20_roll,
                "initiative_order": a.initiative_order,
                "is_ai": a.is_ai,
            }
            for a in active_actions
        ]
        gm_responses = await self._gm.process_round(
            session_id=str(round_.session_id),
            ordered_actions=ordered_payload,
        )

        results: list[RoundActionResultDTO] = []

        for i, action in enumerate(active_actions):
            raw_response = gm_responses[i] if i < len(gm_responses) else ""
            parsed = parse_gm_response(raw_response)
            clean_text = parsed["clean_text"]
            roll_results = parsed["roll_results"]

            # Determina se GM rolou dado
            gm_rolled = len(roll_results) > 0
            outcome_roll = roll_results[0].result if gm_rolled else None

            # Atualiza ação com resposta do GM
            action.record_gm_outcome(
                gm_response=clean_text,
                gm_rolled_dice=gm_rolled,
                outcome_roll=outcome_roll,
            )
            await self._rounds.update_action(action)

            # Persiste como mensagem de sessão (histórico)
            gm_msg = SessionMessage.create(
                session_id=round_.session_id,
                role=MessageRole.GM,
                content=raw_response,
            )
            await self._messages.save(gm_msg)

            # Broadcast por ação
            if self._ws_broadcast:
                asyncio.create_task(
                    self._ws_broadcast(
                        str(round_.session_id),
                        {
                            "type": "gm_round_response",
                            "payload": {
                                "initiative_order": action.initiative_order,
                                "character_name": action.character_name,
                                "action_text": action.action_text,
                                "gm_text": clean_text,
                                "roll_results": [
                                    {"expr": r.expr, "result": r.result}
                                    for r in roll_results
                                ],
                                "gm_rolled_dice": gm_rolled,
                                "outcome_roll": outcome_roll,
                            },
                        },
                    )
                )

            results.append(
                RoundActionResultDTO(
                    character_name=action.character_name,
                    initiative_order=action.initiative_order or 0,
                    action_text=action.action_text,
                    is_pass=action.is_pass,
                    gm_response=clean_text,
                    gm_rolled_dice=gm_rolled,
                    outcome_roll=outcome_roll,
                    d20_roll=action.d20_roll or 0,
                )
            )

        # Encerra o round
        round_.complete()
        await self._rounds.save(round_)

        if self._ws_broadcast:
            asyncio.create_task(
                self._ws_broadcast(
                    str(round_.session_id),
                    {
                        "type": "round_completed",
                        "payload": {"round_number": round_.round_number},
                    },
                )
            )

        return results
