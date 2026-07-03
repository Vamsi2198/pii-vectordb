from typing import Dict

def resolve_role(auth_token:str) -> str:
    if auth_token == "admin_token":
        return "admin"
    if auth_token=="finance_token":
        return "finance"
    if auth_token=="manager_token":
        return "manager"
    return "analyst"

def is_allowed(role:str, meta: Dict)-> bool:
    allowed = meta.get("allowed_roles", [])
    return role in allowed


def is_privileged_role(role:str)-> bool:
    """Check if role is privileged (should see masked data)"""
    return role in ["manager", "finance"]