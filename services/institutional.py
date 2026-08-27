from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests


class InstitutionalAPIError(RuntimeError):
    """Base error for institutional identity and enrollment lookups."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class InstitutionalConfigurationError(InstitutionalAPIError):
    def __init__(self, message: str = "La API institucional no está configurada."):
        super().__init__(message, 503)


class InstitutionalAuthenticationError(InstitutionalAPIError):
    def __init__(self, message: str = "El ID o la credencial institucional no son válidos."):
        super().__init__(message, 401)


@dataclass(frozen=True)
class AuthenticatedTeacher:
    institutional_id: str
    display_name: str
    role: str
    access_token: str
    expires_in_seconds: int

    @property
    def initials(self) -> str:
        parts = [part for part in self.display_name.split() if part]
        return "".join(part[0].upper() for part in parts[:2]) or "DC"


@dataclass(frozen=True)
class Classroom:
    institutional_id: str
    name: str
    grade: str | None
    course: str | None
    period: str | None


@dataclass(frozen=True)
class ClassroomStudent:
    institutional_id: str
    apellidos: str
    nombres: str

    @property
    def full_name(self) -> str:
        return f"{self.apellidos.upper()}, {self.nombres.title()}"


@dataclass(frozen=True)
class RecognizedStudent:
    institutional_id: str
    display_name: str
    role: str
    active: bool
    classroom_ids: frozenset[str]


class InstitutionalClient:
    """Strict HTTP adapter for CIMA's source-of-truth API.

    The adapter intentionally fails when a required field is absent. It never
    fabricates teachers, classrooms, enrollments, or student identities.
    """

    def __init__(
        self,
        *,
        base_url: str,
        login_path: str,
        google_login_path: str,
        classrooms_path: str,
        student_path: str,
        service_token: str,
        students_path: str = "",
        timeout_seconds: float = 8.0,
        verify_tls: bool = True,
    ):
        self.base_url = base_url.rstrip("/") + "/" if base_url else ""
        self.login_path = login_path
        self.google_login_path = google_login_path
        self.classrooms_path = classrooms_path
        self.students_path = students_path
        self.student_path = student_path
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds
        self.verify_tls = verify_tls
        self.http = requests.Session()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "InstitutionalClient":
        return cls(
            base_url=str(config.get("INSTITUTIONAL_API_BASE_URL") or "").strip(),
            login_path=str(config.get("INSTITUTIONAL_API_LOGIN_PATH") or "").strip(),
            google_login_path=str(
                config.get("INSTITUTIONAL_API_GOOGLE_LOGIN_PATH") or ""
            ).strip(),
            classrooms_path=str(config.get("INSTITUTIONAL_API_CLASSROOMS_PATH") or "").strip(),
            students_path=str(config.get("INSTITUTIONAL_API_STUDENTS_PATH") or "").strip(),
            student_path=str(config.get("INSTITUTIONAL_API_STUDENT_PATH") or "").strip(),
            service_token=str(config.get("INSTITUTIONAL_API_SERVICE_TOKEN") or "").strip(),
            timeout_seconds=float(config.get("INSTITUTIONAL_API_TIMEOUT_SECONDS") or 8),
            verify_tls=bool(config.get("INSTITUTIONAL_API_VERIFY_TLS", True)),
        )

    @property
    def login_ready(self) -> bool:
        return bool(self.base_url and self.login_path and self.classrooms_path)

    @property
    def recognition_ready(self) -> bool:
        return bool(self.base_url and self.student_path and self.service_token)

    @property
    def students_ready(self) -> bool:
        return bool(self.base_url and self.students_path)

    @property
    def google_login_ready(self) -> bool:
        return bool(self.base_url and self.google_login_path)

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise InstitutionalConfigurationError()
        return urljoin(self.base_url, path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.http.request(
                method,
                self._url(path),
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
                verify=self.verify_tls,
            )
        except requests.RequestException as exc:
            raise InstitutionalAPIError("No se pudo contactar la API institucional.", 503) from exc

        if response.status_code in {401, 403}:
            raise InstitutionalAuthenticationError()
        if response.status_code == 404:
            raise InstitutionalAPIError("El registro institucional solicitado no existe.", 404)
        if response.status_code >= 400:
            raise InstitutionalAPIError(
                f"La API institucional respondió con estado {response.status_code}.",
                502,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise InstitutionalAPIError("La API institucional devolvió una respuesta no válida.") from exc

    @staticmethod
    def _required_text(record: dict[str, Any], field: str) -> str:
        value = str(record.get(field) or "").strip()
        if not value:
            raise InstitutionalAPIError(
                f"La respuesta institucional no contiene el campo obligatorio '{field}'."
            )
        return value

    def _parse_authenticated_teacher(self, payload: Any) -> AuthenticatedTeacher:
        if not isinstance(payload, dict) or not isinstance(payload.get("teacher"), dict):
            raise InstitutionalAPIError("La respuesta de inicio de sesión no cumple el contrato MAXCIM.")

        teacher = payload["teacher"]
        access_token = self._required_text(payload, "access_token")
        teacher_id = self._required_text(teacher, "id")
        display_name = self._required_text(teacher, "display_name")
        role = self._required_text(teacher, "role").upper()
        status = self._required_text(teacher, "status").upper()

        if role not in {"DOCENTE", "TEACHER"}:
            raise InstitutionalAuthenticationError("La cuenta institucional no pertenece a una docente.")
        if status not in {"ACTIVO", "ACTIVE"}:
            raise InstitutionalAuthenticationError("La cuenta institucional no está activa.")

        try:
            expires_in = max(300, int(payload.get("expires_in", 3600)))
        except (TypeError, ValueError) as exc:
            raise InstitutionalAPIError("La expiración del token institucional no es válida.") from exc

        return AuthenticatedTeacher(
            institutional_id=teacher_id,
            display_name=display_name,
            role="DOCENTE",
            access_token=access_token,
            expires_in_seconds=expires_in,
        )

    def authenticate(self, institutional_id: str, credential: str) -> AuthenticatedTeacher:
        if not self.login_ready:
            raise InstitutionalConfigurationError()
        payload = self._request(
            "POST",
            self.login_path,
            payload={"institutional_id": institutional_id, "credential": credential},
        )
        return self._parse_authenticated_teacher(payload)

    def authenticate_google(self, verified_id_token: str) -> AuthenticatedTeacher:
        """Exchange a verified Google ID token for the institutional session.

        The institutional API must validate the token again and map its stable
        Google subject/email to an active teacher record. MAXCIM never creates a
        teacher solely from Google profile claims.
        """

        if not self.google_login_ready:
            raise InstitutionalConfigurationError(
                "La validación institucional del acceso con Google no está configurada."
            )
        payload = self._request(
            "POST",
            self.google_login_path,
            payload={"id_token": verified_id_token},
        )
        return self._parse_authenticated_teacher(payload)

    def list_teacher_classrooms(self, access_token: str, teacher_id: str) -> list[Classroom]:
        if not self.login_ready:
            raise InstitutionalConfigurationError()
        path = self.classrooms_path.format(teacher_id=teacher_id)
        payload = self._request("GET", path, token=access_token)
        records = payload.get("classrooms") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise InstitutionalAPIError("La API institucional no devolvió la lista de aulas esperada.")

        classrooms: list[Classroom] = []
        for record in records:
            if not isinstance(record, dict):
                raise InstitutionalAPIError("La API institucional devolvió un aula no válida.")
            classrooms.append(Classroom(
                institutional_id=self._required_text(record, "id"),
                name=self._required_text(record, "name"),
                grade=str(record.get("grade") or "").strip() or None,
                course=str(record.get("course") or "").strip() or None,
                period=str(record.get("period") or "").strip() or None,
            ))
        return classrooms

    @classmethod
    def _map_classroom_student(cls, record: dict[str, Any]) -> ClassroomStudent:
        """Mapea temporalmente las variantes previstas del contrato de alumnos.

        Los nombres reales de los campos aún deben ser confirmados por el
        cliente. Todas las variantes están centralizadas aquí para que ese
        ajuste futuro se haga en un solo lugar.
        """

        def first_text(*fields: str) -> str:
            for field in fields:
                value = record.get(field)
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    normalized = str(value).strip()
                    if normalized:
                        return normalized
            return ""

        institutional_id = first_text(
            "id", "institutional_id", "student_id", "id_alumno", "alumno_id"
        )
        apellidos = first_text("apellidos", "last_name", "last_names", "surname", "surnames")
        nombres = first_text("nombres", "first_name", "given_name", "given_names", "nombre")

        if not apellidos:
            apellido_paterno = first_text("apellido_paterno", "paternal_surname")
            apellido_materno = first_text("apellido_materno", "maternal_surname")
            apellidos = " ".join(
                part for part in (apellido_paterno, apellido_materno) if part
            )

        if not apellidos or not nombres:
            combined_name = first_text("full_name", "display_name", "nombre_completo", "name")
            if "," in combined_name:
                combined_apellidos, combined_nombres = (
                    part.strip() for part in combined_name.split(",", 1)
                )
            else:
                parts = combined_name.split()
                surname_count = 2 if len(parts) >= 3 else 1
                combined_nombres = " ".join(parts[:-surname_count])
                combined_apellidos = " ".join(parts[-surname_count:])
            apellidos = apellidos or combined_apellidos
            nombres = nombres or combined_nombres

        missing_fields = [
            field
            for field, value in (
                ("id", institutional_id),
                ("apellidos", apellidos),
                ("nombres", nombres),
            )
            if not value
        ]
        if missing_fields:
            raise InstitutionalAPIError(
                "La respuesta institucional del alumno no contiene datos válidos para: "
                + ", ".join(missing_fields)
                + "."
            )

        return ClassroomStudent(
            institutional_id=institutional_id,
            apellidos=apellidos,
            nombres=nombres,
        )

    def list_classroom_students(
        self, access_token: str, classroom_id: str
    ) -> list[ClassroomStudent]:
        if not self.students_ready:
            raise InstitutionalConfigurationError(
                "La consulta institucional de alumnos por aula no está configurada."
            )
        path = self.students_path.format(classroom_id=classroom_id)
        payload = self._request("GET", path, token=access_token)
        # La clave del sobre tampoco está confirmada por el cliente, igual que
        # los campos de cada alumno en `_map_classroom_student`. Se aceptan las
        # variantes previstas y la lista desnuda.
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = next(
                (
                    payload[key]
                    for key in ("students", "alumnos", "data", "items")
                    if isinstance(payload.get(key), list)
                ),
                None,
            )
        else:
            records = None
        if not isinstance(records, list):
            raise InstitutionalAPIError(
                "La API institucional no devolvió la lista de alumnos esperada."
            )

        students: list[ClassroomStudent] = []
        for record in records:
            if not isinstance(record, dict):
                raise InstitutionalAPIError(
                    "La API institucional devolvió un alumno no válido."
                )
            students.append(self._map_classroom_student(record))
        return students

    def get_recognized_student(self, person_id: str) -> RecognizedStudent:
        if not self.recognition_ready:
            raise InstitutionalConfigurationError(
                "La validación institucional del reconocimiento facial no está configurada."
            )
        path = self.student_path.format(person_id=person_id)
        payload = self._request("GET", path, token=self.service_token)
        student = payload.get("student") if isinstance(payload, dict) else None
        if not isinstance(student, dict):
            raise InstitutionalAPIError("La API institucional no devolvió el perfil del alumno esperado.")

        classroom_ids = student.get("classroom_ids")
        if not isinstance(classroom_ids, list):
            raise InstitutionalAPIError("La API institucional no confirmó las matrículas activas del alumno.")

        role = self._required_text(student, "role").upper()
        status = self._required_text(student, "status").upper()
        return RecognizedStudent(
            institutional_id=self._required_text(student, "id"),
            display_name=self._required_text(student, "display_name"),
            role=role,
            active=status in {"ACTIVO", "ACTIVE"},
            classroom_ids=frozenset(str(item).strip() for item in classroom_ids if str(item).strip()),
        )
