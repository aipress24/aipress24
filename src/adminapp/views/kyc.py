from sqladmin import Admin, ModelView

from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation


class UserAdmin(ModelView, model=User):
    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    can_delete = False

    # List view
    column_list = [User.id, User.last_name, User.first_name]

    # Details view
    column_details_exclude_list = [User.password]

    # Edit view
    form_excluded_columns = [User.password]


class OrganisationAdmin(ModelView, model=Organisation):
    icon = "fa-solid fa-building"
    category = "Auth / KYC"

    # List view
    column_list = [Organisation.id, Organisation.name]

    # Edit view
    form_excluded_columns = [Organisation.members]


class ProfileAdmin(ModelView, model=KYCProfile):
    name = "Profil KYC"
    name_plural = "Profils KYC"
    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    can_delete = False

    # List view
    column_list = [KYCProfile.id, KYCProfile.user]


class RoleAdmin(ModelView, model=Role):
    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    # List view
    column_list = [Role.id, Role.name]


def register(admin: Admin):
    admin.add_view(UserAdmin)
    admin.add_view(OrganisationAdmin)
    admin.add_view(ProfileAdmin)
    # Broken
    # admin.add_view(RoleAdmin)
