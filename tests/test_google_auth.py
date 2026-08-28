from __future__ import annotations

import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from maxcim import create_app
from maxcim.extensions import db
from maxcim.models import GoogleIdentity, LearningSession, User
from maxcim.services import google_identity
from maxcim.services.google_identity import (
    GoogleTokenError,
    validate_teacher_claims,
    verify_google_token,
)

TEACHER_EMAIL = "docente@colegiocima.edu.pe"


def _google_app(tmp_path, **overrides):
    config = {
        "TESTING": True,
        "SECRET_KEY": "google-test-secret-that-is-long-enough",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'google.db'}",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "AUTH_PROVIDER": "google",
        "DEMO_MODE": True,
        # The factory must suppress fixtures for every institutional provider.
        "SEED_DEMO_DATA": True,
        "AUTO_CREATE_DB": True,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
        "GOOGLE_OAUTH_CLIENT_ID": "client.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:5000/login/google/callback",
        "GOOGLE_WORKSPACE_DOMAIN": "colegiocima.edu.pe",
        "GOOGLE_ALLOWED_TEACHER_EMAILS": (TEACHER_EMAIL,),
        "GOOGLE_OAUTH_FLOW_MAX_AGE_SECONDS": 600,
        "GOOGLE_OAUTH_TIMEOUT_SECONDS": 5.0,
    }
    config.update(overrides)
    return create_app(config)


class FakeGoogleFlow:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.code_verifier = kwargs.get("code_verifier") or "pkce-verifier"
        self.credentials = SimpleNamespace(id_token="raw-google-id-token")
        self.fetched_code = None
        self.fetched_timeout = None

    def authorization_url(self, **_kwargs):
        return "https://accounts.google.com/o/oauth2/v2/auth?test=1", "state-good"

    def fetch_token(self, *, code, timeout):
        self.fetched_code = code
        self.fetched_timeout = timeout


def _install_fake_google(monkeypatch, nonce_holder):
    flows = []

    def flow_factory(**kwargs):
        flow = FakeGoogleFlow(**kwargs)
        flows.append(flow)
        return flow

    def verify_token(token, client_id, timeout_seconds):
        assert token == "raw-google-id-token"
        assert client_id == "client.apps.googleusercontent.com"
        assert timeout_seconds == 5.0
        return {
            "sub": "google-subject-123",
            "email": TEACHER_EMAIL,
            "email_verified": True,
            "hd": "colegiocima.edu.pe",
            "name": "Docente Institucional",
            "nonce": nonce_holder["nonce"],
        }

    monkeypatch.setattr("maxcim.routes.auth._build_google_flow", flow_factory)
    monkeypatch.setattr("maxcim.routes.auth.verify_google_token", verify_token)
    return flows


def test_google_login_creates_stable_identity_without_demo_classrooms(tmp_path, monkeypatch):
    application = _google_app(tmp_path)
    client = application.test_client()
    nonce_holder = {}
    flows = _install_fake_google(monkeypatch, nonce_holder)

    login_page = client.get("/login").get_data(as_text=True)
    assert "Continuar con Google" in login_page
    assert 'name="password"' not in login_page

    started = client.get("/login/google?next=/material")
    assert started.status_code == 302
    assert started.headers["Location"].startswith("https://accounts.google.com/")
    with client.session_transaction() as flask_session:
        oauth_state = flask_session["google_oauth_flow"]
        nonce_holder["nonce"] = oauth_state["nonce"]
        assert oauth_state["state"] == "state-good"
        assert oauth_state["code_verifier"] == "pkce-verifier"
        assert oauth_state["next"] == "/material"

    callback = client.get("/login/google/callback?state=state-good&code=authorization-code")
    assert callback.status_code == 302
    assert callback.headers["Location"].endswith("/material")
    assert flows[-1].fetched_code == "authorization-code"
    assert flows[-1].fetched_timeout == 5.0
    with client.session_transaction() as flask_session:
        assert flask_session["auth_provider"] == "google"

    dashboard = client.get("/dashboard")
    html = dashboard.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert "Cuenta institucional verificada" in html
    assert "3.º A — Secundaria" not in html

    health = client.get("/health")
    assert health.get_json() == {"mode": "google", "status": "ok"}

    sessions_page = client.get("/sesiones")
    sessions_html = sessions_page.get_data(as_text=True)
    assert sessions_page.status_code == 200
    assert "Integración pendiente de CIMA" in sessions_html
    assert "No hay aulas asignadas" in sessions_html

    assert client.post("/logout").status_code == 302
    client.get("/login/google")
    with client.session_transaction() as flask_session:
        nonce_holder["nonce"] = flask_session["google_oauth_flow"]["nonce"]
    assert client.get(
        "/login/google/callback?state=state-good&code=second-code"
    ).status_code == 302

    with application.app_context():
        user = User.query.one()
        identity = GoogleIdentity.query.one()
        assert application.config["SEED_DEMO_DATA"] is False
        assert user.email == TEACHER_EMAIL
        assert user.display_name == "Docente Institucional"
        assert identity.subject == "google-subject-123"
        assert identity.user_id == user.id
        assert "raw-google-id-token" not in repr(identity.__dict__)
        db.session.remove()
        db.drop_all()


