from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.gemini import analyze_intent
from app.integrations.prisma import transcribe_audio
from app.schemas.voice import VoiceProcessResponse
from app.services.conversation_service import (
    add_user_turn,
    create_conversation,
)
from app.services.customer_service import get_customer_balance
from app.services.entity_resolution_service import (
    resolve_intent_entities,
)
from app.services.inventory_service import get_store_inventory
from app.services.operation_planner import plan_operations
from app.services.pending_operation_service import (
    create_pending_operation,
)
from app.services.report_service import get_daily_summary

IST = ZoneInfo("Asia/Kolkata")


def format_rupees(paise: int) -> str:
    """Convert integer paise into a display-ready rupee amount."""
    return f"₹{paise / 100:,.2f}"


def format_quantity(quantity) -> str:
    """Format Decimal quantities without unnecessary trailing zeros."""
    value = Decimal(str(quantity))
    return format(value.normalize(), "f")


async def handle_read_only_action(
    db: AsyncSession,
    store_id: UUID,
    action,
    language: str,
) -> tuple[str, dict]:

    # ---------------------------------------------------------
    # 1. CHECK INVENTORY
    # ---------------------------------------------------------

    if action.original_action.action_type == "check_inventory":

        if action.product is None or action.product.entity_id is None:
            raise HTTPException(
                status_code=422,
                detail="A product must be identified for an inventory query.",
            )

        inventory = await get_store_inventory(
            db=db,
            store_id=store_id,
            limit=100,
            offset=0,
            low_stock_only=False,
        )

        product = next(
            (
                item
                for item in inventory
                if item.product_id == action.product.entity_id
            ),
            None,
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product inventory was not found.",
            )

        quantity = format_quantity(product.quantity)

        if language == "hi":
            message = (
                f"{product.product_name} ka stock "
                f"{quantity} {product.unit} hai."
            )
        else:
            message = (
                f"You currently have {quantity} {product.unit} "
                f"of {product.product_name} in stock."
            )

        return message, {
            "query_type": "INVENTORY",
            "product_id": str(product.product_id),
            "product_name": product.product_name,
            "quantity": quantity,
            "unit": product.unit,
            "reorder_level": format_quantity(product.reorder_level),
            "is_low_stock": product.is_low_stock,
        }

    # ---------------------------------------------------------
    # 2. CHECK CUSTOMER CREDIT BALANCE
    # ---------------------------------------------------------

    if action.original_action.action_type == "check_customer_balance":

        if action.customer is None or action.customer.entity_id is None:
            raise HTTPException(
                status_code=422,
                detail="A customer must be identified for a balance query.",
            )

        balance = await get_customer_balance(
            db=db,
            store_id=store_id,
            customer_id=action.customer.entity_id,
        )

        outstanding = balance["outstanding_paise"]

        if language == "hi":
            message = (
                f"{balance['customer_name']} par "
                f"{format_rupees(outstanding)} udhaar baaki hai."
            )
        else:
            message = (
                f"{balance['customer_name']} has an outstanding "
                f"balance of {format_rupees(outstanding)}."
            )

        return message, {
            "query_type": "CUSTOMER_BALANCE",
            "customer_id": str(balance["customer_id"]),
            "customer_name": balance["customer_name"],
            "total_credit_paise": balance["total_credit_paise"],
            "total_repaid_paise": balance["total_repaid_paise"],
            "outstanding_paise": outstanding,
        }

    # ---------------------------------------------------------
    # 3. GET TODAY'S BUSINESS SUMMARY
    # ---------------------------------------------------------

    if action.original_action.action_type == "get_daily_summary":

        today = datetime.now(IST).date()

        summary = await get_daily_summary(
            db=db,
            store_id=store_id,
            report_date=today,
        )

        if language == "hi":
            message = (
                f"Aaj {summary['transaction_count']} sales hui hain. "
                f"Total bikri {format_rupees(summary['revenue_paise'])}, "
                f"vasooli {format_rupees(summary['collected_paise'])}, "
                f"baaki {format_rupees(summary['outstanding_paise'])}, "
                f"aur gross profit "
                f"{format_rupees(summary['gross_profit_paise'])} hai."
            )
        else:
            message = (
                f"Today you completed {summary['transaction_count']} sales. "
                f"Revenue was {format_rupees(summary['revenue_paise'])}, "
                f"collections were {format_rupees(summary['collected_paise'])}, "
                f"outstanding dues were "
                f"{format_rupees(summary['outstanding_paise'])}, "
                f"and gross profit was "
                f"{format_rupees(summary['gross_profit_paise'])}."
            )

        return message, {
            "query_type": "DAILY_SUMMARY",
            **summary,
        }

    raise HTTPException(
        status_code=422,
        detail="Unsupported read-only action.",
    )




async def process_voice_request(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    conversation_id: UUID | None = None,
) -> VoiceProcessResponse:
    transcription = await transcribe_audio(
        audio_bytes=audio_bytes,
        filename=filename,
        content_type=content_type,
    )

    transcript = transcription["transcript"]

    if not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="The audio did not contain recognizable speech.",
        )

    return await process_transcript_request(
        db=db,
        store_id=store_id,
        user_id=user_id,
        transcript=transcript,
        detected_language=transcription.get("detected_language"),
        input_type="VOICE",
        conversation_id=conversation_id,
    )


async def process_text_request(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    text: str,
    conversation_id: UUID | None = None,
) -> VoiceProcessResponse:
    transcript = text.strip()

    if not transcript:
        raise HTTPException(
            status_code=422,
            detail="Please enter a business request.",
        )

    if len(transcript) > 2000:
        raise HTTPException(
            status_code=422,
            detail="Text requests cannot exceed 2000 characters.",
        )

    return await process_transcript_request(
        db=db,
        store_id=store_id,
        user_id=user_id,
        transcript=transcript,
        detected_language=None,
        input_type="TEXT",
        conversation_id=conversation_id,
    )


