-- Base propia de MAXCIM App.
-- Solo contiene estructura: docentes, alumnos y aulas provienen de la API institucional.

CREATE DATABASE IF NOT EXISTS `maxcim_app`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE `maxcim_app`;

CREATE TABLE IF NOT EXISTS `material` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre_material` VARCHAR(255) NOT NULL,
  `tipo_material` VARCHAR(255) NOT NULL,
  `path_audio` VARCHAR(500) NOT NULL,
  `path_texto` VARCHAR(500) NOT NULL,
  `path_audio_resumen` VARCHAR(500) NOT NULL,
  `path_texto_resumen` VARCHAR(500) NOT NULL,
  `path_preguntas` VARCHAR(500) NOT NULL,
  `fecha_subido` DATE NOT NULL,
  -- ID institucional de la docente. No es una FK real: la tabla `docente`
  -- vive en la API institucional, no en esta base.
  `fk_user` VARCHAR(50) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_material_docente` (`fk_user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Una interacción = un turno de pregunta/respuesta entre un alumno y MAXCIM
-- sobre un material puntual.
CREATE TABLE IF NOT EXISTS `interaccion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_material` INT NOT NULL,
  -- ID institucional del alumno, igual que `fk_user` en `material`: no es una
  -- FK real porque la tabla `alumno` también vive en la API institucional.
  `fk_alumno` VARCHAR(50) NOT NULL,
  `fecha_hora` DATETIME NOT NULL,
  `pregunta` TEXT NOT NULL,
  `respuesta` TEXT NOT NULL,
  `path_audio_rpta` VARCHAR(500) NOT NULL,
  `apreciacion_robot` TEXT NOT NULL COMMENT 'Campo en el cual el robot dirá su "crítica" sobre la respuesta del alumno.',
  `rpta_correcta` BOOLEAN NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_interaccion_alumno` (`fk_alumno`),
  INDEX `ix_interaccion_material` (`id_material`),
  CONSTRAINT `interaccion_id_material_foreign` FOREIGN KEY (`id_material`) REFERENCES `material` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