def test_google_login_builds_real_pkce_authorization_request(tmp_path):
    application = _google_app(tmp_path)
    client = application.test_client()

    response = client.get("/login/google?next=/material")
    assert response.status_code == 302
    location = urlsplit(response.headers["Location"])
    parameters = parse_qs(location.query)
    assert location.netloc == "accounts.google.com"
    assert parameters["client_id"] == ["client.apps.googleusercontent.com"]
    assert parameters["redirect_uri"] == [
        "http://127.0.0.1:5000/login/google/callback"
    ]
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["hd"] == ["colegiocima.edu.pe"]
    assert set(parameters["scope"][0].split()) == {"openid", "email", "profile"}
    assert parameters["nonce"][0]
    assert parameters["state"][0]

    with client.session_transaction() as flask_session:
        oauth_state = flask_session["google_oauth_flow"]
        assert oauth_state["state"] == parameters["state"][0]
        assert oauth_state["nonce"] == parameters["nonce"][0]
        assert oauth_state["code_verifier"]
        assert oauth_state["next"] == "/material"

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_google_callback_rejects_mismatched_and_expired_state(tmp_path, monkeypatch):
    application = _google_app(tmp_path)
    client = application.test_client()
    nonce_holder = {}
    _install_fake_google(monkeypatch, nonce_holder)

    client.get("/login/google")
    mismatch = client.get("/login/google/callback?state=altered&code=code")
    assert mismatch.status_code == 302
    assert mismatch.headers["Location"].endswith("/login")

    client.get("/login/google")
    with client.session_transaction() as flask_session:
        oauth_state = dict(flask_session["google_oauth_flow"])
        oauth_state["issued_at"] = int(time.time()) - 601
        flask_session["google_oauth_flow"] = oauth_state
    expired = client.get("/login/google/callback?state=state-good&code=code")
    assert expired.status_code == 302
    assert expired.headers["Location"].endswith("/login")

    with application.app_context():
        assert User.query.count() == 0
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize(
    "unsafe_target",
    (
        "https://example.com/escape",
        "//example.com/escape",
        "///example.com/escape",
        "/\\example.com/escape",
        "/safe\nLocation: https://example.com",
    ),
)
def test_google_login_rejects_external_next_targets(tmp_path, monkeypatch, unsafe_target):
    application = _google_app(tmp_path)
    client = application.test_client()
    _install_fake_google(monkeypatch, {})

    response = client.get("/login/google", query_string={"next": unsafe_target})
    assert response.status_code == 302
    with client.session_transaction() as flask_session:
        assert flask_session["google_oauth_flow"]["next"] == ""

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_teacher_claim_policy_rejects_wrong_domain_role_and_nonce():
    base = {
        "sub": "subject",
        "email": TEACHER_EMAIL,
        "email_verified": True,
        "hd": "colegiocima.edu.pe",
        "name": "Docente",
        "nonce": "expected",
    }
    kwargs = {
        "expected_nonce": "expected",
        "workspace_domain": "colegiocima.edu.pe",
        "allowed_emails": (TEACHER_EMAIL,),
    }

    wrong_domain = {**base, "hd": "gmail.com"}
    with pytest.raises(GoogleTokenError):
        validate_teacher_claims(wrong_domain, **kwargs)

    student = {**base, "email": "estudiante@colegiocima.edu.pe"}
    with pytest.raises(GoogleTokenError):
        validate_teacher_claims(student, **kwargs)

    replayed = {**base, "nonce": "replayed"}
    with pytest.raises(GoogleTokenError):
        validate_teacher_claims(replayed, **kwargs)


