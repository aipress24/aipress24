from __future__ import annotations

import functools
from pathlib import Path

import yaml
from flask import current_app
from flask_super.decorators import service
from svcs import Container

from app.models.auth import User
from app.modules.kyc.community_role import community_to_role_name


# Cache pour le fichier de configuration RBAC pour éviter de le lire à chaque fois
@functools.lru_cache(maxsize=1)
def _load_rbac_config() -> dict:
    """Charge la configuration RBAC depuis le fichier YAML."""
    # S'assure que le chemin est relatif à la racine de l'application
    config_path = Path(current_app.root_path).parent / "config" / "rbac.yaml"
    with config_path.open("r") as f:
        return yaml.safe_load(f)


@service
class AuthorizationService:
    """
    Le point de décision central (PDP) pour toutes les vérifications de permissions.
    """

    @classmethod
    def svcs_factory(cls, ctn: Container) -> AuthorizationService:
        """Factory pour l'injection de dépendances via svcs."""
        return cls()

    def can(self, user: User|None, permission: str, resource: object = None) -> bool:
        """Vérifie si un utilisateur a une permission spécifique."""
        if not user or user.is_anonymous:
            return False

        user_permissions = self.get_permissions(user, resource)
        return permission in user_permissions

    def has_role(self, user: User, role_name: str, resource: object = None) -> bool:
        """Vérifie si un utilisateur possède un rôle spécifique."""
        if not user or user.is_anonymous:
            return False

        user_roles = self.get_roles(user, resource)
        return role_name in user_roles

    def get_roles(self, user: User, resource: object = None) -> set[str]:
        """Retourne l'ensemble de tous les noms de rôles d'un utilisateur."""
        if not user or user.is_anonymous:
            return set()

        roles = set()

        # 1. Rôles directs (stockés en base de données)
        for role in user.roles:
            roles.add(role.name)

        # 2. Rôle hérité de la communauté (via le profil KYC)
        if user.profile and user.profile.profile_community:
            community_role = community_to_role_name(user.profile.profile_community)
            roles.add(community_role)

        # 3. Rôle hérité du type de Business Wall de l'organisation
        if user.organisation and user.organisation.bw_type:
            rbac_config = _load_rbac_config()
            bw_type_str = user.organisation.bw_type.name.lower().replace("_", "-")
            inherited_role = rbac_config.get("roles_by_bw_type", {}).get(bw_type_str)
            if inherited_role:
                roles.add(inherited_role)

        # TODO: Implémenter les rôles contextuels basés sur 'resource' si nécessaire.
        # Par exemple, vérifier si `user` est manager de `resource` (si c'est une organisation).

        return roles

    def get_permissions(self, user: User, resource: object = None) -> set[str]:
        """Retourne l'ensemble de toutes les permissions d'un utilisateur."""
        if not user or user.is_anonymous:
            return set()

        user_roles = self.get_roles(user, resource)
        rbac_config = _load_rbac_config()
        all_permissions = rbac_config.get("role_permissions", {})

        permissions = set()
        for role_name in user_roles:
            # Récupère les permissions pour ce rôle et les ajoute à l'ensemble
            role_perms = all_permissions.get(role_name.lower(), [])
            permissions.update(role_perms)

        return permissions
