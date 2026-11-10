from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select, text

from app.core.database import upgrade_schema
from app.entities.models import utc_now


def test_upgrade_preserves_legacy_accounts_sessions_and_mocks():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "app" / "migrations"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_baseline")
        connection.execute(text("DROP TABLE alembic_version"))
        metadata = MetaData()
        metadata.reflect(connection)
        now = utc_now()
        timestamps = {"created_at": now, "updated_at": now}
        connection.execute(metadata.tables["users"].insert().values(
            id=1, email="legacy@example.com", password_hash="old-hash", is_active=True, **timestamps,
        ))
        connection.execute(metadata.tables["sessions"].insert().values(
            id=1, user_id=1, token_hash="old-session-hash", expires_at=now, last_seen_at=now, created_at=now,
        ))
        connection.execute(metadata.tables["mocks"].insert().values(
            id="old-mock", owner_id=1, name="Old mock", desired_status="RUNNING", runtime_status="RUNNING",
            deletion_requested=False, config_version=7, **timestamps,
        ))
        connection.execute(metadata.tables["mock_endpoints"].insert().values(
            id="old-route", mock_id="old-mock", method="GET", path="/legacy",
            status_code=200, response_headers={}, response_body={"existing": True},
            delay_ms=5, enabled=True, **timestamps,
        ))

    for _ in range(2):
        with engine.begin() as connection:
            upgrade_schema(connection)

    with engine.connect() as connection:
        metadata = MetaData()
        metadata.reflect(connection)
        user = connection.execute(select(metadata.tables["users"])).one()
        session = connection.execute(select(metadata.tables["sessions"])).one()
        mock = connection.execute(select(metadata.tables["mocks"])).one()
        endpoint = connection.execute(select(metadata.tables["mock_endpoints"])).one()
        assert (user.email, user.password_hash) == ("legacy@example.com", "old-hash")
        assert (session.user_id, session.token_hash) == (user.id, "old-session-hash")
        assert (mock.owner_id, mock.config_version, mock.runtime_status) == (user.id, 7, "RUNNING")
        assert (mock.default_delay_ms, mock.default_response_headers) == (0, {})
        assert (endpoint.mock_id, endpoint.path, endpoint.response_body) == (mock.id, "/legacy", {"existing": True})
        assert (endpoint.name, endpoint.description) == (None, None)
        assert inspect(connection).has_table("email_verifications")
    engine.dispose()
