# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Class and ModelLoder abstract class for survey wizard.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import attr


@attr.mutable
class Profile:
    id: str = ""
    description: str = ""
    community: str = ""
    groups: list[Group] = attr.field(factory=list)

    @property
    def label(self):
        return self.description


@attr.mutable
class Group:
    label: str = ""
    survey_fields: list[tuple[SurveyField, str]] = attr.field(factory=list)


@attr.mutable
class SurveyField:
    id: str = ""
    name: str = ""
    public_allow: bool = False
    public_default: bool = False
    type: str = ""
    description: str = ""
    upper_message: str = ""


@attr.frozen
class Community:
    id: str
    label: str
    profiles: list = attr.field(factory=list)


@attr.frozen
class Communities:
    _communities: list[Community] = attr.field(factory=list)

    def add_profile(self, profile):
        community_label = profile.community
        if community := self.get(community_label):
            community.profiles.append(profile)
        else:
            community = Community(
                id=community_label, label=community_label, profiles=[profile]
            )
            self._communities.append(community)

    def get(self, community_name):
        for community in self._communities:
            if community.label == community_name:
                return community
        return None

    def __iter__(self):
        return iter(self._communities)


class ModelLoader(ABC):
    @abstractmethod
    def parse(self, source: str | Path) -> None: ...

    @property
    @abstractmethod
    def model(self) -> dict[str, Any]: ...
