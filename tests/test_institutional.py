import pytest

from services.institutional import InstitutionalAPIError, InstitutionalClient


def make_client(**overrides):
    settings = {
        "base_url": "https://api.cima.example",
        "login_path": "/v1/auth/login",
        "google_login_path": "/v1/auth/google",
        "classrooms_path": "/v1/teachers/{teacher_id}/classrooms",
        "students_path": "/v1/classrooms/{classroom_id}/students",
        "student_path": "/v1/students/{person_id}",
        "service_token": "service-token",
    }
    settings.update(overrides)
    return InstitutionalClient(**settings)


def test_list_classroom_students_maps_supported_name_spellings(monkeypatch):
    client = make_client()
    captured = {}

    def fake_request(method, path, *, token=None, payload=None):
        captured.update(method=method, path=path, token=token, payload=payload)
        return {
            "students": [
                {"id": "ALU-1", "apellidos": "Pérez Rojas", "nombres": "Ana Lucía"},
                {
                    "institutional_id": "ALU-2",
                    "last_name": "Smith",
                    "first_name": "Jordan",
                },
                {
                    "student_id": "ALU-3",
                    "apellido_paterno": "Quispe",
                    "apellido_materno": "Flores",
                    "given_name": "Mateo",
                },
                {"id_alumno": "ALU-4", "full_name": "Soto Díaz, Elena María"},
            ]
        }

    monkeypatch.setattr(client, "_request", fake_request)

    students = client.list_classroom_students("teacher-token", "AULA-5B")

    assert captured == {
        "method": "GET",
        "path": "/v1/classrooms/AULA-5B/students",
        "token": "teacher-token",
        "payload": None,
    }
    assert [student.institutional_id for student in students] == [
        "ALU-1",
        "ALU-2",
        "ALU-3",
        "ALU-4",
    ]
    assert [student.full_name for student in students] == [
        "PÉREZ ROJAS, Ana Lucía",
        "SMITH, Jordan",
        "QUISPE FLORES, Mateo",
        "SOTO DÍAZ, Elena María",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"students": "no-es-una-lista"},
        {"students": [{"id": "ALU-SIN-NOMBRE"}]},
        {"students": ["no-es-un-registro"]},
    ],
)
def test_list_classroom_students_rejects_malformed_payload(monkeypatch, payload):
    client = make_client()
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: payload)

    with pytest.raises(InstitutionalAPIError):
        client.list_classroom_students("teacher-token", "AULA-1A")


def test_students_path_is_loaded_from_config_and_exposes_readiness():
    client = InstitutionalClient.from_config(
        {
            "INSTITUTIONAL_API_BASE_URL": "https://api.cima.example",
            "INSTITUTIONAL_API_STUDENTS_PATH": "/v1/aulas/{classroom_id}/alumnos",
        }
    )

    assert client.students_path == "/v1/aulas/{classroom_id}/alumnos"
    assert client.students_ready is True