async def process_transcript_request(
    db: AsyncSession,
    store_id: UUID,
    user_id: UUID,
    transcript: str,
    detected_language: str | None,
    input_type: str,
    conversation_id: UUID | None = None,
) -> VoiceProcessResponse:
    # ---------------------------------------------------------
    # 2. CREATE OR REUSE CONVERSATION
    # ---------------------------------------------------------

    if conversation_id is None:
        conversation = await create_conversation(
            db=db,
            store_id=store_id,
            user_id=user_id,
            title=transcript[:100],
        )

        conversation_id = conversation.id

    # ---------------------------------------------------------
    # 3. SAVE USER TURN
    # ---------------------------------------------------------

    turn = await add_user_turn(
        db=db,
        store_id=store_id,
        user_id=user_id,
        conversation_id=conversation_id,
        content=transcript,
        input_type=input_type,
    )

    # ---------------------------------------------------------
    # 4. UNDERSTAND THE REQUEST
    # ---------------------------------------------------------

    intent = await analyze_intent(transcript)

    if not intent.actions:
        return VoiceProcessResponse(
            status="CLARIFICATION_REQUIRED",
            message="I couldn't identify a business action in that request.",
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            clarification_questions=[
                "Could you repeat what you would like me to do?"
            ],
        )

    # ---------------------------------------------------------
    # 5. ONE ACTION PER REQUEST
    # ---------------------------------------------------------

    if len(intent.actions) != 1:
        return VoiceProcessResponse(
            status="CLARIFICATION_REQUIRED",
            message=(
                "Please make one business request at a time "
                "so I can verify each operation independently."
            ),
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            clarification_questions=[
                "Please repeat the request with only one business action."
            ],
        )

    # ---------------------------------------------------------
    # 6. HANDLE AMBIGUOUS INTENTS
    # ---------------------------------------------------------

    if intent.needs_clarification:
        questions = (
            [intent.clarification_question]
            if intent.clarification_question
            else ["Could you clarify your request?"]
        )

        return VoiceProcessResponse(
            status="CLARIFICATION_REQUIRED",
            message="I need a little more information before proceeding.",
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            clarification_questions=questions,
        )

    # ---------------------------------------------------------
    # 7. RESOLVE PRODUCT AND CUSTOMER NAMES
    # ---------------------------------------------------------

    resolved_intent = await resolve_intent_entities(
        db=db,
        store_id=store_id,
        intent=intent,
    )

    if resolved_intent.needs_clarification:
        return VoiceProcessResponse(
            status="CLARIFICATION_REQUIRED",
            message="I couldn't confidently identify the requested entities.",
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            resolved_intent=resolved_intent.model_dump(mode="json"),
            clarification_questions=resolved_intent.clarification_questions,
        )

    # ---------------------------------------------------------
    # 8. EXECUTE READ-ONLY QUERY HANDLERS
    # ---------------------------------------------------------

    action = resolved_intent.actions[0]
    action_type = intent.actions[0].action_type

    read_only_actions = {
        "check_inventory",
        "check_customer_balance",
        "get_daily_summary",
    }

    if action_type in read_only_actions:

        message, data = await handle_read_only_action(
            db=db,
            store_id=store_id,
            action=action,
            language=intent.language,
        )

        return VoiceProcessResponse(
            status="READ_ONLY_SUCCESS",
            message=message,
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            resolved_intent=resolved_intent.model_dump(mode="json"),
            data=data,
        )

    # ---------------------------------------------------------
    # 9. PLAN FINANCIAL OR INVENTORY MUTATIONS
    # ---------------------------------------------------------

    planning_result = await plan_operations(
        db=db,
        store_id=store_id,
        resolved_intent=resolved_intent,
    )

    if planning_result.needs_clarification:
        return VoiceProcessResponse(
            status="CLARIFICATION_REQUIRED",
            message="The requested operation needs clarification.",
            transcript=transcript,
            detected_language=detected_language,
            conversation_id=conversation_id,
            turn_id=turn.id,
            intent=intent.model_dump(mode="json"),
            resolved_intent=resolved_intent.model_dump(mode="json"),
            clarification_questions=planning_result.clarification_questions,
        )

    if len(planning_result.plans) != 1:
        raise HTTPException(
            status_code=422,
            detail="Expected exactly one validated operation plan.",
        )

    plan = planning_result.plans[0]

    # ---------------------------------------------------------
    # 10. CREATE PENDING OPERATION
    # ---------------------------------------------------------

    pending_operation = await create_pending_operation(
        db=db,
        store_id=store_id,
        user_id=user_id,
        conversation_id=conversation_id,
        plan=plan,
    )

    # Financial and inventory mutations still require
    # confirmation and a separate execution request.

    return VoiceProcessResponse(
        status="AWAITING_CONFIRMATION",
        message=plan.confirmation_message,
        transcript=transcript,
        detected_language=detected_language,
        conversation_id=conversation_id,
        turn_id=turn.id,
        intent=intent.model_dump(mode="json"),
        resolved_intent=resolved_intent.model_dump(mode="json"),
        operation_plan=plan.model_dump(mode="json"),
        pending_operation={
            "id": str(pending_operation.id),
            "operation_type": pending_operation.operation_type,
            "status": pending_operation.status,
            "confirmation_message": pending_operation.confirmation_message,
            "payload": pending_operation.payload,
            "expires_at": (
                pending_operation.expires_at.isoformat()
                if pending_operation.expires_at
                else None
            ),
        },
    )