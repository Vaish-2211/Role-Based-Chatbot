from enum import Enum


class Role(str, Enum):
    """
    All valid user roles in the system.

    Inheriting from both `str` and `Enum` means:
      - Role.FINANCE == "finance"  → True  (comparison with plain strings works)
      - A Role value can be used anywhere a string is expected (e.g. JWT payload)
      - Pydantic models accept Role as a field type and validate automatically
    """

    C_LEVEL = "c_level"
    FINANCE = "finance"
    MARKETING = "marketing"
    HR = "hr"
    ENGINEERING = "engineering"
    EMPLOYEE = "employee"


# ── Access Matrix ─────────────────────────────────────────────────────────────
# Maps each role to the list of departments whose documents they may retrieve.
# This is the single source of truth for RBAC — every filter in the system
# derives from this dictionary.
#
# Rule: always include "general" for every non-c_level role so that company
# policies are accessible to all employees.

ROLE_ACCESS: dict[Role, list[str]] = {
    Role.C_LEVEL:     ["finance", "marketing", "hr", "engineering", "general"],
    Role.FINANCE:     ["finance", "general"],
    Role.MARKETING:   ["marketing", "general"],
    Role.HR:          ["hr", "general"],
    Role.ENGINEERING: ["engineering", "general"],
    Role.EMPLOYEE:    ["general"],
}


def get_allowed_departments(role: Role) -> list[str]:
    """
    Return the list of departments a role is permitted to access.

    Example:
        get_allowed_departments(Role.FINANCE)
        # → ["finance", "general"]
    """
    return ROLE_ACCESS[role]


def has_access(role: Role, department: str) -> bool:
    """
    Return True if `role` is allowed to read documents from `department`.

    This is the single gatekeeper function used by:
      - The Qdrant RBAC filter (retrieval layer)
      - The Pandas agent guard (analytics layer)
      - Unit tests

    Example:
        has_access(Role.FINANCE, "hr")      # → False
        has_access(Role.FINANCE, "finance") # → True
        has_access(Role.C_LEVEL, "hr")      # → True
    """
    return department in ROLE_ACCESS[role]
