from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from models import Material


def test_material_schema_is_compatible_with_managed_mysql():
    ddl = str(CreateTable(Material.__table__).compile(dialect=mysql.dialect()))

    assert "fecha_subido DATE NOT NULL" in ddl
    assert "DEFAULT CURRENT_DATE" not in ddl
