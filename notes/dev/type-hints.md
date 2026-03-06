# Type Hints Guide

Ce guide documente les conventions de typage utilisées dans le projet AiPress24.

## Syntaxe Moderne (Python 3.10+)

### Union Types

```python
# Moderne (préféré)
def process(value: str | int) -> str | None:
    ...

# Ancien (éviter)
from typing import Union, Optional
def process(value: Union[str, int]) -> Optional[str]:
    ...
```

### Optional

```python
# Moderne (préféré)
def find_user(id: int) -> User | None:
    ...

# Équivalent à
def find_user(id: int) -> Optional[User]:
    ...

# Pour les paramètres avec valeur par défaut None
def search(query: str, limit: int | None = None) -> list[User]:
    ...
```

### Collections

```python
# Moderne (préféré) - utiliser les built-ins
def get_users() -> list[User]:
    ...

def get_config() -> dict[str, Any]:
    ...

def get_ids() -> set[int]:
    ...

# Ancien (éviter)
from typing import List, Dict, Set
def get_users() -> List[User]:
    ...
```

### Tuple

```python
# Tuple de taille fixe
def get_coordinates() -> tuple[float, float]:
    return (1.0, 2.0)

# Tuple de taille variable (homogène)
def get_values() -> tuple[int, ...]:
    return (1, 2, 3, 4)
```

## Callable et Fonctions

```python
from collections.abc import Callable

# Fonction sans arguments retournant str
handler: Callable[[], str]

# Fonction avec arguments
processor: Callable[[str, int], bool]

# Fonction avec arguments variés
def apply(func: Callable[..., Any], *args: Any) -> Any:
    return func(*args)
```

## TYPE_CHECKING

Utiliser `TYPE_CHECKING` pour éviter les imports circulaires et améliorer les performances.

### Quand l'utiliser

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Ces imports ne sont exécutés qu'au type checking
    from app.models.auth import User
    from app.models.organisation import Organisation

class MyService:
    def get_user(self, id: int) -> User:  # OK grâce à __future__.annotations
        ...
```

### Patterns courants

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from flask import Flask

def init_app(app: Flask) -> None:
    ...

def get_session() -> Session:
    ...
```

### Quand NE PAS l'utiliser

```python
# Ne pas utiliser TYPE_CHECKING pour les types utilisés à runtime
from app.enums import RoleEnum  # Utilisé dans la logique

def has_role(user: User, role: RoleEnum) -> bool:
    return role in user.roles  # RoleEnum utilisé à runtime
```

## SQLAlchemy 2.0 Patterns

### Modèles avec Mapped

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import IdMixin, LifeCycleMixin


class User(IdMixin, LifeCycleMixin, Base):
    __tablename__ = "auth_user"

    # Colonnes simples
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")

    # Colonne nullable
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Colonne avec valeur par défaut
    active: Mapped[bool] = mapped_column(default=True)
    karma: Mapped[int] = mapped_column(default=0)

    # Foreign key
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("org_organisation.id"), nullable=True
    )

    # Relationship (many-to-one)
    organisation: Mapped[Organisation | None] = relationship(
        back_populates="members"
    )

    # Relationship (one-to-many)
    posts: Mapped[list[Post]] = relationship(
        back_populates="author",
        default_factory=list
    )
```

### Colonnes JSON

```python
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column


class Profile(Base):
    # JSON avec type dict
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    # JSON nullable
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
```

### Colonnes Enum

```python
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import PublicationStatus


class Article(Base):
    status: Mapped[PublicationStatus] = mapped_column(
        SAEnum(PublicationStatus),
        default=PublicationStatus.DRAFT
    )
```

### Relationships

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Organisation(Base):
    # One-to-many
    members: Mapped[list[User]] = relationship(
        back_populates="organisation",
        default_factory=list
    )

    # Many-to-many (avec table d'association)
    tags: Mapped[list[Tag]] = relationship(
        secondary=organisation_tags_table,
        back_populates="organisations"
    )


class User(Base):
    # Many-to-one
    organisation: Mapped[Organisation | None] = relationship(
        back_populates="members"
    )

    # One-to-one
    profile: Mapped[Profile | None] = relationship(
        back_populates="user",
        uselist=False
    )
```

### Select Statements

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload


