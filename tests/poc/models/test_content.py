# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for BWContent model."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from advanced_alchemy.types.file_object import FileObject

from poc.blueprints.bw_activation_full.models import BWContent, BWContentRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from poc.blueprints.bw_activation_full.models import BusinessWall


class TestBWContent:
    """Tests for BWContent model."""

    def test_create_content(self, db_session: Session, business_wall: BusinessWall):
        """Test creating BWContent."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            organization_type="Entreprise",
            description="We are a leading media company",
            baseline="Innovation in journalism",
            website="https://example.com",
            email="contact@example.com",
            phone="+33 1 23 45 67 89",
        )
        db_session.add(content)
        db_session.commit()

        assert content.id is not None
        assert content.business_wall_id == business_wall.id
        assert content.official_name == "My Organization"
        assert content.organization_type == "Entreprise"
        assert content.description == "We are a leading media company"
        assert content.baseline == "Innovation in journalism"
        assert content.website == "https://example.com"

    def test_content_repr(self, db_session: Session, business_wall: BusinessWall):
        """Test BWContent __repr__."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="Test Org",
        )
        db_session.add(content)
        db_session.commit()

        repr_str = repr(content)
        assert "BWContent" in repr_str
        assert "Test Org" in repr_str

    def test_content_with_address(self, db_session: Session, business_wall: BusinessWall):
        """Test BWContent with full address."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            address="123 Main Street",
            city="Paris",
            zip_code="75001",
            country="France",
        )
        db_session.add(content)
        db_session.commit()

        assert content.address == "123 Main Street"
        assert content.city == "Paris"
        assert content.zip_code == "75001"
        assert content.country == "France"

    def test_content_with_administrative_data(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with administrative identifiers."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            siren="123456789",
            tva_number="FR12345678901",
            cppap="0123A12345",
        )
        db_session.add(content)
        db_session.commit()

        assert content.siren == "123456789"
        assert content.tva_number == "FR12345678901"
        assert content.cppap == "0123A12345"

    def test_content_with_social_media(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with social media links."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            twitter_url="https://twitter.com/myorg",
            linkedin_url="https://linkedin.com/company/myorg",
            facebook_url="https://facebook.com/myorg",
        )
        db_session.add(content)
        db_session.commit()

        assert content.twitter_url == "https://twitter.com/myorg"
        assert content.linkedin_url == "https://linkedin.com/company/myorg"
        assert content.facebook_url == "https://facebook.com/myorg"

    def test_content_with_ontology_selections(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with ontology selections (JSON arrays)."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            topics=["technology", "business", "innovation"],
            geographic_zones=["france", "europe", "international"],
            sectors=["media", "communication", "digital"],
        )
        db_session.add(content)
        db_session.commit()

        assert content.topics == ["technology", "business", "innovation"]
        assert content.geographic_zones == ["france", "europe", "international"]
        assert content.sectors == ["media", "communication", "digital"]

    def test_content_with_member_list(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with member IDs list."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            member_ids=[1, 2, 3, 4, 5],
        )
        db_session.add(content)
        db_session.commit()

        assert content.member_ids == [1, 2, 3, 4, 5]
        assert len(content.member_ids) == 5

    def test_content_with_client_list(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with client list (for PR type)."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="PR Agency",
            client_list=["Acme Corp", "XYZ Industries", "Global Media Ltd"],
        )
        db_session.add(content)
        db_session.commit()

        assert content.client_list == ["Acme Corp", "XYZ Industries", "Global Media Ltd"]
        assert len(content.client_list) == 3

    @pytest.mark.skip(reason="FileObject storage requires backend configuration")
    def test_content_with_logo(self, db_session: Session, business_wall: BusinessWall):
        """Test BWContent with logo FileObject."""
        logo = FileObject(
            backend="local",
            filename="logo.png",
            content=b"fake-image-data",
            metadata={"alt": "Company Logo", "width": 200, "height": 100},
        )

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            logo=logo,
        )
        db_session.add(content)
        db_session.commit()

        assert content.logo is not None
        assert content.logo.filename == "logo.png"
        assert content.logo.metadata["alt"] == "Company Logo"

    @pytest.mark.skip(reason="FileObject storage requires backend configuration")
    def test_content_with_banner(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with banner FileObject."""
        banner = FileObject(
            backend="local",
            filename="banner.jpg",
            content=b"fake-banner-data",
            metadata={"alt": "Company Banner"},
        )

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            banner=banner,
        )
        db_session.add(content)
        db_session.commit()

        assert content.banner is not None
        assert content.banner.filename == "banner.jpg"

    @pytest.mark.skip(reason="FileObject storage requires backend configuration")
    def test_content_with_gallery(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with gallery FileObjectList."""
        gallery = [
            FileObject(
                backend="local",
                filename=f"gallery_{i}.jpg",
                content=f"fake-image-{i}".encode(),
            )
            for i in range(3)
        ]

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            gallery=gallery,
        )
        db_session.add(content)
        db_session.commit()

        assert content.gallery is not None
        assert len(content.gallery) == 3
        assert content.gallery[0].filename == "gallery_0.jpg"
        assert content.gallery[1].filename == "gallery_1.jpg"
        assert content.gallery[2].filename == "gallery_2.jpg"

    @pytest.mark.skip(reason="FileObject storage requires backend configuration")
    def test_content_with_all_files(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent with logo, banner, and gallery."""
        logo = FileObject(
            backend="local",
            filename="logo.png",
            content=b"logo-data",
        )
        banner = FileObject(
            backend="local",
            filename="banner.jpg",
            content=b"banner-data",
        )
        gallery = [
            FileObject(
                backend="local",
                filename=f"gallery_{i}.jpg",
                content=f"image-{i}".encode(),
            )
            for i in range(5)
        ]

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
            logo=logo,
            banner=banner,
            gallery=gallery,
        )
        db_session.add(content)
        db_session.commit()

        assert content.logo is not None
        assert content.banner is not None
        assert content.gallery is not None
        assert len(content.gallery) == 5

    def test_content_relationship_to_business_wall(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test BWContent relationship to BusinessWall (one-to-one)."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
        )
        db_session.add(content)
        db_session.commit()

        # Access relationship
        assert content.business_wall is not None
        assert content.business_wall.id == business_wall.id

        # Access from BW side
        db_session.refresh(business_wall)
        assert business_wall.content is not None
        assert business_wall.content.id == content.id

    def test_content_empty_json_fields_default_to_empty_list(
        self, db_session: Session, business_wall: BusinessWall
    ):
        """Test that JSON array fields default to empty lists."""
        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="My Organization",
        )
        db_session.add(content)
        db_session.commit()

        assert content.topics == []
        assert content.geographic_zones == []
        assert content.sectors == []
        assert content.member_ids == []
        assert content.client_list == []


class TestBWContentRepository:
    """Tests for BWContentRepository."""

    def test_repository_add(self, db_session: Session, business_wall: BusinessWall):
        """Test repository add operation."""
        repo = BWContentRepository(session=db_session)

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="Test Organization",
        )

        saved = repo.add(content)

        assert saved.id is not None
        assert saved.official_name == "Test Organization"

    def test_repository_get(self, db_session: Session, business_wall: BusinessWall):
        """Test repository get operation."""
        repo = BWContentRepository(session=db_session)

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="Test Organization",
        )
        repo.add(content)

        retrieved = repo.get(content.id)

        assert retrieved is not None
        assert retrieved.id == content.id
        assert retrieved.official_name == "Test Organization"

    def test_repository_update(self, db_session: Session, business_wall: BusinessWall):
        """Test repository update operation."""
        repo = BWContentRepository(session=db_session)

        content = BWContent(
            business_wall_id=business_wall.id,
            official_name="Old Name",
        )
        repo.add(content)

        # Update entity attributes
        content.official_name = "New Name"
        updated = repo.update(content)

        assert updated.official_name == "New Name"
