-- Base propia de MAXCIM App.
-- Solo contiene estructura: docentes, alumnos y aulas provienen de la API institucional.

CREATE DATABASE IF NOT EXISTS `maxcim_app`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE `maxcim_app`;

CREATE TABLE IF NOT EXISTS `material` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre_material` VARCHAR(255) NOT NULL,
  `path_audio` VARCHAR(500) NOT NULL,
  `path_texto` VARCHAR(500) NOT NULL,
  `path_audio_resumen` VARCHAR(500) NOT NULL,
  `path_texto_resumen` VARCHAR(500) NOT NULL,
  `fecha_subido` DATE NOT NULL,
  `fk_user` VARCHAR(50) NOT NULL,
  `path_preguntas` VARCHAR(500) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_material_docente` (`fk_user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
