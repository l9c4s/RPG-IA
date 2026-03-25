from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    """Dados necessários para registrar um novo usuário."""

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        examples=["jogador_01"],
        description="Nome de usuário único (letras, números, _ e -).",
    )
    email: EmailStr = Field(
        examples=["jogador@email.com"],
        description="Endereço de e-mail válido e único.",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        examples=["SenhaForte@123"],
        description="Senha com no mínimo 8 caracteres.",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class UserLogin(BaseModel):
    """Credenciais para autenticação."""

    email: EmailStr = Field(examples=["jogador@email.com"])
    password: str = Field(examples=["SenhaForte@123"])

    model_config = ConfigDict(str_strip_whitespace=True)


class Token(BaseModel):
    """Token de acesso retornado após autenticação bem-sucedida."""

    access_token: str = Field(description="Token JWT de acesso.")
    token_type: str = Field(default="bearer", description="Tipo do token (sempre 'bearer').")


class UserResponse(BaseModel):
    """Dados públicos do usuário retornados pela API."""

    id: int = Field(description="Identificador único do usuário.")
    username: str = Field(description="Nome de usuário.")
    email: EmailStr = Field(description="Endereço de e-mail.")
    is_active: bool = Field(description="Indica se a conta está ativa.")

    model_config = ConfigDict(from_attributes=True)
