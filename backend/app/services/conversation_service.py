from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.conversation import Conversation
from app.models.conversation_turn import ConversationTurn


async def create_conversation(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    title: str | None = None,
) -> Conversation:
    conversation = Conversation(
        store_id=store_id,
        user_id=user_id,
        title=title,
        status="ACTIVE",
    )

    db.add(conversation)

    try:
        await db.flush()

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=conversation.id,
                event_type="CONVERSATION_CREATED",
                entity_type="CONVERSATION",
                entity_id=conversation.id,
                event_data={"title": title},
            )
        )

        await db.commit()
        await db.refresh(conversation)

        return conversation

    except Exception:
        await db.rollback()
        raise


async def add_user_turn(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    conversation_id: UUID,
    content: str,
    input_type: str = "TEXT",
) -> ConversationTurn:
    # Lock the conversation so concurrent messages cannot receive
    # the same sequence number.
    conversation = await db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.store_id == store_id,
            Conversation.user_id == user_id,
            Conversation.status == "ACTIVE",
        )
        .with_for_update()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Active conversation not found.",
        )

    if input_type not in {"TEXT", "VOICE"}:
        raise HTTPException(
            status_code=422,
            detail="Unsupported input type.",
        )

    try:
        current_max = await db.scalar(
            select(func.coalesce(func.max(ConversationTurn.sequence_number), 0))
            .where(
                ConversationTurn.store_id == store_id,
                ConversationTurn.conversation_id == conversation_id,
            )
        )

        next_sequence = current_max + 1

        turn = ConversationTurn(
            store_id=store_id,
            conversation_id=conversation_id,
            sequence_number=next_sequence,
            role="USER",
            content=content,
            input_type=input_type,
        )

        db.add(turn)

        conversation.updated_at = func.now()

        await db.flush()

        db.add(
            AuditEvent(
                store_id=store_id,
                user_id=user_id,
                conversation_id=conversation_id,
                event_type="USER_TURN_CREATED",
                entity_type="CONVERSATION_TURN",
                entity_id=turn.id,
                event_data={
                    "sequence_number": next_sequence,
                    "input_type": input_type,
                    "content_length": len(content),
                },
            )
        )

        await db.commit()
        await db.refresh(turn)

        return turn

    except Exception:
        await db.rollback()
        raise
