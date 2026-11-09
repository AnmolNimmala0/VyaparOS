from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=150)
    language: str = Field(default="hi", min_length=1, max_length=20)

    @field_validator("alias")
    @classmethod
    def clean_alias(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Alias cannot be empty.")
        return value


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    sku: str | None = Field(default=None, max_length=80)
    unit: str = Field(default="piece", min_length=1, max_length=30)

    cost_price_paise: int = Field(default=0, ge=0)
    selling_price_paise: int = Field(default=0, ge=0)

    aliases: list[ProductAliasCreate] = Field(default_factory=list)

    @field_validator("name", "unit")
    @classmethod
    def clean_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("aliases")
    @classmethod
    def validate_unique_aliases(
        cls,
        aliases: list[ProductAliasCreate],
    ) -> list[ProductAliasCreate]:
        normalized = [item.alias.casefold() for item in aliases]

        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate aliases are not allowed.")

        return aliases


class ProductRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    sku: str | None
    unit: str
    cost_price_paise: int
    selling_price_paise: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductDetail(ProductRead):
    aliases: list[ProductAliasCreate] = Field(default_factory=list)