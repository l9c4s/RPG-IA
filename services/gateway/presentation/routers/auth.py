"""Auth router — /auth/register, /auth/login, /auth/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from application.user.dtos import LoginDTO, RegisterDTO
from application.user.use_cases import GetMeUseCase, LoginUseCase, RegisterUseCase
from presentation.dependencies import (
    get_current_user_id,
    get_get_me_uc,
    get_login_uc,
    get_register_uc,
)
from presentation.schemas.user import LoginRequest, TokenResponse, UserCreateRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_dto_to_response(dto) -> UserResponse:
    return UserResponse(
        id=dto.id,
        username=dto.username,
        email=dto.email,
        is_active=dto.is_active,
        created_at=dto.created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreateRequest,
    uc: RegisterUseCase = Depends(get_register_uc),
):
    try:
        user_dto = await uc.execute(RegisterDTO(
            username=body.username,
            email=body.email,
            password=body.password,
        ))
    except ValueError as exc:
        msg = str(exc)
        if msg == "email_taken":
            raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já está cadastrado.")
        if msg == "username_taken":
            raise HTTPException(status.HTTP_409_CONFLICT, "Este nome de usuário já está em uso.")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não foi possível cadastrar o usuário.")
    return _user_dto_to_response(user_dto)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    uc: LoginUseCase = Depends(get_login_uc),
):
    try:
        _, token_dto = await uc.execute(LoginDTO(email=body.email, password=body.password))
    except ValueError as exc:
        msg = str(exc)
        if msg == "inactive_user":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Conta desativada. Entre em contato com o suporte.",
            )
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "E-mail ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token_dto.access_token, token_type=token_dto.token_type)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id=Depends(get_current_user_id),
    uc: GetMeUseCase = Depends(get_get_me_uc),
):
    try:
        user_dto = await uc.execute(user_id)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado.")
    return _user_dto_to_response(user_dto)
