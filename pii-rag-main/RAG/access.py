from typing import Dict

def resolve_role(auth_token: str) -> str:
    if not auth_token:
        return "analyst"
    token = auth_token.strip().lower()
    if token.startswith("bearer "):
        token = token[len("bearer "):].strip()

    if token in {"admin_token", "admin"}:
        return "admin"
    if token in {"finance_token", "finance"}:
        return "finance"
    if token in {"manager_token", "manager"}:
        return "manager"
    return "analyst"

def is_allowed(role:str, meta: Dict)-> bool:
    allowed = meta.get("allowed_roles", [])
    # If no roles specified, allow all access (default to permissive)
    if not allowed:
        return True
    return role in allowed


def is_privileged_role(role:str)-> bool:
    """Check if role is privileged (should see masked data)"""
    return role in ["manager", "finance"]