"""Strict adapter for the official CIMA School teacher API."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import requests


class CimaAPIError(RuntimeError):
    """Base error for safe, user-facing CIMA integration failures."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class CimaConfigurationError(CimaAPIError):
    def __init__(self, message: str = "La conexión institucional no está configurada."):
        super().__init__(message, 503)


class CimaAuthenticationError(CimaAPIError):
    def __init__(self, message: str = "Las credenciales institucionales no son válidas."):
        super().__init__(message, 401)


class CimaUnavailableError(CimaAPIError):
    def __init__(self, message: str = "El servicio institucional no está disponible."):
        super().__init__(message, 503)


class CimaContractError(CimaAPIError):
    def __init__(self, message: str = "La respuesta institucional no cumple el contrato esperado."):
        super().__init__(message, 502)


@dataclass(frozen=True)
class AuthenticatedTeacher:
    teacher_id: str
    authorization: str
    display_name: str | None
    expires_at: datetime | None


@dataclass(frozen=True)
class Classroom:
    institutional_id: str
    classroom_type: str
    description: str
    status: bool

    @property
    def type_label(self) -> str:
        return "Curso regular" if self.classroom_type == "N" else "Grupo de inglés"


@dataclass(frozen=True)
class Student:
    person_id: str
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part).strip()

    @property
    def initials(self) -> str:
        parts = [part for part in self.full_name.split() if part]
        return "".join(part[0].upper() for part in parts[:2]) or "AL"


def normalize_authorization(token: str) -> str:
    """Return exactly one Bearer prefix, including when CIMA already sent it."""

    normalized = str(token or "").strip()
    if not normalized:
        raise CimaContractError("La respuesta institucional no contiene un token de acceso.")
    if normalized.lower() == "bearer":
        raise CimaContractError("La respuesta institucional contiene un token vacío.")
    if normalized.lower().startswith("bearer "):
        scheme, value = normalized.split(None, 1)
        if not value.strip():
            raise CimaContractError("La respuesta institucional contiene un token vacío.")
        return f"{scheme.title()} {value.strip()}"
    return f"Bearer {normalized}"


def decode_jwt_claims(authorization: str) -> dict[str, Any]:
    """Decode JWT claims without treating them as a local authorization proof."""

    token = normalize_authorization(authorization).split(None, 1)[1]
    parts = token.split(".")
    if len(parts) != 3:
        raise CimaContractError("El token institucional no tiene formato JWT.")
    try:
        padding = "=" * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(parts[1] + padding)
        claims = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CimaContractError("No se pudo interpretar el token institucional.") from exc
    if not isinstance(claims, dict):
        raise CimaContractError("El token institucional no contiene claims válidos.")
    return claims


def _claim_value(claims: dict[str, Any], claim_path: str) -> Any:
    value: Any = claims
    for part in claim_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def extract_teacher_id(claims: dict[str, Any], configured_claim: str = "") -> str:
    """Extract the documented teacher/user ID and fail closed if it is ambiguous."""

    if configured_claim:
        value = _claim_value(claims, configured_claim)
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
            raise CimaConfigurationError(
                f"El claim configurado '{configured_claim}' no contiene el identificador docente."
            )
        return str(value).strip()

    candidates = ("idDocente", "idUsuario", "idUser", "teacherId", "teacher_id")
    found = {
        str(value).strip()
        for claim in candidates
        if (value := _claim_value(claims, claim)) is not None
        and not isinstance(value, bool)
        and isinstance(value, (str, int))
        and str(value).strip()
    }
    if len(found) == 1:
        return found.pop()
    raise CimaConfigurationError(
        "Configura CIMA_API_TEACHER_ID_CLAIM con el claim exacto del identificador docente."
    )


def _display_name(claims: dict[str, Any]) -> str | None:
    for claim in ("name", "displayName", "fullName", "nombreCompleto"):
        value = _claim_value(claims, claim)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return None


def _expiration(claims: dict[str, Any]) -> datetime | None:
    value = claims.get("exp")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


