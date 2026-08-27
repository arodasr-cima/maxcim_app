from __future__ import annotations

import pytest

from maxcim import create_app
from maxcim.extensions import db


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "DEMO_MODE": True,
            "SEED_DEMO_DATA": True,
            "AUTO_CREATE_DB": True,
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def logged_client(client, app):
    response = client.post(
        "/login",
        data={"email": app.config["DEMO_EMAIL"], "password": app.config["DEMO_PASSWORD"]},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client
