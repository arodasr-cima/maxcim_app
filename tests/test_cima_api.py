from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
import requests

from maxcim.services.cima_api import (
    CimaAPIClient,
    CimaConfigurationError,
    CimaContractError,
    CimaUnavailableError,
    decode_jwt_claims,
    normalize_authorization,
)


def jwt(claims: dict) -> str:
    def encoded(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encoded({'alg': 'none'})}.{encoded(claims)}.signature"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeHTTP:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client(http, **overrides):
    settings = {
        "base_url": "https://api.cima.example:8086",
        "teacher_id_claim": "idUsuario",
        "http": http,
    }
    settings.update(overrides)
    return CimaAPIClient(**settings)


def test_authenticate_email_uses_official_contract_and_keeps_single_bearer():
    expires = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    token = jwt({"idUsuario": 314, "name": "Docente Oficial", "exp": expires})
    http = FakeHTTP(
        FakeResponse({"code": 200, "content": {"token": f"Bearer {token}"}}),
        FakeResponse([{"id": 2165, "type": "N", "description": "5TH - A", "status": True}]),
    )
    client = make_client(http)

    teacher = client.authenticate_email("DOCENTE@CIMA.EDU.PE", "secreto", "192.0.2.10")
    classrooms = client.list_classrooms(teacher.authorization, teacher.teacher_id)

    login_call = http.calls[0]
    assert login_call[0] == "POST"
    assert login_call[1].endswith("/api/v2/authentication/with/email")
    assert login_call[2]["json"] == {
        "email": "docente@cima.edu.pe",
        "password": "secreto",
        "idSystem": 21,
        "identifier": "192.0.2.10",
    }
    assert http.calls[1][2]["headers"]["Authorization"] == f"Bearer {token}"
    assert teacher.teacher_id == "314"
    assert teacher.display_name == "Docente Oficial"
    assert classrooms[0].description == "5TH - A"


def test_authenticate_username_adds_bearer_only_when_missing():
    token = jwt({"idDocente": "DOC-9"})
    http = FakeHTTP(FakeResponse({"content": {"token": token}}))
    client = make_client(http, teacher_id_claim="idDocente")

    teacher = client.authenticate_username("bcesar", "clave", "MAXCIM-WEB")

    assert teacher.authorization == f"Bearer {token}"
    assert http.calls[0][1].endswith("/api/v2/authentication/with/user")
    assert http.calls[0][2]["json"]["username"] == "bcesar"


def test_list_students_minimizes_sensitive_contract_fields():
    http = FakeHTTP(
        FakeResponse(
            [
                {
                    "idPerson": 53362,
                    "firstName": "Adriano",
                    "lastName": "Amaya",
                    "institutionalEmail": "menor@cima.edu.pe",
                    "idStudentSchool": 73566673,
                    "photoRoute": "https://drive.google.com/private",
                }
            ]
        )
    )
    client = make_client(http)

    students = client.list_students("Bearer token", "2165", "N", "A")

    assert students[0].person_id == "53362"
    assert students[0].full_name == "Adriano Amaya"
    assert not hasattr(students[0], "institutional_email")
    assert not hasattr(students[0], "student_school_id")
    assert http.calls[0][1].endswith(
        "/api/v2/studentschool/list/gradesectiongroup/2165/type/N/order/A"
    )


def test_teacher_claim_is_required_when_no_explicit_semantic_claim_exists():
    claims = decode_jwt_claims(f"Bearer {jwt({'sub': 'not-safe-to-guess'})}")
    http = FakeHTTP(FakeResponse({"content": {"token": jwt(claims)}}))
    client = make_client(http, teacher_id_claim="")

    with pytest.raises(CimaConfigurationError, match="claim exacto"):
        client.authenticate_email("docente@cima.edu.pe", "clave", "device")


@pytest.mark.parametrize("value", ["", "Bearer ", "uno.dos"])
def test_invalid_tokens_are_rejected(value):
    with pytest.raises(CimaContractError):
        if value == "uno.dos":
            decode_jwt_claims(value)
        else:
            normalize_authorization(value)


def test_timeout_is_reported_without_leaking_request_data():
    http = FakeHTTP(requests.Timeout("secret request body"))
    client = make_client(http)

    with pytest.raises(CimaUnavailableError, match="tiempo de espera") as error:
        client.authenticate_email("docente@cima.edu.pe", "super-secret", "device")
    assert "super-secret" not in str(error.value)


def test_protected_requests_never_follow_redirects():
    http = FakeHTTP(FakeResponse({}, status_code=307))
    client = make_client(http)

    with pytest.raises(CimaContractError, match="redirigir"):
        client.authenticate_email("docente@cima.edu.pe", "secret", "device")
    assert http.calls[0][2]["allow_redirects"] is False


def test_client_rejects_plain_http_base_url():
    with pytest.raises(CimaConfigurationError, match="HTTPS"):
        CimaAPIClient(base_url="http://api.cima.example")
