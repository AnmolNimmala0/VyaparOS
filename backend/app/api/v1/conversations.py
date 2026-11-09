from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_demo_context
from app.core.database import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationTurnCreate,
    ConversationTurnRead,
)
from app.services.conversation_service import (
    add_user_turn,
    create_conversation,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation_endpoint(
    payload: ConversationCreate,
    context=Depends(get_demo_context),
    db: AsyncSession = Depends(get_db),
):
    store_id, user_id = context

    return await create_conversation(
        db=db,
        store_id=store_id,
        user_id=user_id,
        title=payload.title,
    )


@router.post(
    "/{conversation_id}/turns",
    response_model=ConversationTurnRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_user_turn_endpoint(
    conversation_id: UUID,
    payload: ConversationTurnCreate,
    context=Depends(get_demo_context),
    db: AsyncSession = Depends(get_db),
):
    store_id, user_id = context

    return await add_user_turn(
        db=db,
        store_id=store_id,
        user_id=user_id,
        conversation_id=conversation_id,
        content=payload.content,
        input_type=payload.input_type,
    )
