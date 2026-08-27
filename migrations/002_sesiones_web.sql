-- Sesiones opacas para docentes autenticadas por la API institucional.
-- El token se almacena cifrado; la cookie del navegador contiene solo el UUID.

CREATE TABLE IF NOT EXISTS `sesion_web_docente` (
  `id` VARCHAR(36) NOT NULL,
  `id_docente_institucional` VARCHAR(50) NOT NULL,
  `nombre_docente` VARCHAR(255) NOT NULL,
  `rol` VARCHAR(30) NOT NULL,
  `token_cifrado` LONGBLOB NOT NULL,
  `expira_en` DATETIME NOT NULL,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ultimo_acceso_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `revocada_en` DATETIME NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_sesion_web_docente` (`id_docente_institucional`),
  INDEX `ix_sesion_web_expira` (`expira_en`),
  INDEX `ix_sesion_web_revocada` (`revocada_en`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
