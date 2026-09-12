from __future__ import annotations

from typing import Any


ASSURANCE = {"DECLARED", "OBSERVED", "TRUSTED", "UNVERIFIED"}
SOURCES = {"runtime-session", "adapter", "authenticated-human", "runtime", "provider", "artifact"}


def actor_identity(
    identifier: str | None,
    actor_type: str,
    source: str,
    assurance: str,
    **observations: Any,
) -> dict[str, Any]:
    if assurance not in ASSURANCE:
        raise ValueError(f"unknown actor assurance: {assurance}")
    if source not in SOURCES:
        raise ValueError(f"unknown actor identity source: {source}")
    # An artifact cannot authenticate its own author.
    if source == "artifact" and assurance in {"OBSERVED", "TRUSTED"}:
        assurance = "UNVERIFIED"
    value: dict[str, Any] = {
        "id": identifier,
        "type": actor_type,
        "source": source,
        "assurance": assurance,
    }
    value.update({key: item for key, item in observations.items() if item is not None})
    return value


def trusted_session_actor(identifier: str, actor_type: str = "agent", **observations: Any) -> dict[str, Any]:
    return actor_identity(identifier, actor_type, "runtime-session", "TRUSTED", **observations)


def declared_actor(identifier: str | None, actor_type: str = "agent") -> dict[str, Any]:
    return actor_identity(identifier, actor_type, "artifact", "UNVERIFIED")


def review_independence(
    producer: dict[str, Any] | None,
    reviewer: dict[str, Any] | None,
    *,
    required: bool = True,
) -> str:
    if not required:
        return "NOT_REQUIRED"
    if not producer or not reviewer:
        return "UNVERIFIED"
    reliable = {"OBSERVED", "TRUSTED"}
    if producer.get("assurance") not in reliable or reviewer.get("assurance") not in reliable:
        return "UNVERIFIED"
    producer_id, reviewer_id = producer.get("id"), reviewer.get("id")
    if not producer_id or not reviewer_id:
        return "UNVERIFIED"
    if producer_id == reviewer_id:
        return "NOT_INDEPENDENT"
    # Distinct labels are positive independence evidence only when both were
    # bound by a trusted identity mechanism. OBSERVED adapter labels can prove
    # sameness, but cannot prove that two sessions are distinct principals.
    if producer.get("assurance") == reviewer.get("assurance") == "TRUSTED":
        return "INDEPENDENT"
    return "UNVERIFIED"


def independent_review_satisfied(independence: str, required: bool) -> bool:
    if not required:
        return independence == "NOT_REQUIRED"
    return independence == "INDEPENDENT"
