-- Esquema MySQL 8 vigente de MAXCIM App.
-- Generado a partir de bd_app.sql: solo contiene las tablas que el código
-- actual usa (material, interaccion). Las tablas de migrations/001 y
-- migrations/002 (pregunta, sesion_interaccion, turno_conversacion,
-- evaluacion_interaccion, evento_reconocimiento, sesion_web_docente)
-- quedaron obsoletas tras el refactor a este esquema de dos tablas y no se
-- incluyen aquí. Docentes, aulas y alumnos provienen de la API institucional
-- y nunca se persisten localmente.

CREATE DATABASE IF NOT EXISTS `maxcim_app`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE `maxcim_app`;

CREATE TABLE IF NOT EXISTS `material` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre_material` VARCHAR(255) NOT NULL,
  -- Valores permitidos: 'cuento' y 'oracion'.
  `tipo_material` VARCHAR(255) NOT NULL,
  `path_audio` VARCHAR(500) NULL,
  `path_texto` VARCHAR(500) NULL,
  `path_audio_resumen` VARCHAR(500) NULL,
  `path_texto_resumen` VARCHAR(500) NULL,
  -- Para un cuento guarda la ruta del JSON de preguntas; para una oración
  -- guarda el texto de las oraciones. Por eso es TEXT y no VARCHAR(500).
  `path_preguntas` TEXT NOT NULL,
  `fecha_subido` DATE NOT NULL,
  -- ID institucional de la docente (`idPersona` de CIMA). No es una FK real: la
  -- tabla `docente` vive en la API institucional, no en esta base.
  `fk_user` VARCHAR(50) NOT NULL,
  -- Nombre de la docente al crear el material; copia para que el robot lo
  -- muestre sin volver a consultar a CIMA. NULL en registros antiguos.
  `fk_user_name` VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  INDEX `ix_material_docente` (`fk_user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Una interacción = un turno de pregunta/respuesta entre un alumno y MAXCIM.
-- Normalmente es sobre un material puntual; cuando `id_material` es NULL el
-- turno es una conversación libre del alumno con MAXCIM, sin material asociado
-- (las vistas de la docente lo rotulan "Conversación").
CREATE TABLE IF NOT EXISTS `interaccion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_material` INT NULL,
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
