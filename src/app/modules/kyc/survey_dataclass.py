# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Class and ModelLoder abstract class for survey wizard."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import attr

from app.enums import CommunityEnum, ContactTypeEnum


@attr.mutable
class SurveyProfile:
    id: str = ""
    description: str = ""
    community: CommunityEnum = ""
    contact_type: ContactTypeEnum = ""
    groups: list[Group] = attr.field(factory=list)
    _organisation_field_cache: str = ""

    @property
    def label(self):
        return self.description

    @property
    def organisation_field(self) -> str:
        """Name of the field that contains declared organisation name.

        May be different field for different Profile.
        """
        if not self._organisation_field_cache:
            for group in self.groups:
                for field, _ in group.survey_fields:
                    if field.is_organisation:
                        self._organisation_field_cache = field.name
                        break
                if self._organisation_field_cache:
                    break
        return self._organisation_field_cache

    def fields(self, mandatory: bool = False) -> Iterator[SurveyField]:
        """Iterator on list of SurveyField of the profile.

        If mandatory, return only mandatory fields (code "M").
        """
        for group in self.groups:
            for survey_field, code in group.survey_fields:
                if not mandatory or code == "M":
                    yield survey_field


@attr.mutable
class Group:
    label: str = ""
    survey_fields: list[tuple[SurveyField, str]] = attr.field(factory=list)


@attr.mutable
class SurveyField:
    id: str = ""
    name: str = ""
    public_maxi: bool = False
    public_default: bool = False
    public_mini: bool = False
    validate_changes: bool = False
    is_organisation: bool = False
    type: str = ""
    description: str = ""
    upper_message: str = ""

    def is_visible(self, level: int) -> bool:
        if level == 0:  # minimal
            return self.public_mini
        elif level == 1:  # medium (default)
            return self.public_default
        return self.public_maxi


@attr.frozen
class SurveyCommunity:
    id: str
    label: str
    profiles: list = attr.field(factory=list)


@attr.frozen
class SurveyCommunities:
    _communities: list[SurveyCommunity] = attr.field(factory=list)

    def add_profile(self, profile: SurveyProfile):
        community_name = profile.community.name
        if community := self.get(community_name):
            community.profiles.append(profile)
        else:
            community = SurveyCommunity(
                id=community_name,
                label=str(profile.community),
                profiles=[profile],
            )
            self._communities.append(community)

    def get(self, community_name: str) -> SurveyCommunity | None:
        for community in self._communities:
            if community.id == community_name:
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
