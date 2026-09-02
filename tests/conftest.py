import tempfile

import pytest
from cryptography.fernet import Fernet

import app as app_module
from extensions import db
from services.institutional import AuthenticatedTeacher, Classroom, ClassroomStudent


TEST_TEACHER = {
    "id": "DOC-TEST-1",
    "name": "Docente de pruebas",
    "initials": "DP",
    "role": "DOCENTE",
    "access_token": "test-access-token",
}


class FakeInstitutionalClient:
    login_ready = True

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

    def list_classroom_students(self, access_token, classroom_id, section_type=None):
        assert classroom_id == "AULA-REAL-1"
        return [
            ClassroomStudent("ALU-TEST-1", "Pérez Flores", "Ana Lucía"),
            ClassroomStudent("ALU-TEST-2", "Quispe Rojas", "Mateo"),
        ]


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
        "UPLOADS_ROOT": tempfile.mkdtemp(prefix="maxcim-uploads-"),
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


@pytest.fixture()
def urls(app):
    """Construye las URLs de la consola con los identificadores opacos
    (aula/alumno firmados) que ahora esperan las rutas."""
    def _ref(name, *ids):
        with app.test_request_context():
            return app.jinja_env.globals[name](*ids)

    class _URLs:
        def classroom(self, classroom_id):
            return f"/aulas/{_ref('classroom_ref', classroom_id)}"

        def progress(self, classroom_id):
            return f"/aulas/{_ref('classroom_ref', classroom_id)}/avance"

        def student(self, classroom_id, student_id):
            return f"/aulas/alumno/{_ref('student_ref', classroom_id, student_id)}"

    return _URLs()