def test_google_token_verifier_wraps_provider_validation(monkeypatch):
    with pytest.raises(GoogleTokenError):
        verify_google_token("", "client-id", 5.0)

    expected_claims = {"sub": "stable-subject"}
    observed_timeouts = []

    def fake_request(**kwargs):
        observed_timeouts.append(kwargs["timeout"])

    monkeypatch.setattr(google_identity, "GoogleRequest", lambda: fake_request)

    def verified_token(token, transport, audience):
        transport(url="https://www.googleapis.com/oauth2/v1/certs")
        return expected_claims

    monkeypatch.setattr(
        google_identity.google_id_token,
        "verify_oauth2_token",
        verified_token,
    )
    assert verify_google_token("signed-token", "client-id", 4.5) == expected_claims
    assert observed_timeouts == [4.5]

    def rejected_token(*_args, **_kwargs):
        raise ValueError("invalid signature")

    monkeypatch.setattr(
        google_identity.google_id_token,
        "verify_oauth2_token",
        rejected_token,
    )
    with pytest.raises(GoogleTokenError):
        verify_google_token("bad-token", "client-id", 5.0)


def test_google_user_cannot_schedule_a_fictitious_classroom(tmp_path, monkeypatch):
    application = _google_app(tmp_path)
    client = application.test_client()
    nonce_holder = {}
    _install_fake_google(monkeypatch, nonce_holder)

    client.get("/login/google")
    with client.session_transaction() as flask_session:
        nonce_holder["nonce"] = flask_session["google_oauth_flow"]["nonce"]
    client.get("/login/google/callback?state=state-good&code=code")

    response = client.post(
        "/sesiones/nueva",
        data={
            "title": "No debe crearse",
            "classroom": "3.º A — Secundaria",
            "scheduled_at": "2026-09-01T10:30",
        },
    )
    assert response.status_code == 302
    with application.app_context():
        assert LearningSession.query.count() == 0
        db.session.remove()
        db.drop_all()


def test_google_mode_rejects_session_from_another_provider(tmp_path):
    application = _google_app(tmp_path)
    client = application.test_client()
    with application.app_context():
        user = User(
            email="demo-session@maxcim.demo",
            display_name="Sesión anterior",
            initials="SA",
            role="DOCENTE",
        )
        user.set_password("not-used")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as flask_session:
        flask_session["_user_id"] = str(user_id)
        flask_session["_fresh"] = True
        flask_session["auth_provider"] = "demo"

    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
    with client.session_transaction() as flask_session:
        assert "_user_id" not in flask_session

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_google_allowlist_removal_revokes_existing_session(tmp_path, monkeypatch):
    application = _google_app(tmp_path)
    client = application.test_client()
    nonce_holder = {}
    _install_fake_google(monkeypatch, nonce_holder)

    client.get("/login/google")
    with client.session_transaction() as flask_session:
        nonce_holder["nonce"] = flask_session["google_oauth_flow"]["nonce"]
    client.get("/login/google/callback?state=state-good&code=code")

    application.config["GOOGLE_ALLOWED_TEACHER_EMAILS"] = (
        "otro-docente@colegiocima.edu.pe",
    )
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
    with client.session_transaction() as flask_session:
        assert "_user_id" not in flask_session

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_google_provider_requires_exact_teacher_allowlist(tmp_path):
    with pytest.raises(RuntimeError, match="GOOGLE_ALLOWED_TEACHER_EMAILS"):
        _google_app(tmp_path, GOOGLE_ALLOWED_TEACHER_EMAILS=())

    with pytest.raises(RuntimeError, match="GOOGLE_OAUTH_TIMEOUT_SECONDS"):
        _google_app(tmp_path, GOOGLE_OAUTH_TIMEOUT_SECONDS=31)
