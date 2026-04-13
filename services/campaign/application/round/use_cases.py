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
from infrastructure.ai.loop_detector import NarrativeLoopDetector
from infrastructure.ai.state_parser import parse_gm_response
from infrastructure.external.image_client import CharacterServiceClient

logger = logging.getLogger(__name__)


def _d20_tier(roll: int) -> str:
    if roll >= 16:
        return "SUCESSO CRÍTICO"
    if roll >= 10:
        return "SUCESSO NORMAL"
    if roll >= 5:
        return "FALHA"
    return "FALHA CRÍTICA"


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
        from infrastructure.repositories.session_repository import MessageRepository

        session_str = str(dto.session_id)

        # Busca as últimas 5 mensagens do GM para contexto real da cena
        gm_texts: list[str] = []
        scene_context = f"Round {round_.round_number} da sessão."
        try:
            async with AsyncSessionLocal() as db:
                msg_repo = MessageRepository(db)
                all_messages = await msg_repo.list_by_session(dto.session_id)
                gm_texts = [m.content for m in all_messages if m.role.value == "gm"][-5:]
                if gm_texts:
                    scene_context = "\n\n".join(gm_texts)
                else:
                    scene_context = f"Round {round_.round_number} da sessão. A aventura está começando."
        except Exception:
            pass

        # Detecta loop e monta hint anti-loop para companions
        anti_loop_hint = ""
        try:
            loop_result = NarrativeLoopDetector().analyze(gm_texts)
            if loop_result.is_loop:
                anti_loop_hint = NarrativeLoopDetector().build_companion_anti_loop_hint(gm_texts)
        except Exception:
            pass

        for companion in companions:
            try:
                enriched_context = scene_context + anti_loop_hint
                action_text = await self._gm.generate_companion_action(
                    companion=companion,
                    scene_context=enriched_context,
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
    4. Persiste como SessionMessage para aparecer no histórico após reload.
    5. Broadcast 'action_submitted' (sem revelar o texto da ação).
    6. Se todos submeteram → dispara ResolveRoundUseCase.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        session_repo: ISessionRepository,
        character_client: CharacterServiceClient,
        message_repo: IMessageRepository | None = None,
        ws_broadcast_fn=None,
    ) -> None:
        self._rounds = round_repo
        self._sessions = session_repo
        self._characters = character_client
        self._messages = message_repo
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

        # Persiste como SessionMessage para aparecer no histórico após reload
        if self._messages and dto.action_text and not dto.is_pass:
            role = MessageRole.AI_COMPANION if dto.is_ai else MessageRole.PLAYER
            player_msg = SessionMessage.create(
                session_id=dto.session_id,
                role=role,
                content=dto.action_text,
                character_id=dto.character_id,
            )
            await self._messages.save(player_msg)

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
                            "character_id": str(dto.character_id) if dto.character_id else None,
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
        from infrastructure.repositories.campaign_repository import CampaignRepository
        from infrastructure.repositories.round_repository import RoundRepository
        from infrastructure.repositories.session_repository import MessageRepository, SessionRepository
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
                session_repo = SessionRepository(db)
                campaign_repo = CampaignRepository(db)
                from infrastructure.repositories.combat_repository import CombatRepository
                combat_repo = CombatRepository(db)
                gm = LangchainGMService(vector_db_url)
                knowledge = KnowledgeClient()
                from infrastructure.external.image_client import CharacterServiceClient
                process_uc = ProcessGMTurnUseCase(
                    round_repo=repo,
                    message_repo=msg_repo,
                    gm_service=gm,
                    knowledge_retriever=knowledge,
                    ws_broadcast_fn=self._ws_broadcast,
                    character_client=CharacterServiceClient(),
                    campaign_repo=campaign_repo,
                    session_repo=session_repo,
                    combat_repo=combat_repo,
                )
                await process_uc.execute(round_id)
                await db.commit()
        except Exception as exc:
            logger.error("Falha no ProcessGMTurnUseCase para round %s: %s", round_id, exc)


