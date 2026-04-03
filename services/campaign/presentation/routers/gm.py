"""
Rotas HTTP do Game Master — borda da aplicação.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from application.gm.dtos import Generate8BitCharacterDTO, TriggerOpeningDTO
from application.gm.use_cases import (
    Generate8BitCharacterUseCase,
    GenerateOpeningNarrativeUseCase,
    TriggerOpeningUseCase,
)
from presentation.dependencies import (
    get_8bit_character_uc,
    get_opening_narrative_uc,
    get_trigger_opening_uc,
)
from presentation.schemas.gm import Generate8BitRequest, Generate8BitResponse, OpeningStatusResponse

router = APIRouter(tags=["gm"])


@router.post(
    "/campaigns/{campaign_id}/generate-character-8bit",
    response_model=Generate8BitResponse,
    status_code=status.HTTP_200_OK,
    summary="Gerar personagem 8-bit via LangChain",
)
async def generate_character_8bit(
    campaign_id: UUID,
    body: Generate8BitRequest,
    uc: Generate8BitCharacterUseCase = Depends(get_8bit_character_uc),
) -> Generate8BitResponse:
    try:
        result = await uc.execute(
            Generate8BitCharacterDTO(campaign_id=campaign_id, description=body.description)
        )
        return Generate8BitResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar a descrição 8-bit do personagem. Tente novamente.",
        )


@router.post(
    "/campaigns/{campaign_id}/generate-opening",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_generate_opening(
    campaign_id: UUID,
    trigger_uc: TriggerOpeningUseCase = Depends(get_trigger_opening_uc),
    opening_uc: GenerateOpeningNarrativeUseCase = Depends(get_opening_narrative_uc),
) -> OpeningStatusResponse:
    """
    Dispara manualmente a geração da narrativa de abertura.
    Idempotente: ignora se já gerado ou em andamento.
    """
    try:
        result = await trigger_uc.execute(
            TriggerOpeningDTO(campaign_id=campaign_id),
            opening_task_fn=opening_uc.execute,
        )
        return OpeningStatusResponse(init_status=result.init_status, message=result.message)
    except ValueError as exc:
        code = (
            status.HTTP_400_BAD_REQUEST
            if "sessão" in str(exc).lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=str(exc))
