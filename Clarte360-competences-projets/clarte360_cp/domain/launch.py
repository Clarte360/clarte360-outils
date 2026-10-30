from __future__ import annotations

from dataclasses import dataclass

from .enums import ActorRole

SCOPE_VOCAB = "CP_V1"
TOOL_CODE = "COMPETENCES_PROJETS"
HUB_SOURCE = "GESTION_ACTIONS"

ACCOMPAGNATEUR_SCOPES = frozenset({
    "CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_GDA_READ",
    "CP_SOURCE_MANUAL_IMPORT", "CP_VALIDATE", "CP_PUBLISH", "CP_FINALIZE",
    "CP_DELIVERABLE_RETURN",
})
BENEFICIAIRE_SCOPES = frozenset({
    "CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT",
    "CP_BENEFICIARY_VALIDATE", "CP_DOCUMENT_READ_PUBLISHED",
})


@dataclass(frozen=True)
class LaunchContext:
    beneficiary_id: str
    action_id: str
    prescription_id: str
    participant_id: str | None
    actor_role: ActorRole
    actor_id: str
    scopes: tuple[str, ...]
    token_version: int
    iat: int
    exp: int
    hub_source: str = HUB_SOURCE
    scope_vocab: str = SCOPE_VOCAB
    tool_code: str = TOOL_CODE
    action_no: str = ""

    def allowed_scopes(self) -> frozenset[str]:
        return ACCOMPAGNATEUR_SCOPES if self.actor_role is ActorRole.ACCOMPAGNATEUR else BENEFICIAIRE_SCOPES

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise PermissionError(f"Scope manquant : {scope}")