def get_users_with_org(session: Session) -> list[User]:
    stmt = (
        select(User)
        .where(User.active == True)
        .options(selectinload(User.organisation))
        .order_by(User.last_name)
    )
    return list(session.scalars(stmt))


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return session.scalar(stmt)
```

## ClassVar et Instance Variables

```python
from typing import ClassVar


class MyComponent:
    # Variable de classe (partagée entre instances)
    default_limit: ClassVar[int] = 100
    allowed_types: ClassVar[list[str]] = ["article", "post"]

    # Variable d'instance (propre à chaque instance)
    name: str
    items: list[str]

    def __init__(self, name: str) -> None:
        self.name = name
        self.items = []  # Nouvelle liste pour chaque instance
```

## Generics

```python
from typing import TypeVar, Generic

T = TypeVar("T")


class Repository(Generic[T]):
    model_class: type[T]

    def get(self, id: int) -> T | None:
        ...

    def get_all(self) -> list[T]:
        ...

    def create(self, **kwargs: Any) -> T:
        ...


class UserRepository(Repository[User]):
    model_class = User
```

## Protocol (Duck Typing Structurel)

```python
from typing import Protocol


class Renderable(Protocol):
    def render(self) -> str:
        ...


class HTMLComponent(Protocol):
    id: str

    def render(self) -> str:
        ...

    def get_context(self) -> dict[str, Any]:
        ...


def render_all(components: list[Renderable]) -> str:
    return "".join(c.render() for c in components)
```

## Dataclasses et Attrs

```python
from dataclasses import dataclass, field
from attrs import define


# Dataclass
@dataclass
class UserDTO:
    id: int
    email: str
    name: str | None = None
    roles: list[str] = field(default_factory=list)


# Attrs (préféré dans ce projet)
@define
class ArticleVM:
    title: str
    content: str
    author: UserDTO
    tags: list[str] = []
```

## Patterns Spécifiques au Projet

### ViewModels

```python
from typing import TYPE_CHECKING, cast

from attrs import define

from app.flask.lib.view_model import ViewModel

if TYPE_CHECKING:
    from app.models.auth import User


@define
class UserVM(ViewModel):
    @property
    def user(self) -> User:
        return cast("User", self._model)

    def extra_attrs(self) -> dict[str, Any]:
        return {
            "full_name": self.user.full_name,
            "avatar_url": self.user.photo_image_signed_url(),
        }
```

### Flask Views

```python
from flask import Response, render_template
from flask.views import MethodView


class UserDetailView(MethodView):
    def get(self, id: str) -> str:
        user = get_obj(id, User)
        return render_template("user.j2", user=user)

    def post(self, id: str) -> Response | str:
        # Peut retourner Response ou str
        ...
```

### Services avec SVCS

```python
from typing import TYPE_CHECKING

import svcs

if TYPE_CHECKING:
    from app.services.notifications import NotificationService


def send_notification(user_id: int, message: str) -> None:
    service: NotificationService = svcs.flask.get(NotificationService)
    service.send(user_id, message)
```

## Résolution d'Erreurs Courantes

### "X is not defined"

```python
# Erreur: User is not defined
def get_user() -> User:
    ...

# Solution: Utiliser annotations différées
from __future__ import annotations

def get_user() -> User:  # OK maintenant
    ...
```

### Incompatibilité Optional

```python
# Erreur: Argument of type "str | None" cannot be assigned to parameter of type "str"
def process(value: str) -> None:
    ...

name: str | None = get_name()
process(name)  # Erreur!

# Solution: Vérifier None explicitement
if name is not None:
    process(name)  # OK

# Ou utiliser une valeur par défaut
process(name or "default")  # OK
```

### List vs Sequence

```python
from collections.abc import Sequence

# Accepte list, tuple, etc. (lecture seule)
def process_items(items: Sequence[str]) -> None:
    for item in items:
        print(item)

# Accepte seulement list (mutation possible)
def append_item(items: list[str], item: str) -> None:
    items.append(item)
```

## Outils de Vérification

```bash
# Type checker principal
uv run ty check

# Alternative avec messages détaillés
uv run pyrefly

# Vérifier un fichier spécifique
uv run ty check src/app/models/auth.py
```

## Ressources

- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 604 - Union Syntax](https://peps.python.org/pep-0604/)
- [SQLAlchemy 2.0 Typing](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html)
- [typing module docs](https://docs.python.org/3/library/typing.html)
