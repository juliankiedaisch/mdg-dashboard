# Assistant Module - Tests: Tag Permission System
"""
Test suite for the tag-based source access control system.
Covers tag CRUD, dynamic permissions, source-tag assignment, and RAG filtering.

Run with: python -m pytest backend/modules/assistant/tests/test_tags.py -v
"""
import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


@pytest.fixture
def app():
    """Create a minimal Flask app with an in-memory SQLite database for testing."""
    from flask import Flask
    from src.db import db as _db

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['SESSION_TYPE'] = 'filesystem'

    _db.init_app(app)

    with app.app_context():
        # Import all models so tables get created
        from modules.assistant.models.tag import AssistantTag, source_tag_mapping  # noqa
        from modules.assistant.models.source_config import SourceConfig  # noqa
        from modules.assistant.models.assistant_model import AssistantModel, AssistantLog  # noqa
        from modules.assistant.models.chat_session import ChatSession  # noqa
        from modules.assistant.models.chat_message import ChatMessage  # noqa
        from src.db_models import Permission, Profile, User, Group  # noqa

        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    """Get db session."""
    from src.db import db as _db
    return _db


# ── Tag Model Tests ─────────────────────────────────────────────────

class TestAssistantTagModel:
    """Test AssistantTag model directly."""

    def test_create_tag(self, app, db):
        from modules.assistant.models.tag import AssistantTag

        with app.app_context():
            tag = AssistantTag(name='engineering_wiki', description='Engineering docs')
            db.session.add(tag)
            db.session.commit()

            assert tag.id is not None
            assert tag.name == 'engineering_wiki'
            assert tag.permission_id == 'ASSISTANT_TAG_ENGINEERING_WIKI'

    def test_tag_to_dict(self, app, db):
        from modules.assistant.models.tag import AssistantTag

        with app.app_context():
            tag = AssistantTag(name='hr_documents', description='HR related')
            db.session.add(tag)
            db.session.commit()

            d = tag.to_dict()
            assert d['name'] == 'hr_documents'
            assert d['permission_id'] == 'ASSISTANT_TAG_HR_DOCUMENTS'
            assert d['description'] == 'HR related'
            assert 'created_at' in d

    def test_tag_unique_name(self, app, db):
        from modules.assistant.models.tag import AssistantTag
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            tag1 = AssistantTag(name='unique_tag')
            db.session.add(tag1)
            db.session.commit()

            tag2 = AssistantTag(name='unique_tag')
            db.session.add(tag2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_source_tag_relationship(self, app, db):
        from modules.assistant.models.tag import AssistantTag
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag = AssistantTag(name='internal_docs')
            source = SourceConfig(name='Wiki', source_type='bookstack')
            db.session.add_all([tag, source])
            db.session.commit()

            source.tags.append(tag)
            db.session.commit()

            assert len(source.tags) == 1
            assert source.tags[0].name == 'internal_docs'
            assert len(tag.sources) == 1
            assert tag.sources[0].name == 'Wiki'

    def test_source_tag_names_property(self, app, db):
        from modules.assistant.models.tag import AssistantTag
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag1 = AssistantTag(name='tag_a')
            tag2 = AssistantTag(name='tag_b')
            source = SourceConfig(name='Src', source_type='filesystem')
            db.session.add_all([tag1, tag2, source])
            db.session.commit()

            source.tags = [tag1, tag2]
            db.session.commit()

            assert set(source.tag_names) == {'tag_a', 'tag_b'}

    def test_source_to_dict_includes_tags(self, app, db):
        from modules.assistant.models.tag import AssistantTag
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag = AssistantTag(name='public_docs')
            source = SourceConfig(name='Pub', source_type='bookstack')
            db.session.add_all([tag, source])
            db.session.commit()

            source.tags.append(tag)
            db.session.commit()

            d = source.to_dict()
            assert 'tags' in d
            assert len(d['tags']) == 1
            assert d['tags'][0]['name'] == 'public_docs'


# ── Dynamic Permission Tests ────────────────────────────────────────

class TestDynamicPermissions:
    """Test dynamic permission registration/removal."""

    def test_register_dynamic_permission(self, app, db):
        from src.permissions import register_dynamic_permission
        from src.db_models import Permission

        with app.app_context():
            register_dynamic_permission('ASSISTANT_TAG_TEST', 'Test tag permission')
            perm = Permission.query.get('ASSISTANT_TAG_TEST')
            assert perm is not None
            assert perm.module == 'assistant'
            assert perm.description == 'Test tag permission'

    def test_register_dynamic_permission_idempotent(self, app, db):
        from src.permissions import register_dynamic_permission
        from src.db_models import Permission

        with app.app_context():
            register_dynamic_permission('ASSISTANT_TAG_IDEM', 'First')
            register_dynamic_permission('ASSISTANT_TAG_IDEM', 'Updated')

            perm = Permission.query.get('ASSISTANT_TAG_IDEM')
            assert perm is not None
            assert perm.description == 'Updated'

    def test_unregister_dynamic_permission(self, app, db):
        from src.permissions import register_dynamic_permission, unregister_dynamic_permission
        from src.db_models import Permission

        with app.app_context():
            register_dynamic_permission('ASSISTANT_TAG_REMOVE', 'To remove')
            assert Permission.query.get('ASSISTANT_TAG_REMOVE') is not None

            unregister_dynamic_permission('ASSISTANT_TAG_REMOVE')
            assert Permission.query.get('ASSISTANT_TAG_REMOVE') is None

    def test_unregister_nonexistent_permission(self, app, db):
        from src.permissions import unregister_dynamic_permission

        with app.app_context():
            # Should not raise error
            unregister_dynamic_permission('DOES_NOT_EXIST')

    def test_dynamic_permission_in_permission_list(self, app, db):
        from src.permissions import register_dynamic_permission
        from src.db_models import Permission

        with app.app_context():
            register_dynamic_permission('ASSISTANT_TAG_VISIBLE', 'Should be visible')

            all_perms = Permission.query.all()
            perm_ids = [p.id for p in all_perms]
            assert 'ASSISTANT_TAG_VISIBLE' in perm_ids


# ── Tag Service Tests ───────────────────────────────────────────────

class TestTagService:
    """Test tag CRUD service functions."""

    def test_create_tag(self, app, db):
        from modules.assistant.services.tag_service import create_tag
        from src.db_models import Permission

        with app.app_context():
            result, err = create_tag('my_tag', 'My description')
            assert err is None
            assert result['name'] == 'my_tag'
            assert result['permission_id'] == 'ASSISTANT_TAG_MY_TAG'

            # Permission should have been created
            perm = Permission.query.get('ASSISTANT_TAG_MY_TAG')
            assert perm is not None

    def test_create_tag_normalizes_name(self, app, db):
        from modules.assistant.services.tag_service import create_tag

        with app.app_context():
            result, err = create_tag('My Tag Name', '')
            assert err is None
            assert result['name'] == 'my_tag_name'

    def test_create_tag_duplicate(self, app, db):
        from modules.assistant.services.tag_service import create_tag

        with app.app_context():
            create_tag('dup_tag')
            result, err = create_tag('dup_tag')
            assert result is None
            assert 'already exists' in err

    def test_create_tag_invalid_name(self, app, db):
        from modules.assistant.services.tag_service import create_tag

        with app.app_context():
            result, err = create_tag('')
            assert result is None
            assert 'required' in err

    def test_create_tag_invalid_characters(self, app, db):
        from modules.assistant.services.tag_service import create_tag

        with app.app_context():
            result, err = create_tag('bad-name!')
            assert result is None
            assert 'letters, numbers' in err

    def test_update_tag(self, app, db):
        from modules.assistant.services.tag_service import create_tag, update_tag
        from src.db_models import Permission

        with app.app_context():
            tag, _ = create_tag('old_name')
            tag_id = tag['id']

            # Update name
            result, err = update_tag(tag_id, name='new_name')
            assert err is None
            assert result['name'] == 'new_name'
            assert result['permission_id'] == 'ASSISTANT_TAG_NEW_NAME'

            # Old permission should be gone, new one should exist
            assert Permission.query.get('ASSISTANT_TAG_OLD_NAME') is None
            assert Permission.query.get('ASSISTANT_TAG_NEW_NAME') is not None

    def test_update_tag_description_only(self, app, db):
        from modules.assistant.services.tag_service import create_tag, update_tag

        with app.app_context():
            tag, _ = create_tag('stable_name')
            result, err = update_tag(tag['id'], description='New desc')
            assert err is None
            assert result['name'] == 'stable_name'

    def test_delete_tag(self, app, db):
        from modules.assistant.services.tag_service import create_tag, delete_tag
        from modules.assistant.models.tag import AssistantTag
        from src.db_models import Permission

        with app.app_context():
            tag, _ = create_tag('to_delete')
            tag_id = tag['id']

            result, err = delete_tag(tag_id)
            assert err is None
            assert result['status'] is True

            assert AssistantTag.query.get(tag_id) is None
            assert Permission.query.get('ASSISTANT_TAG_TO_DELETE') is None

    def test_delete_nonexistent_tag(self, app, db):
        from modules.assistant.services.tag_service import delete_tag

        with app.app_context():
            result, err = delete_tag(9999)
            assert result is None
            assert 'not found' in err

    def test_get_all_tags(self, app, db):
        from modules.assistant.services.tag_service import create_tag, get_all_tags

        with app.app_context():
            create_tag('alpha')
            create_tag('beta')
            tags = get_all_tags()
            assert len(tags) == 2
            names = [t['name'] for t in tags]
            assert 'alpha' in names
            assert 'beta' in names


# ── Source Tag Assignment Tests ──────────────────────────────────────

class TestSourceTagAssignment:
    """Test assigning tags to sources."""

    def test_set_source_tags(self, app, db):
        from modules.assistant.services.tag_service import create_tag, set_source_tags
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag1, _ = create_tag('tag1')
            tag2, _ = create_tag('tag2')
            source = SourceConfig(name='Test Source', source_type='bookstack')
            db.session.add(source)
            db.session.commit()

            result, err = set_source_tags(source.id, [tag1['id'], tag2['id']])
            assert err is None
            assert len(result['tags']) == 2

    def test_set_source_tags_replaces_existing(self, app, db):
        from modules.assistant.services.tag_service import create_tag, set_source_tags
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag1, _ = create_tag('first')
            tag2, _ = create_tag('second')
            source = SourceConfig(name='Src', source_type='filesystem')
            db.session.add(source)
            db.session.commit()

            set_source_tags(source.id, [tag1['id']])
            result, _ = set_source_tags(source.id, [tag2['id']])
            assert len(result['tags']) == 1
            assert result['tags'][0]['name'] == 'second'

    def test_get_source_tags(self, app, db):
        from modules.assistant.services.tag_service import create_tag, set_source_tags, get_source_tags
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag, _ = create_tag('visible')
            source = SourceConfig(name='S', source_type='bookstack')
            db.session.add(source)
            db.session.commit()

            set_source_tags(source.id, [tag['id']])
            tags = get_source_tags(source.id)
            assert len(tags) == 1
            assert tags[0]['name'] == 'visible'

    def test_set_source_tags_nonexistent_source(self, app, db):
        from modules.assistant.services.tag_service import set_source_tags

        with app.app_context():
            result, err = set_source_tags(9999, [])
            assert result is None
            assert 'not found' in err


# ── User Tag Permission Tests ────────────────────────────────────────

class TestUserTagPermissions:
    """Test that user permissions correctly map to allowed tags."""

    def test_get_user_allowed_tags(self, app, db):
        from modules.assistant.services.tag_service import create_tag, get_user_allowed_tags

        with app.app_context():
            create_tag('engineering')
            create_tag('hr_docs')
            create_tag('secret')

            # User has permissions for engineering and hr_docs only
            user_perms = {'ASSISTANT_TAG_ENGINEERING', 'ASSISTANT_TAG_HR_DOCS'}
            allowed = get_user_allowed_tags(user_perms)
            assert set(allowed) == {'engineering', 'hr_docs'}

    def test_get_user_allowed_tags_none(self, app, db):
        from modules.assistant.services.tag_service import create_tag, get_user_allowed_tags

        with app.app_context():
            create_tag('restricted')

            allowed = get_user_allowed_tags(set())
            assert allowed == []

    def test_get_user_allowed_source_ids(self, app, db):
        from modules.assistant.services.tag_service import create_tag, set_source_tags, get_user_allowed_source_ids
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag1, _ = create_tag('allowed_tag')
            tag2, _ = create_tag('forbidden_tag')

            src1 = SourceConfig(name='Allowed Source', source_type='bookstack')
            src2 = SourceConfig(name='Forbidden Source', source_type='bookstack')
            db.session.add_all([src1, src2])
            db.session.commit()

            set_source_tags(src1.id, [tag1['id']])
            set_source_tags(src2.id, [tag2['id']])

            user_perms = {'ASSISTANT_TAG_ALLOWED_TAG'}
            allowed_ids = get_user_allowed_source_ids(user_perms)
            assert src1.id in allowed_ids
            assert src2.id not in allowed_ids

    def test_get_user_allowed_source_ids_no_perms(self, app, db):
        from modules.assistant.services.tag_service import get_user_allowed_source_ids

        with app.app_context():
            allowed_ids = get_user_allowed_source_ids(set())
            assert allowed_ids == []

    def test_partial_tag_permissions(self, app, db):
        """User with partial tag permissions only sees matching sources."""
        from modules.assistant.services.tag_service import create_tag, set_source_tags, get_user_allowed_tags
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag_eng, _ = create_tag('engineering')
            tag_hr, _ = create_tag('hr')
            tag_finance, _ = create_tag('finance')

            src1 = SourceConfig(name='Eng Wiki', source_type='bookstack')
            src2 = SourceConfig(name='HR Wiki', source_type='bookstack')
            src3 = SourceConfig(name='Finance Wiki', source_type='bookstack')
            db.session.add_all([src1, src2, src3])
            db.session.commit()

            set_source_tags(src1.id, [tag_eng['id']])
            set_source_tags(src2.id, [tag_hr['id']])
            set_source_tags(src3.id, [tag_finance['id']])

            # User only has engineering permission
            user_perms = {'ASSISTANT_TAG_ENGINEERING'}
            allowed = get_user_allowed_tags(user_perms)
            assert allowed == ['engineering']


# ── Default Tag Migration Tests ──────────────────────────────────────

class TestDefaultTagMigration:
    """Test that default tags are created and assigned properly."""

    def test_ensure_default_tag(self, app, db):
        from modules.assistant.services.tag_service import ensure_default_tag
        from modules.assistant.models.tag import AssistantTag

        with app.app_context():
            ensure_default_tag()
            tag = AssistantTag.query.filter_by(name='default_assistant_source').first()
            assert tag is not None

    def test_ensure_default_tag_assigns_to_untagged_sources(self, app, db):
        from modules.assistant.services.tag_service import ensure_default_tag
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            # Create sources without tags
            src1 = SourceConfig(name='Untagged1', source_type='bookstack')
            src2 = SourceConfig(name='Untagged2', source_type='filesystem')
            db.session.add_all([src1, src2])
            db.session.commit()

            ensure_default_tag()

            # Both should now have the default tag
            for src in [src1, src2]:
                db.session.refresh(src)
                assert len(src.tags) == 1
                assert src.tags[0].name == 'default_assistant_source'

    def test_ensure_default_tag_idempotent(self, app, db):
        from modules.assistant.services.tag_service import ensure_default_tag
        from modules.assistant.models.tag import AssistantTag

        with app.app_context():
            ensure_default_tag()
            ensure_default_tag()  # Should not create duplicate
            count = AssistantTag.query.filter_by(name='default_assistant_source').count()
            assert count == 1

    def test_sync_tag_permissions(self, app, db):
        from modules.assistant.services.tag_service import create_tag, sync_tag_permissions
        from src.db_models import Permission

        with app.app_context():
            create_tag('sync_test')

            # Delete the permission manually
            perm = Permission.query.get('ASSISTANT_TAG_SYNC_TEST')
            if perm:
                db.session.delete(perm)
                db.session.commit()

            # sync should re-create it
            sync_tag_permissions()
            perm = Permission.query.get('ASSISTANT_TAG_SYNC_TEST')
            assert perm is not None


# ── RAG Filtering Tests ─────────────────────────────────────────────

class TestRAGTagFiltering:
    """Test that the RAG pipeline respects tag permissions."""

    def test_vector_store_search_with_permission_tags(self):
        """Test that VectorStore.search passes permission_tags to Qdrant filter."""
        from modules.assistant.rag.vector_store import VectorStore
        from unittest.mock import MagicMock, patch

        vs = VectorStore.__new__(VectorStore)
        vs.collection_name = 'test'
        vs.vector_size = 768
        vs.qdrant_url = 'http://mock:6333'

        mock_client = MagicMock()
        mock_client.search.return_value = []
        vs._client = mock_client

        # Mock ensure_collection
        vs.ensure_collection = MagicMock()

        # Search with permission tags
        vs.search(query_vector=[0.1] * 768, top_k=5, permission_tags=['engineering', 'hr'])

        # Verify the filter was passed
        call_args = mock_client.search.call_args
        query_filter = call_args.kwargs.get('query_filter') or call_args[1].get('query_filter')
        assert query_filter is not None
        # The filter should contain permission_tags condition
        assert len(query_filter.must) > 0

    def test_vector_store_search_without_tags_no_filter(self):
        """Test that when permission_tags is None, no tag filter is applied."""
        from modules.assistant.rag.vector_store import VectorStore
        from unittest.mock import MagicMock

        vs = VectorStore.__new__(VectorStore)
        vs.collection_name = 'test'
        vs.vector_size = 768
        vs.qdrant_url = 'http://mock:6333'

        mock_client = MagicMock()
        mock_client.search.return_value = []
        vs._client = mock_client
        vs.ensure_collection = MagicMock()

        # Search without permission tags
        vs.search(query_vector=[0.1] * 768, top_k=5, permission_tags=None)

        call_args = mock_client.search.call_args
        query_filter = call_args.kwargs.get('query_filter') or call_args[1].get('query_filter')
        # No filter should be applied
        assert query_filter is None

    def test_retriever_passes_permission_tags(self):
        """Test that Retriever passes permission_tags through to vector search."""
        from modules.assistant.rag.retriever import Retriever
        from unittest.mock import MagicMock, patch

        retriever = Retriever(top_k=3)

        with patch('modules.assistant.rag.retriever.get_embedding_service') as mock_embed, \
             patch('modules.assistant.rag.retriever.get_vector_store') as mock_vs:

            mock_embed_svc = MagicMock()
            mock_embed_svc.embed_text.return_value = [0.1] * 768
            mock_embed.return_value = mock_embed_svc

            mock_store = MagicMock()
            mock_store.search.return_value = []
            mock_vs.return_value = mock_store

            retriever.retrieve('test query', permission_tags=['allowed_tag'])

            mock_store.search.assert_called_once()
            call_kwargs = mock_store.search.call_args
            assert call_kwargs.kwargs.get('permission_tags') == ['allowed_tag'] or \
                   call_kwargs[1].get('permission_tags') == ['allowed_tag']


# ── Admin Tag Change Tests ───────────────────────────────────────────

class TestAdminTagChanges:
    """Test scenarios where admin changes tag assignments."""

    def test_tag_reassignment_updates_sources(self, app, db):
        """When tags are reassigned, sources reflect the change."""
        from modules.assistant.services.tag_service import create_tag, set_source_tags
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag_old, _ = create_tag('old_tag')
            tag_new, _ = create_tag('new_tag')

            source = SourceConfig(name='Mutable', source_type='bookstack')
            db.session.add(source)
            db.session.commit()

            # Initially assign old tag
            set_source_tags(source.id, [tag_old['id']])
            assert source.tag_names == ['old_tag']

            # Reassign to new tag
            set_source_tags(source.id, [tag_new['id']])
            db.session.refresh(source)
            assert source.tag_names == ['new_tag']

    def test_deleting_tag_removes_from_sources(self, app, db):
        """When a tag is deleted, it's removed from all assigned sources."""
        from modules.assistant.services.tag_service import create_tag, set_source_tags, delete_tag
        from modules.assistant.models.source_config import SourceConfig

        with app.app_context():
            tag, _ = create_tag('ephemeral')
            source = SourceConfig(name='Src', source_type='bookstack')
            db.session.add(source)
            db.session.commit()

            set_source_tags(source.id, [tag['id']])
            assert len(source.tags) == 1

            delete_tag(tag['id'])
            db.session.refresh(source)
            assert len(source.tags) == 0
