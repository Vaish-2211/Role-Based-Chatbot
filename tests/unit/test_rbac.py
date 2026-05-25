"""
Unit tests for the RBAC access control logic.

These tests verify that has_access() and get_allowed_departments()
correctly implement the access matrix from the plan.
"""

import pytest
from app.core.rbac import Role, has_access, get_allowed_departments, ROLE_ACCESS


# ── has_access: positive cases ────────────────────────────────────────────────

def test_c_level_can_access_all():
    """C-Level must access every department."""
    for dept in ["finance", "marketing", "hr", "engineering", "general"]:
        assert has_access(Role.C_LEVEL, dept), f"c_level should access {dept}"


def test_finance_can_access_own_department():
    assert has_access(Role.FINANCE, "finance")


def test_finance_can_access_general():
    assert has_access(Role.FINANCE, "general")


def test_marketing_can_access_own_department():
    assert has_access(Role.MARKETING, "marketing")


def test_hr_can_access_own_department():
    assert has_access(Role.HR, "hr")


def test_engineering_can_access_own_department():
    assert has_access(Role.ENGINEERING, "engineering")


def test_employee_can_access_general():
    assert has_access(Role.EMPLOYEE, "general")


# ── has_access: negative cases (RBAC must block these) ───────────────────────

def test_finance_cannot_access_hr():
    assert not has_access(Role.FINANCE, "hr")


def test_finance_cannot_access_marketing():
    assert not has_access(Role.FINANCE, "marketing")


def test_finance_cannot_access_engineering():
    assert not has_access(Role.FINANCE, "engineering")


def test_marketing_cannot_access_hr():
    assert not has_access(Role.MARKETING, "hr")


def test_hr_cannot_access_finance():
    assert not has_access(Role.HR, "finance")


def test_engineering_cannot_access_finance():
    assert not has_access(Role.ENGINEERING, "finance")


def test_employee_cannot_access_hr():
    """The lowest-privilege role must not see HR data."""
    assert not has_access(Role.EMPLOYEE, "hr")


def test_employee_cannot_access_finance():
    assert not has_access(Role.EMPLOYEE, "finance")


def test_employee_cannot_access_marketing():
    assert not has_access(Role.EMPLOYEE, "marketing")


def test_employee_cannot_access_engineering():
    assert not has_access(Role.EMPLOYEE, "engineering")


# ── get_allowed_departments ───────────────────────────────────────────────────

def test_get_allowed_departments_finance():
    depts = get_allowed_departments(Role.FINANCE)
    assert set(depts) == {"finance", "general"}


def test_get_allowed_departments_c_level():
    depts = get_allowed_departments(Role.C_LEVEL)
    assert set(depts) == {"finance", "marketing", "hr", "engineering", "general"}


def test_get_allowed_departments_employee():
    depts = get_allowed_departments(Role.EMPLOYEE)
    assert depts == ["general"]


# ── Role enum ─────────────────────────────────────────────────────────────────

def test_role_enum_string_equality():
    """Role.FINANCE should equal the string 'finance' (str + Enum inheritance)."""
    assert Role.FINANCE == "finance"
    assert Role.C_LEVEL == "c_level"
    assert Role.EMPLOYEE == "employee"


def test_all_roles_have_access_entry():
    """Every Role value must have an entry in ROLE_ACCESS — no missing roles."""
    for role in Role:
        assert role in ROLE_ACCESS, f"Role {role} is missing from ROLE_ACCESS"


def test_general_access_for_all_non_none_roles():
    """Every role (including employee) must have access to 'general'."""
    for role in Role:
        assert has_access(role, "general"), f"{role} should always access 'general'"
