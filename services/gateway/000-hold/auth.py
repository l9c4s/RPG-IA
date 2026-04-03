from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, User
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ALGORITHM = "HS256"
DEFAULT_EXPIRY_HOURS = 24


def get_password_hash(password: str) -> str:
    """Gera o hash bcrypt de uma senha em texto plano."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash armazenado."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um token JWT assinado com os dados fornecidos.

    Args:
        data: Payload a ser codificado no token.
        expires_delta: Tempo de expiração customizado. Padrão: 24 horas.

    Returns:
        Token JWT como string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(hours=DEFAULT_EXPIRY_HOURS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Verifica e decodifica um token JWT.

    Args:
        token: Token JWT como string.

    Returns:
        Payload decodificado.

    Raises:
        HTTPException 401: Token inválido ou expirado.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependência FastAPI que extrai e valida o usuário autenticado a partir do token JWT.

    Args:
        token: Bearer token extraído do cabeçalho Authorization.
        db: Sessão assíncrona do banco de dados.

    Returns:
        Instância do usuário autenticado.

    Raises:
        HTTPException 401: Token inválido, expirado ou usuário não encontrado.
        HTTPException 403: Conta do usuário desativada.
    """
    payload = verify_token(token)
    user_id: Optional[str] = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Entre em contato com o suporte.",
        )

    return user
