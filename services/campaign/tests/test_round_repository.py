"""
Testes de integração do RoundRepository.
Usa fixture db_session própria (sem depender do conftest) conectando ao postgres do Docker.
"""

import pytest
import pytest_asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from infrastructure.database.orm_models import Base
from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus
from infrastructure.database.orm_models import CampaignORM, SessionORM
from infrastructure.repositories.round_repository import RoundRepository

# URL do banco de testes — usa rpg_platform (banco real dentro do Docker)
_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://rpg_user:change_me_strong_password@postgres:5432/rpg_platform",
)


@pytest_asyncio.fixture
async def db_session():
    """Cria engine e sessão temporária; faz rollback ao final de cada teste."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    # Garante que as tabelas do sistema de rounds existem
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def create_campaign_and_session(db: AsyncSession):
    """Cria campanha e sessão de suporte para os testes."""
    campaign = CampaignORM(
        id=uuid4(),
        title="Test Campaign",
        rpg_system="D&D 5e",
        difficulty="medium",
        tone="heroic",
        status="active",
        ai_players_count=0,
        init_status="idle",
        opening_generated=False,
    )
    db.add(campaign)
    await db.flush()

    session_orm = SessionORM(id=uuid4(), campaign_id=campaign.id)
    db.add(session_orm)
    await db.flush()
    return campaign.id, session_orm.id


# ─── Testes ───────────────────────────────────────────────────────────────────

class TestRoundRepository:
    @pytest.mark.asyncio
    async def test_save_and_get_round(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        saved = await repo.save(r)
        assert saved.id == r.id
        assert saved.status == RoundStatus.COLLECTING
        assert saved.round_number == 1

        fetched = await repo.get_by_id(r.id)
        assert fetched is not None
        assert fetched.session_id == session_id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_unknown(self, db_session):
        repo = RoundRepository(db_session)
        result = await repo.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_by_session(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)
        await db_session.commit()

        active = await repo.get_active_by_session(session_id)
        assert active is not None
        assert active.id == r.id

    @pytest.mark.asyncio
    async def test_get_active_returns_none_when_all_completed(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        r.status = RoundStatus.COLLECTING
        await repo.save(r)

        # Completa o round
        r.status = RoundStatus.GM_PROCESSING
        r.complete()
        await repo.save(r)
        await db_session.commit()

        active = await repo.get_active_by_session(session_id)
        assert active is None

    @pytest.mark.asyncio
    async def test_get_last_round_number_zero_when_empty(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        last = await repo.get_last_round_number(session_id)
        assert last == 0

    @pytest.mark.asyncio
    async def test_get_last_round_number_increments(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        for i in range(1, 4):
            r = Round.create(session_id=session_id, round_number=i)
            r.status = RoundStatus.GM_PROCESSING
            r.complete()
            await repo.save(r)
            await db_session.flush()

        last = await repo.get_last_round_number(session_id)
        assert last == 3

    @pytest.mark.asyncio
    async def test_save_action_and_load(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)

        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Thorin",
            is_ai=False,
            is_pass=False,
            action_text="Ataco o dragão!",
        )
        await repo.save_action(action)
        await db_session.commit()

        fetched_round = await repo.get_by_id(r.id)
        assert len(fetched_round.actions) == 1
        assert fetched_round.actions[0].character_name == "Thorin"
        assert fetched_round.actions[0].action_text == "Ataco o dragão!"

    @pytest.mark.asyncio
    async def test_save_pass_action(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)

        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Garet",
            is_ai=False,
            is_pass=True,
        )
        await repo.save_action(action)
        await db_session.commit()

        fetched_round = await repo.get_by_id(r.id)
        assert fetched_round.actions[0].is_pass is True
        assert fetched_round.actions[0].action_text is None

    @pytest.mark.asyncio
    async def test_update_action_persists_d20_and_gm_response(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)

        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Elara",
            is_ai=False,
            is_pass=False,
            action_text="Fireball!",
        )
        await repo.save_action(action)

        action.d20_roll = 17
        action.initiative_order = 1
        action.record_gm_outcome("A bola de fogo acerta!", gm_rolled_dice=False)
        await repo.update_action(action)
        await db_session.commit()

        fetched_round = await repo.get_by_id(r.id)
        updated = fetched_round.actions[0]
        assert updated.d20_roll == 17
        assert updated.initiative_order == 1
        assert updated.gm_response == "A bola de fogo acerta!"
        assert updated.gm_rolled_dice is False

    @pytest.mark.asyncio
    async def test_save_ai_action(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)

        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Pip (IA)",
            is_ai=True,
            is_pass=False,
            action_text="Curo o aliado ferido.",
        )
        await repo.save_action(action)
        await db_session.commit()

        fetched_round = await repo.get_by_id(r.id)
        assert fetched_round.actions[0].is_ai is True

    @pytest.mark.asyncio
    async def test_multiple_actions_loaded_in_order(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)

        names = ["Alpha", "Beta", "Gamma"]
        for name in names:
            action = RoundAction.create(
                round_id=r.id,
                session_id=session_id,
                character_name=name,
                is_ai=False,
                is_pass=False,
                action_text=f"{name} ataca",
            )
            await repo.save_action(action)
            await db_session.flush()

        await db_session.commit()
        fetched = await repo.get_by_id(r.id)
        loaded_names = [a.character_name for a in fetched.actions]
        assert loaded_names == names

    @pytest.mark.asyncio
    async def test_update_round_status(self, db_session):
        _, session_id = await create_campaign_and_session(db_session)
        repo = RoundRepository(db_session)

        r = Round.create(session_id=session_id, round_number=1)
        await repo.save(r)
        await db_session.commit()

        r.status = RoundStatus.RESOLVING
        await repo.save(r)
        await db_session.commit()

        fetched = await repo.get_by_id(r.id)
        assert fetched.status == RoundStatus.RESOLVING
