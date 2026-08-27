import pytest
from cryptography.fernet import Fernet

import app as app_module
from extensions import db
from services.institutional import AuthenticatedTeacher, Classroom, RecognizedStudent


TEST_TEACHER = {
    "id": "DOC-TEST-1",
    "name": "Docente de pruebas",
    "initials": "DP",
    "role": "DOCENTE",
    "access_token": "test-access-token",
}


class FakeInstitutionalClient:
    login_ready = True
    recognition_ready = True

    def authenticate(self, institutional_id, credential):
        if institutional_id != TEST_TEACHER["id"] or credential != "valid-credential":
            from services.institutional import InstitutionalAuthenticationError
            raise InstitutionalAuthenticationError()
        return AuthenticatedTeacher(
            institutional_id=TEST_TEACHER["id"],
            display_name=TEST_TEACHER["name"],
            role="DOCENTE",
            access_token="test-access-token",
            expires_in_seconds=3600,
        )

    def list_teacher_classrooms(self, access_token, teacher_id):
        assert teacher_id == TEST_TEACHER["id"]
        return [Classroom(
            institutional_id="AULA-REAL-1",
            name="Aula autorizada",
            grade="Nivel autorizado",
            course="Tutoría",
            period="Periodo activo",
        )]

    def get_recognized_student(self, person_id):
        if person_id.startswith("STAFF-"):
            return RecognizedStudent(
                institutional_id=person_id,
                display_name="Personal autorizado",
                role="DOCENTE",
                active=True,
                classroom_ids=frozenset(),
            )
        return RecognizedStudent(
            institutional_id=person_id,
            display_name="Alumno autorizado",
            role="ALUMNO",
            active=True,
            classroom_ids=frozenset({"AULA-REAL-1"}),
        )


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(app_module, "gemini_client", None)
    application = app_module.create_app({
        "TESTING": True,
        "DEMO_MODE": False,
        "TEST_TEACHER": TEST_TEACHER,
        "INSTITUTIONAL_CLIENT": FakeInstitutionalClient(),
        "SECRET_KEY": "test-secret-key",
        "SESSION_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "SESSION_COOKIE_SECURE": False,
        "MAXCIM_WEBHOOK_SECRET": "test-webhook-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "FACE_MATCH_MIN_CONFIDENCE": 0.85,
    })
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
