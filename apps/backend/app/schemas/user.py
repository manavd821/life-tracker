from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClerkEmailAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email_address: str


class ClerkUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    email_addresses: list[ClerkEmailAddress] = Field(default_factory=list)
    primary_email_address_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_primary_email(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("email") is not None:
            return data

        addresses = data.get("email_addresses") or []
        primary_id = data.get("primary_email_address_id")

        for address in addresses:
            if address.get("id") == primary_id:
                data["email"] = address.get("email_address")
                break
        else:
            if addresses:
                data["email"] = addresses[0].get("email_address")

        return data


class ClerkWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    data: dict[str, Any]
