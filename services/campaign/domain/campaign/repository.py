from typing import Protocol
from uuid import UUID

from domain.campaign.entity import Campaign


class ICampaignRepository(Protocol):
    """
    Interface (porta de saída) para persistência de campanhas.
    A camada de domínio define o contrato; a infra implementa.
    """

    async def get_by_id(self, campaign_id: UUID) -> Campaign | None:
        """Retorna a campanha pelo ID ou None se não encontrada."""
        ...

    async def list_all(self) -> list[Campaign]:
        """Lista todas as campanhas em ordem decrescente de criação."""
        ...

    async def save(self, campaign: Campaign) -> Campaign:
        """Persiste (cria ou atualiza) uma campanha e retorna o estado salvo."""
        ...

    async def delete(self, campaign_id: UUID) -> None:
        """Remove uma campanha e seus dados relacionados (cascata)."""
        ...
