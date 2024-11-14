# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from collections.abc import Sequence

import rich
import sqlalchemy as sa
from attr import field, frozen
from cleez.colors import dim
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session
from mimesis.locales import Locale
from sqlalchemy.orm import scoped_session

from app.models.base import Base
from app.modules.admin.invitations import invite_users
from app.modules.events.models import participation_table
from app.modules.swork.models import Comment, group_members_table
from app.services.roles import add_role
from app.services.social_graph import adapt

from ._generators.biz import EditorialProductGenerator
from ._generators.content import PressReleaseGenerator
from ._generators.events import EventGenerator
from ._generators.groups import GroupGenerator
from ._generators.orgs import OrgGenerator
from ._generators.social import PostGenerator
from ._generators.users import UserGenerator

sample = random.choice

FAKERS_SETTINGS = [
    # SWORK
    ("users", UserGenerator, 500),  # 500
    ("groups", GroupGenerator, 50),  # 50
    ("organisations", OrgGenerator, 60),  # 60
    # Content
    ("events", EventGenerator, 500),  # 500
    # ("articles", ArticleGenerator, 500),
    # ("photos", PhotoGenerator, 100),
    ("press-releases", PressReleaseGenerator, 200),  # 200
    # Social
    # ("comments", CommentGenerator, 1000),
    ("posts", PostGenerator, 500),  # 1000
    # Biz
    ("editorial-products", EditorialProductGenerator, 100),
]

FAKER_TEST_SETTINGS = [
    (key, generator, count // 10) for (key, generator, count) in FAKERS_SETTINGS
]


@frozen
class FakerService:
    db: SQLAlchemy

    locale: Locale = field(default=Locale("fr"))

    users: list = field(factory=list)
    articles: list = field(factory=list)
    settings: Sequence = field(default=tuple(FAKERS_SETTINGS))
    repository: dict = field(factory=dict)

    @property
    def session(self) -> scoped_session[Session]:
        return self.db.session

    def generate_fake_entities(self) -> None:
        self.session.flush()
        for name, faker_class, count in self.settings:
            rich.print(f"[dim]Generating {name}...[/dim]")
            faker = faker_class(self.repository, self.locale)
            objs = faker.make_objects(count)
            self.persist_objects(objs)
            self.session.flush()
            self.repository[name] = objs

        print(dim("Generating relationships..."))
        self.generate_fake_relationships()
        print(dim("Updating counts..."))
        # self.update_counts()
        self.session.flush()

    def generate_fake_relationships(self) -> None:
        self.generate_fake_org_membership()
        self.generate_fake_invitations()
        self.generate_fake_group_membership()
        self.generate_fake_followers_for_users()
        self.generate_fake_followers_for_orgs()
        # self.generate_fake_likes()
        self.generate_fake_tags()
        self.generate_fake_event_participations()

        self.session.flush()

    def generate_fake_org_membership(self) -> None:
        organisations = self.repository["organisations"]
        users = self.repository["users"]
        for user in users:
            # if user already got a AUTO organisation, keep it at 80%
            # this will test the garbage collector
            if user.organisation_id and random.randint(1, 100) <= 80:
                continue
            # only 80% of user in official organisation
            if random.randint(1, 100) <= 20:
                continue
            organisation = sample(organisations)
            # add an invitation
            invite_users(user.email, organisation.id)
            user.organisation_id = organisation.id
            profile = user.profile
            profile.induce_organisation_name(organisation.name)
            self.session.flush()
            if len(organisation.members) == 1:
                add_role(user, "MANAGER")
                add_role(user, "LEADER")
            elif random.randint(1, 100) <= 30:
                # 30% of other members become manager too
                add_role(user, "MANAGER")

        self.session.flush()

    def generate_fake_invitations(self) -> None:
        organisations = self.repository["organisations"]
        users = self.repository["users"]
        for organisation in organisations:
            # generate 5 random invitations for each org
            for _i in range(5):
                user = sample(users)
                invite_users(user.email, organisation.id)
        self.session.flush()

    def generate_fake_followers_for_users(self) -> None:
        users = self.repository["users"]
        for user in users:
            max_count = min(20, len(users))
            count = random.randint(0, max_count)
            followers = random.sample(users, count)

            # can't follow oneself
            if user in followers:
                followers.remove(user)

            for follower in followers:
                adapt(follower).follow(user)

        self.session.flush()

    def generate_fake_followers_for_orgs(self) -> None:
        users = self.repository["users"]
        orgs = self.repository["organisations"]
        for org in orgs:
            max_count = min(20, len(orgs))
            count = random.randint(0, max_count)
            followers = random.sample(users, count)

            for follower in followers:
                adapt(follower).follow(org)

        self.session.flush()

    def generate_fake_likes(self) -> None:
        users = self.repository["users"]
        articles = self.repository["articles"]
        for article in articles:
            max_count = min(10, len(users))
            count = int(abs(random.normalvariate(0, max_count)))
            count = min(count, max_count)
            for user in random.sample(users, count):
                adapt(user).like(article)
            article.like_count = adapt(article).num_likes()

        self.session.flush()

    def generate_fake_views(self) -> None:
        users = self.repository["users"]
        articles = self.repository["articles"]
        for article in articles:
            max_count = min(10, len(users))
            count = int(abs(random.normalvariate(0, max_count)))
            count = min(count, max_count)
            for user in random.sample(users, count):
                adapt(user).like(article)
            article.like_count = adapt(article).num_likes()

        self.session.flush()

    def generate_fake_group_membership(self) -> None:
        users = self.repository["users"]
        groups = self.repository["groups"]
        for group in groups:
            max_count = min(20, len(users))
            count = random.randint(0, max_count)
            members = random.sample(users, count)
            for m in members:
                stmt = sa.insert(group_members_table).values(
                    user_id=m.id, group_id=group.id
                )
                self.session.execute(stmt)

            group.num_members = count

        self.session.flush()

    def generate_fake_tags(self) -> None:
        return
        # users = self.repository["users"]
        # articles = self.repository["articles"]
        # for article in articles:
        #     count = int(abs(random.normalvariate(0, 10)))
        #     for user in random.sample(users, count):
        #         tag = TagApplication()
        #         tag.owner = user
        #         tag.label = random.choice(TAGS)
        #         tag.object_id = f"article:{article.id}"
        #         self.session.add(tag)
        #
        # self.session.flush()

    def generate_fake_event_participations(self) -> None:
        users = self.repository["users"]
        events = self.repository["events"]
        for event in events:
            max_count = min(20, len(users))
            count = random.randint(0, max_count)
            participants = random.sample(users, count)
            for m in participants:
                stmt = sa.insert(participation_table).values(
                    user_id=m.id, event_id=event.id
                )
                self.session.execute(stmt)

        self.session.flush()

    def update_counts(self) -> None:
        articles = self.repository["articles"]
        all_comments: set[Comment] = self.repository["comments"]
        for article in articles:
            comments = {
                c for c in all_comments if c.object_id == f"article:{article.id}"
            }
            article.comment_count = len(comments)

        self.session.flush()

    def persist_objects(self, objects: list[Base]) -> None:
        for obj in objects:
            self.session.add(obj)