class CimaAPIClient:
    """HTTP client for the four endpoints documented by CIMA School."""

    def __init__(
        self,
        *,
        base_url: str,
        system_id: int = 21,
        user_login_path: str = "/api/v2/authentication/with/user",
        email_login_path: str = "/api/v2/authentication/with/email",
        classrooms_path: str = "/api/v2/gradesection/list/group/user/{teacher_id}",
        students_path: str = (
            "/api/v2/studentschool/list/gradesectiongroup/{classroom_id}"
            "/type/{classroom_type}/order/{order}"
        ),
        teacher_id_claim: str = "",
        timeout_seconds: float = 8.0,
        verify_tls: bool = True,
        http: requests.Session | None = None,
    ):
        if not str(base_url or "").strip():
            raise CimaConfigurationError("Falta CIMA_API_BASE_URL.")
        self.base_url = str(base_url).rstrip("/") + "/"
        parsed_base_url = urlsplit(self.base_url)
        if parsed_base_url.scheme != "https" or not parsed_base_url.hostname:
            raise CimaConfigurationError("CIMA_API_BASE_URL debe usar HTTPS.")
        self.system_id = int(system_id)
        if self.system_id <= 0:
            raise CimaConfigurationError("CIMA_API_SYSTEM_ID debe ser mayor que cero.")
        self.user_login_path = user_login_path
        self.email_login_path = email_login_path
        self.classrooms_path = classrooms_path
        self.students_path = students_path
        self.teacher_id_claim = teacher_id_claim.strip()
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise CimaConfigurationError("CIMA_API_TIMEOUT_SECONDS debe ser mayor que cero.")
        self.verify_tls = bool(verify_tls)
        self.http = http or requests.Session()
        if "{teacher_id}" not in self.classrooms_path:
            raise CimaConfigurationError("La ruta de aulas debe contener {teacher_id}.")
        required_students_fields = ("{classroom_id}", "{classroom_type}", "{order}")
        if not all(field in self.students_path for field in required_students_fields):
            raise CimaConfigurationError("La ruta de alumnos no contiene todos sus parámetros.")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> CimaAPIClient:
        return cls(
            base_url=str(config.get("CIMA_API_BASE_URL") or ""),
            system_id=int(config.get("CIMA_API_SYSTEM_ID") or 21),
            user_login_path=str(config.get("CIMA_API_USER_LOGIN_PATH") or ""),
            email_login_path=str(config.get("CIMA_API_EMAIL_LOGIN_PATH") or ""),
            classrooms_path=str(config.get("CIMA_API_CLASSROOMS_PATH") or ""),
            students_path=str(config.get("CIMA_API_STUDENTS_PATH") or ""),
            teacher_id_claim=str(config.get("CIMA_API_TEACHER_ID_CLAIM") or ""),
            timeout_seconds=float(config.get("CIMA_API_TIMEOUT_SECONDS") or 8),
            verify_tls=bool(config.get("CIMA_API_VERIFY_TLS", True)),
        )

    def _url(self, path: str) -> str:
        if not path:
            raise CimaConfigurationError("Falta configurar una ruta de la API CIMA.")
        return urljoin(self.base_url, path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        *,
        authorization: str | None = None,
        payload: dict[str, Any] | None = None,
        authenticating: bool = False,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if authorization:
            headers["Authorization"] = normalize_authorization(authorization)
        try:
            response = self.http.request(
                method,
                self._url(path),
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
                verify=self.verify_tls,
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise CimaUnavailableError("La API CIMA superó el tiempo de espera.") from exc
        except requests.RequestException as exc:
            raise CimaUnavailableError("No se pudo contactar la API CIMA.") from exc

        if response.status_code in {401, 403} or (authenticating and response.status_code == 400):
            raise CimaAuthenticationError()
        if 300 <= response.status_code < 400:
            raise CimaContractError("La API CIMA intentó redirigir una solicitud protegida.")
        if response.status_code >= 500:
            raise CimaUnavailableError()
        if response.status_code >= 400:
            raise CimaAPIError(f"La API CIMA respondió con estado {response.status_code}.", 502)
        try:
            return response.json()
        except ValueError as exc:
            raise CimaContractError("La API CIMA devolvió una respuesta que no es JSON.") from exc

    def _authenticate(self, field: str, value: str, password: str, identifier: str) -> AuthenticatedTeacher:
        login_value = str(value or "").strip()
        if not login_value or not password:
            raise CimaAuthenticationError()
        device_identifier = str(identifier or "").strip()
        if not device_identifier:
            raise CimaConfigurationError("Falta el identificador requerido por la API CIMA.")
        path = self.email_login_path if field == "email" else self.user_login_path
        payload = self._request(
            "POST",
            path,
            payload={
                field: login_value,
                "password": password,
                "idSystem": self.system_id,
                "identifier": device_identifier,
            },
            authenticating=True,
        )
        if not isinstance(payload, dict):
            raise CimaContractError()
        code = payload.get("code", 200)
        if code not in {200, "200"}:
            if code in {400, 401, 403, "400", "401", "403"}:
                raise CimaAuthenticationError()
            raise CimaContractError("La API CIMA rechazó el contrato de autenticación.")
        content = payload.get("content")
        if not isinstance(content, dict):
            raise CimaContractError()
        authorization = normalize_authorization(content.get("token", ""))
        claims = decode_jwt_claims(authorization)
        return AuthenticatedTeacher(
            teacher_id=extract_teacher_id(claims, self.teacher_id_claim),
            authorization=authorization,
            display_name=_display_name(claims),
            expires_at=_expiration(claims),
        )

    def authenticate_email(self, email: str, password: str, identifier: str) -> AuthenticatedTeacher:
        return self._authenticate("email", email.lower(), password, identifier)

    def authenticate_username(self, username: str, password: str, identifier: str) -> AuthenticatedTeacher:
        return self._authenticate("username", username, password, identifier)

    @staticmethod
    def _records(payload: Any, label: str) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("content", "data", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise CimaContractError(f"La API CIMA no devolvió la lista de {label} esperada.")

    @staticmethod
    def _required_scalar(record: dict[str, Any], field: str) -> str:
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
            raise CimaContractError(f"La respuesta CIMA no contiene el campo válido '{field}'.")
        return str(value).strip()

    def list_classrooms(self, authorization: str, teacher_id: str) -> list[Classroom]:
        path = self.classrooms_path.format(teacher_id=quote(str(teacher_id), safe=""))
        records = self._records(self._request("GET", path, authorization=authorization), "aulas")
        classrooms: list[Classroom] = []
        for record in records:
            if not isinstance(record, dict):
                raise CimaContractError("La API CIMA devolvió un aula no válida.")
            classroom_type = self._required_scalar(record, "type").upper()
            if classroom_type not in {"N", "G"}:
                raise CimaContractError("La API CIMA devolvió un tipo de aula no permitido.")
            status = record.get("status")
            if not isinstance(status, bool):
                raise CimaContractError("La API CIMA devolvió un estado de aula no válido.")
            classrooms.append(
                Classroom(
                    institutional_id=self._required_scalar(record, "id"),
                    classroom_type=classroom_type,
                    description=self._required_scalar(record, "description")[:180],
                    status=status,
                )
            )
        return classrooms

    def list_students(
        self,
        authorization: str,
        classroom_id: str,
        classroom_type: str,
        order: str = "A",
    ) -> list[Student]:
        normalized_type = str(classroom_type).upper()
        normalized_order = str(order).upper()
        if normalized_type not in {"N", "G"} or normalized_order not in {"A", "N"}:
            raise CimaContractError("El tipo o el orden solicitado no es válido.")
        path = self.students_path.format(
            classroom_id=quote(str(classroom_id), safe=""),
            classroom_type=normalized_type,
            order=normalized_order,
        )
        records = self._records(self._request("GET", path, authorization=authorization), "alumnos")
        students: list[Student] = []
        for record in records:
            if not isinstance(record, dict):
                raise CimaContractError("La API CIMA devolvió un alumno no válido.")
            first_name = str(record.get("firstName") or "").strip()
            last_name = str(record.get("lastName") or "").strip()
            if not first_name and not last_name:
                raise CimaContractError("La respuesta CIMA no contiene el nombre del alumno.")
            students.append(
                Student(
                    person_id=self._required_scalar(record, "idPerson"),
                    first_name=first_name[:120],
                    last_name=last_name[:120],
                )
            )
        return students


def get_cima_client(config: dict[str, Any]) -> CimaAPIClient:
    injected = config.get("CIMA_API_CLIENT")
    if injected is not None:
        return injected
    cached = config.get("_CIMA_API_CLIENT")
    if cached is None:
        cached = CimaAPIClient.from_config(config)
        config["_CIMA_API_CLIENT"] = cached
    return cached
