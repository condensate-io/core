import uuid
from unittest.mock import MagicMock, patch, PropertyMock
from src.db.schemas import EpisodicItemCreate
from src.db.models import EpisodicItem


def test_ingress_creates_memory_with_provenance(db_session, project):
    mock_qdrant = MagicMock()

    # project.id is "test-project-id" (a non-UUID string set in conftest)
    # IngressAgent will convert it via uuid.uuid5(uuid.NAMESPACE_DNS, "test-project-id")
    expected_project_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(project.id))

    # db_session.query(...).filter(...).first() returns a MagicMock (truthy),
    # so the "project not found" auto-create branch is skipped.
    # We need .first() to return None so we test the auto-create path,
    # OR return a real-looking project. Either way project_id is set at item construction.
    mock_project = MagicMock()
    mock_project.id = expected_project_uuid
    db_session.query.return_value.filter.return_value.first.return_value = mock_project

    # Patch TextEmbedding so no model download occurs
    with patch("src.agents.ingress.TextEmbedding") as MockEmbedding:
        # Make embed() return a fake vector
        mock_vector = MagicMock()
        mock_vector.tolist.return_value = [0.1] * 384
        mock_embed_instance = MagicMock()
        mock_embed_instance.embed.return_value = iter([mock_vector])
        MockEmbedding.return_value = mock_embed_instance

        from src.agents.ingress import IngressAgent

        agent = IngressAgent(db_session, mock_qdrant)

        data = EpisodicItemCreate(
            project_id=str(project.id),
            text="This is a test memory.",
            source="test"
        )

        memory = agent.process_memory(data)

    # Assertions
    assert memory is not None
    assert not isinstance(memory, MagicMock), \
        "process_memory returned a MagicMock — IngressAgent may have failed to initialise"
    assert memory.id is not None
    assert str(memory.project_id) == str(expected_project_uuid), \
        f"Expected project_id {expected_project_uuid}, got {memory.project_id}"
    assert memory.text == "This is a test memory."

    # Verify DB persistence calls
    db_session.add.assert_called()
    db_session.commit.assert_called()

    # Verify Qdrant upsert was attempted
    mock_qdrant.upsert.assert_called_once()
