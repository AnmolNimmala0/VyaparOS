import unicodedata
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.entity_repository import (
    get_active_customers,
    get_active_products_with_aliases,
)
from app.schemas.intent import IntentAnalysis
from app.schemas.resolved_intent import (
    EntityCandidate,
    EntityResolution,
    ResolvedAction,
    ResolvedIntent,
)


def normalize_entity_name(value: str) -> str:
    """Normalize names for case-insensitive comparison."""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()

    # Remove punctuation and normalize whitespace.
    normalized = "".join(
        char if char.isalnum() or char.isspace() else " "
        for char in normalized
    )

    return " ".join(normalized.split())


def resolve_candidates(
    query: str | None,
    candidates: list[tuple[UUID, str, list[str]]],
) -> EntityResolution:
    """
    Resolve entities using:
    1. Exact canonical-name or alias matching.
    2. Unique partial-name matching.
    3. Conservative fuzzy matching.

    Never automatically select between similarly ranked candidates.
    """

    if not query or not query.strip():
        return EntityResolution(
            status="not_found",
            query=query,
        )

    normalized_query = normalize_entity_name(query)

    # 1. Exact matching.
    exact_matches = []

    for entity_id, canonical_name, aliases in candidates:
        searchable_names = [canonical_name, *aliases]

        if any(
            normalize_entity_name(name) == normalized_query
            for name in searchable_names
        ):
            exact_matches.append((entity_id, canonical_name))

    exact_matches = list({
        entity_id: canonical_name
        for entity_id, canonical_name in exact_matches
    }.items())

    if len(exact_matches) == 1:
        entity_id, canonical_name = exact_matches[0]

        return EntityResolution(
            status="matched",
            query=query,
            entity_id=entity_id,
            canonical_name=canonical_name,
        )

    if len(exact_matches) > 1:
        return EntityResolution(
            status="ambiguous",
            query=query,
            candidates=[
                EntityCandidate(id=entity_id, name=name)
                for entity_id, name in exact_matches
            ],
        )

    # 2. Partial matching.
    partial_matches = []

    for entity_id, canonical_name, aliases in candidates:
        searchable_names = [canonical_name, *aliases]

        if any(
            normalized_query in normalize_entity_name(name).split()
            for name in searchable_names
        ):
            partial_matches.append((entity_id, canonical_name))

    partial_matches = list({
        entity_id: canonical_name
        for entity_id, canonical_name in partial_matches
    }.items())

    if len(partial_matches) == 1:
        entity_id, canonical_name = partial_matches[0]

        return EntityResolution(
            status="matched",
            query=query,
            entity_id=entity_id,
            canonical_name=canonical_name,
        )

    if len(partial_matches) > 1:
        return EntityResolution(
            status="ambiguous",
            query=query,
            candidates=[
                EntityCandidate(id=entity_id, name=name)
                for entity_id, name in partial_matches
            ],
        )

    # 3. Fuzzy matching.
    # Keep the best score for each database entity.
    scores: dict[UUID, tuple[str, float]] = {}

    for entity_id, canonical_name, aliases in candidates:
        searchable_names = [canonical_name, *aliases]
        best_score = 0.0

        for name in searchable_names:
            normalized_name = normalize_entity_name(name)

            if not normalized_name:
                continue

            score = SequenceMatcher(
                None,
                normalized_query,
                normalized_name,
            ).ratio()

            # Also compare individual words for multi-word names.
            token_scores = [
                SequenceMatcher(
                    None,
                    normalized_query,
                    token,
                ).ratio()
                for token in normalized_name.split()
            ]

            if token_scores:
                score = max(score, max(token_scores))

            best_score = max(best_score, score)

        scores[entity_id] = (canonical_name, best_score)

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )

    # Require a strong match and a clear margin over the second choice.
    if ranked:
        best_id, (best_name, best_score) = ranked[0]

        second_score = ranked[1][1][1] if len(ranked) > 1 else 0.0

        if best_score >= 0.88 and best_score - second_score >= 0.08:
            return EntityResolution(
                status="matched",
                query=query,
                entity_id=best_id,
                canonical_name=best_name,
            )

        if best_score >= 0.88:
            close_matches = [
                (entity_id, name)
                for entity_id, (name, score) in ranked
                if score >= best_score - 0.08
            ]

            return EntityResolution(
                status="ambiguous",
                query=query,
                candidates=[
                    EntityCandidate(id=entity_id, name=name)
                    for entity_id, name in close_matches
                ],
            )

    return EntityResolution(
        status="not_found",
        query=query,
    )


async def resolve_intent_entities(
    db: AsyncSession,
    store_id: UUID,
    intent: IntentAnalysis,
) -> ResolvedIntent:
    """Resolve extracted product and customer names to database records."""

    products = await get_active_products_with_aliases(db, store_id)
    customers = await get_active_customers(db, store_id)

    product_candidates = [
        (product.id, product.name, aliases)
        for product, aliases in products
    ]

    customer_candidates = [
        (customer.id, customer.name, [])
        for customer in customers
    ]

    resolved_actions = []
    clarification_questions = []

    for action in intent.actions:
        resolved_product = None
        resolved_customer = None

        product_required = action.action_type in {
            "record_sale",
            "record_credit_sale",
            "check_inventory",
            "adjust_inventory",
        }

        customer_required = action.action_type in {
            "record_credit_repayment",
            "record_credit_sale",
            "check_customer_balance",
        }

        if product_required or action.product_name:
            resolved_product = resolve_candidates(
                action.product_name,
                product_candidates,
            )

            if resolved_product.status != "matched":
                if resolved_product.status == "ambiguous":
                    names = ", ".join(
                        candidate.name
                        for candidate in resolved_product.candidates
                    )
                    clarification_questions.append(
                        f"Which product did you mean by "
                        f"'{action.product_name}'? {names}"
                    )
                else:
                    clarification_questions.append(
                        f"I couldn't identify the product "
                        f"'{action.product_name or 'mentioned product'}'. "
                        "Could you clarify?"
                    )

        if customer_required or action.customer_name:
            resolved_customer = resolve_candidates(
                action.customer_name,
                customer_candidates,
            )

            if resolved_customer.status != "matched":
                if resolved_customer.status == "ambiguous":
                    names = ", ".join(
                        candidate.name
                        for candidate in resolved_customer.candidates
                    )
                    clarification_questions.append(
                        f"Which customer did you mean by "
                        f"'{action.customer_name}'? {names}"
                    )
                else:
                    clarification_questions.append(
                        f"I couldn't identify the customer "
                        f"'{action.customer_name or 'mentioned customer'}'. "
                        "Could you clarify?"
                    )

        resolved_actions.append(
            ResolvedAction(
                original_action=action,
                product=resolved_product,
                customer=resolved_customer,
            )
        )

    return ResolvedIntent(
        actions=resolved_actions,
        needs_clarification=(
            intent.needs_clarification
            or bool(clarification_questions)
        ),
        clarification_questions=clarification_questions,
    )