class ProcessGMTurnUseCase:
    """
    Fase de GM: processa as ações em ordem de iniciativa.

    1. Envia todas as ações ao GM via process_round() com contexto de inimigos.
    2. Para cada resposta, parseia tags [ROLAGEM:], [ESTADO:], [NPC:], [IMAGEM:],
       [INIMIGOS:], [DANO_INIMIGO:], [ATAQUE_INIMIGO:], [ITEM_GANHO:], [LOCAL:].
    3. Persiste respostas em round_actions e session_messages.
    4. Salva gm_memory, campaign_state, npcs, dice_rolls, locations.
    5. Processa combate: cria encounters, spawna inimigos, aplica dano, loga eventos.
    6. Broadcast 'gm_round_response' por ação.
    7. Salva campaign_snapshot ao encerrar o round.
    8. Broadcast 'round_completed'.
    """

    def __init__(
        self,
        round_repo: IRoundRepository,
        message_repo: IMessageRepository,
        gm_service: IGMService,
        knowledge_retriever: IKnowledgeRetriever,
        ws_broadcast_fn=None,
        character_client=None,
        campaign_repo=None,
        session_repo: ISessionRepository | None = None,
        combat_repo=None,
    ) -> None:
        self._rounds = round_repo
        self._messages = message_repo
        self._gm = gm_service
        self._knowledge = knowledge_retriever
        self._ws_broadcast = ws_broadcast_fn
        self._characters = character_client
        self._campaigns = campaign_repo
        self._sessions = session_repo
        self._combat = combat_repo

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

        # Busca estado atual dos inimigos para injetar no prompt do GM
        enemy_context = ""
        if self._combat:
            try:
                encounter = await self._combat.get_active_encounter(round_.session_id)
                if encounter:
                    alive = await self._combat.get_alive_enemies(encounter.id)
                    enemy_context = self._combat.format_enemies_for_gm(alive)
            except Exception as exc:
                logger.warning("Falha ao buscar contexto de inimigos: %s", exc)

        # Busca as últimas mensagens do GM para contexto de cena e detecção de loop
        scene_context = ""
        loop_context = ""
        try:
            recent_gm_messages = await self._messages.list_by_session(round_.session_id)
            gm_texts = [
                m.content for m in recent_gm_messages
                if m.role.value == "gm"
            ][-6:]

            # Cena atual = última mensagem GM (para o GM saber onde o grupo está)
            if gm_texts:
                scene_context = gm_texts[-1]

            # Detecta loop narrativo
            loop_result = NarrativeLoopDetector().analyze(gm_texts)
            if loop_result.is_loop:
                loop_context = loop_result.loop_context
                logger.warning(
                    "Loop narrativo detectado na sessão %s — tema: '%s' (overlap %.0f%%, %d msgs)",
                    round_.session_id,
                    loop_result.detected_theme,
                    loop_result.avg_overlap * 100,
                    loop_result.consecutive_rounds,
                )
        except Exception as exc:
            logger.warning("Falha ao detectar loop narrativo: %s", exc)

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
            enemy_context=enemy_context,
            scene_context=scene_context,
            loop_context=loop_context,
        )

        results: list[RoundActionResultDTO] = []

        for i, action in enumerate(active_actions):
            raw_response = gm_responses[i] if i < len(gm_responses) else ""
            parsed = parse_gm_response(raw_response)
            clean_text = parsed["clean_text"]
            roll_results = parsed["roll_results"]
            state_updates = parsed["state_updates"]
            npcs_introduced = parsed.get("npcs_introduced", [])

            # Persiste d20 de iniciativa
            if action.d20_roll is not None:
                try:
                    await self._rounds.save_dice_roll(
                        session_id=round_.session_id,
                        character_id=action.character_id,
                        roll_type="initiative",
                        dice_expr="1d20",
                        result=action.d20_roll,
                        breakdown={"tier": _d20_tier(action.d20_roll)},
                    )
                except Exception as exc:
                    logger.warning("Falha ao salvar d20 de %s: %s", action.character_name, exc)

            # Persiste rolls gerados pelo GM ([ROLAGEM:] tags)
            for roll in roll_results:
                try:
                    await self._rounds.save_dice_roll(
                        session_id=round_.session_id,
                        character_id=action.character_id,
                        roll_type="action",
                        dice_expr=roll.expr,
                        result=roll.result,
                        breakdown={"breakdown": getattr(roll, "breakdown", None)},
                    )
                except Exception as exc:
                    logger.warning("Falha ao salvar roll do GM (%s): %s", roll.expr, exc)

            # Aplica mudanças de estado [ESTADO:campo=valor] ao personagem da ação
            if state_updates and action.character_id and self._characters:
                for su in state_updates:
                    await self._characters.apply_state_update(
                        str(action.character_id), su.field, su.value
                    )

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

            # Salva memória narrativa do GM
            if self._campaigns and self._sessions and clean_text:
                try:
                    session = await self._sessions.get_by_id(round_.session_id)
                    if session:
                        await self._campaigns.save_gm_memory(
                            campaign_id=session.campaign_id,
                            content=clean_text[:1000],
                            memory_type="narrative",
                            importance=5,
                        )
                except Exception as exc:
                    logger.warning("Falha ao salvar gm_memory: %s", exc)

            # Persiste NPCs introduzidos via tag [NPC:]
            if self._campaigns and self._sessions and npcs_introduced:
                try:
                    session = await self._sessions.get_by_id(round_.session_id)
                    if session:
                        for npc in npcs_introduced:
                            await self._campaigns.save_npc(
                                campaign_id=session.campaign_id,
                                name=npc["name"],
                                description=npc.get("description"),
                            )
                except Exception as exc:
                    logger.warning("Falha ao salvar NPCs: %s", exc)

            # Persiste locations introduzidas via tag [LOCAL:]
            locations_introduced = parsed.get("locations_introduced", [])
            if self._campaigns and self._sessions and locations_introduced:
                try:
                    session = await self._sessions.get_by_id(round_.session_id)
                    if session:
                        for loc in locations_introduced:
                            await self._campaigns.save_location(
                                campaign_id=session.campaign_id,
                                name=loc["name"],
                                description=loc.get("description"),
                            )
                except Exception as exc:
                    logger.warning("Falha ao salvar locations: %s", exc)

            # Processa tags de combate
            if self._combat:
                await self._handle_combat_tags(
                    parsed=parsed,
                    session_id=round_.session_id,
                    round_id=round_.id,
                    action=action,
                )

            # Notifica o frontend que o estado da sessão pode ter mudado.
            # O frontend busca GET /sessions/{id}/state para obter o estado atual.
            if self._ws_broadcast:
                asyncio.create_task(
                    self._ws_broadcast(
                        str(round_.session_id),
                        {"type": "session_state_changed", "payload": {}},
                    )
                )

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
                                "d20_roll": action.d20_roll,
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

        # Atualiza campaign_state e salva snapshot ao fim do round
        if self._campaigns and self._sessions and results:
            try:
                session = await self._sessions.get_by_id(round_.session_id)
                if session:
                    last_scene = results[-1].gm_response or ""
                    await self._campaigns.upsert_campaign_state(
                        campaign_id=session.campaign_id,
                        current_scene=last_scene[:500] if last_scene else None,
                    )
                    await self._campaigns.save_snapshot(
                        campaign_id=session.campaign_id,
                        session_id=round_.session_id,
                        state_data={
                            "round_number": round_.round_number,
                            "actions": [
                                {
                                    "character": r.character_name,
                                    "action": r.action_text,
                                    "gm_response": (r.gm_response or "")[:200],
                                    "d20_roll": r.d20_roll,
                                }
                                for r in results
                            ],
                        },
                    )
            except Exception as exc:
                logger.warning("Falha ao salvar campaign_state/snapshot: %s", exc)

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

    async def _handle_combat_tags(
        self,
        parsed: dict,
        session_id: UUID,
        round_id: UUID,
        action,
    ) -> None:
        """
        Processa as tags de combate extraídas do parse do GM:
          [INIMIGOS:]      → cria encounter se necessário + spawna inimigos
          [DANO_INIMIGO:]  → aplica dano ao inimigo + loga evento
          [ATAQUE_INIMIGO:] → loga evento de ataque + aplica dano ao jogador
          [ITEM_GANHO:]    → loga evento de item
        Falhas nunca propagam — só logam warning.
        """
        new_enemies = parsed.get("new_enemies", [])
        enemy_damage = parsed.get("enemy_damage", [])
        player_attacks = parsed.get("player_attacks", [])
        items_gained = parsed.get("items_gained", [])
        inferred_kill = parsed.get("inferred_kill", False)

        if not any([new_enemies, enemy_damage, player_attacks, items_gained, inferred_kill]):
            return

        try:
            # Garante que há um encounter ativo
            encounter = await self._combat.get_active_encounter(session_id)

            # [INIMIGOS:] — GM declara inimigos pela primeira vez
            if new_enemies:
                if encounter is None:
                    encounter = await self._combat.create_encounter(
                        session_id=session_id,
                        round_id=round_id,
                    )
                # Salva templates e spawna instâncias
                for enemy_data in new_enemies:
                    template = await self._combat.find_template_by_name(
                        enemy_data.get("nome") or enemy_data.get("name", "")
                    )
                    if template is None:
                        template = await self._combat.save_template({
                            "name": enemy_data.get("nome") or enemy_data.get("name", "Inimigo"),
                            "enemy_type": enemy_data.get("tipo") or enemy_data.get("enemy_type", "humanoid"),
                            "hp_dice": str(enemy_data.get("hp", "2d8")),
                            "armor_class": enemy_data.get("ca") or enemy_data.get("armor_class", 12),
                            "attacks": [{
                                "name": "Ataque",
                                "attack_bonus": enemy_data.get("atk", 3),
                                "damage": enemy_data.get("dano", "1d6"),
                                "damage_type": "slashing",
                            }],
                            "source": "generated",
                        })
                    # injeta template_id para spawn
                    enemy_data["template_id"] = template.id

                await self._combat.spawn_enemies(encounter.id, new_enemies)

            # [DANO_INIMIGO:] — jogador causou dano a inimigo
            if enemy_damage and encounter:
                for slug_hint, damage in enemy_damage:
                    try:
                        enemy = await self._combat.find_enemy_by_slug(encounter.id, slug_hint)
                        if enemy:
                            updated = await self._combat.apply_damage_to_enemy(enemy.id, damage)
                            await self._combat.log_event(
                                encounter_id=encounter.id,
                                event_type="damage",
                                round_id=round_id,
                                source_type="player",
                                source_name=action.character_name,
                                source_id=action.character_id,
                                target_type="enemy",
                                target_name=enemy.display_name,
                                target_id=enemy.id,
                                damage_dealt=damage,
                                damage_type="physical",
                                is_hit=True,
                            )
                            # Inimigo morreu → broadcast enemy_killed com XP e loot
                            if not updated.is_alive and self._ws_broadcast:
                                kill_payload = await self._combat.get_kill_payload(
                                    updated, action.character_name
                                )
                                asyncio.create_task(
                                    self._ws_broadcast(
                                        str(session_id),
                                        {"type": "enemy_killed", "payload": kill_payload},
                                    )
                                )
                    except Exception as exc:
                        logger.warning("Falha ao aplicar DANO_INIMIGO %s:%d — %s", slug_hint, damage, exc)

            # [ATAQUE_INIMIGO:] — inimigo atacou jogador (narrativo)
            if player_attacks and encounter:
                for atk in player_attacks:
                    try:
                        target = atk.get("target", "")
                        damage = atk.get("damage", 0)
                        is_group = atk.get("is_group", False)
                        await self._combat.log_event(
                            encounter_id=encounter.id,
                            event_type="enemy_attack",
                            round_id=round_id,
                            source_type="enemy",
                            source_name="Inimigo",
                            target_type="player" if not is_group else "group",
                            target_name=target,
                            target_id=action.character_id if not is_group else None,
                            is_group_attack=is_group,
                            damage_dealt=damage,
                            is_hit=True,
                        )
                        # Aplica dano ao personagem via character service
                        if self._characters and not is_group and action.character_id:
                            await self._characters.apply_state_update(
                                str(action.character_id), "hp", f"-{damage}"
                            )
                    except Exception as exc:
                        logger.warning("Falha ao logar ATAQUE_INIMIGO: %s", exc)

            # [ITEM_GANHO:] — personagem obteve item em combate
            if items_gained and encounter:
                for item in items_gained:
                    try:
                        await self._combat.log_event(
                            encounter_id=encounter.id,
                            event_type="item_gained",
                            round_id=round_id,
                            source_type="loot",
                            target_type="player",
                            target_name=item.get("char_name", ""),
                            item_data={
                                "item_name": item.get("item_name"),
                                "item_type": item.get("item_type"),
                            },
                        )
                    except Exception as exc:
                        logger.warning("Falha ao logar ITEM_GANHO: %s", exc)

            # Fallback: GM narrou morte em prosa sem usar [DANO_INIMIGO:]
            if inferred_kill and not enemy_damage and encounter:
                try:
                    alive = await self._combat.get_alive_enemies(encounter.id)
                    if alive:
                        target = alive[0]
                        damage = target.hp_current  # dano letal exato para garantir morte
                        updated = await self._combat.apply_damage_to_enemy(target.id, damage)
                        await self._combat.log_event(
                            encounter_id=encounter.id,
                            event_type="inferred_kill",
                            round_id=round_id,
                            source_type="player",
                            source_name=action.character_name,
                            source_id=action.character_id,
                            target_type="enemy",
                            target_name=target.display_name,
                            target_id=target.id,
                            damage_dealt=damage,
                            damage_type="physical",
                            is_hit=True,
                        )
                        if not updated.is_alive and self._ws_broadcast:
                            kill_payload = await self._combat.get_kill_payload(
                                updated, action.character_name
                            )
                            asyncio.create_task(
                                self._ws_broadcast(
                                    str(session_id),
                                    {"type": "enemy_killed", "payload": kill_payload},
                                )
                            )
                        logger.info(
                            "Kill inferido narrativamente: %s por %s",
                            target.display_name,
                            action.character_name,
                        )
                except Exception as exc:
                    logger.warning("Falha ao aplicar kill inferido: %s", exc)

            # Verifica se todos os inimigos morreram → encerra o encounter
            if encounter:
                alive = await self._combat.get_alive_enemies(encounter.id)
                if not alive:
                    await self._combat.resolve_encounter(encounter.id)
                    if self._ws_broadcast:
                        asyncio.create_task(
                            self._ws_broadcast(
                                str(session_id),
                                {"type": "combat_ended", "payload": {"encounter_id": str(encounter.id)}},
                            )
                        )

        except Exception as exc:
            logger.warning("Falha geral em _handle_combat_tags: %s", exc)
