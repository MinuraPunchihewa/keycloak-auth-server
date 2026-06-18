from app.auth.keycloak import User


PERSONA_ROLES = frozenset({"buyer", "seller"})


def has_persona(user: User) -> bool:
    return bool(PERSONA_ROLES.intersection(user.roles))


def is_valid_persona(role: str) -> bool:
    return role in PERSONA_ROLES
