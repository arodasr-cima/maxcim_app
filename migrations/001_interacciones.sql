-- MAXCIM App: preguntas revisables, sesiones orales y evaluación docente.
-- Aplicar después de bd_app.sql sobre la misma base MySQL 8.

CREATE TABLE IF NOT EXISTS `pregunta` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_material` INT NOT NULL,
  `tipo` VARCHAR(30) NOT NULL,
  `enunciado` TEXT NOT NULL,
  `respuesta_esperada` TEXT NULL,
  `orden` INT NOT NULL DEFAULT 0,
  `generada_por_ia` BOOLEAN NOT NULL DEFAULT TRUE,
  `editada_por_docente` BOOLEAN NOT NULL DEFAULT FALSE,
  `estado` VARCHAR(30) NOT NULL DEFAULT 'pendiente_revision',
  `aprobada_por` VARCHAR(50) NULL,
  `aprobada_en` DATETIME NULL,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_pregunta_material` (`id_material`),
  INDEX `ix_pregunta_estado` (`estado`),
  CONSTRAINT `fk_pregunta_material`
    FOREIGN KEY (`id_material`) REFERENCES `material` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `sesion_interaccion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `uuid` VARCHAR(36) NOT NULL,
  `id_docente_institucional` VARCHAR(50) NOT NULL,
  `id_alumno_institucional` VARCHAR(50) NULL,
  `id_aula_institucional` VARCHAR(50) NOT NULL,
  `id_material` INT NULL,
  `objetivo` TEXT NULL,
  `estado` VARCHAR(30) NOT NULL DEFAULT 'esperando_identificacion',
  `alumno_nombre` VARCHAR(255) NULL,
  `confianza_reconocimiento` DECIMAL(5,4) NULL,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `iniciada_en` DATETIME NULL,
  `finalizada_en` DATETIME NULL,
  `revisada_por_docente` BOOLEAN NOT NULL DEFAULT FALSE,
  `observaciones_docente` TEXT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sesion_uuid` (`uuid`),
  INDEX `ix_sesion_docente` (`id_docente_institucional`),
  INDEX `ix_sesion_alumno` (`id_alumno_institucional`),
  INDEX `ix_sesion_aula` (`id_aula_institucional`),
  INDEX `ix_sesion_material` (`id_material`),
  INDEX `ix_sesion_estado` (`estado`),
  CONSTRAINT `fk_sesion_material`
    FOREIGN KEY (`id_material`) REFERENCES `material` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `turno_conversacion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_sesion` INT NOT NULL,
  `id_pregunta` INT NULL,
  `orden` INT NOT NULL,
  `emisor` VARCHAR(20) NOT NULL,
  `texto_transcrito` TEXT NOT NULL,
  `path_audio` VARCHAR(500) NULL,
  `tiempo_respuesta_ms` INT NULL,
  `respuesta_correcta` BOOLEAN NULL,
  `necesito_ayuda` BOOLEAN NOT NULL DEFAULT FALSE,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_turno_orden` (`id_sesion`, `orden`),
  INDEX `ix_turno_pregunta` (`id_pregunta`),
  CONSTRAINT `fk_turno_sesion`
    FOREIGN KEY (`id_sesion`) REFERENCES `sesion_interaccion` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_turno_pregunta`
    FOREIGN KEY (`id_pregunta`) REFERENCES `pregunta` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `evaluacion_interaccion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_sesion` INT NOT NULL,
  `preguntas_realizadas` INT NOT NULL DEFAULT 0,
  `respuestas_registradas` INT NOT NULL DEFAULT 0,
  `respuestas_correctas` INT NOT NULL DEFAULT 0,
  `promedio_respuesta_ms` INT NULL,
  `porcentaje_participacion` DECIMAL(5,2) NOT NULL DEFAULT 0,
  `porcentaje_comprension` DECIMAL(5,2) NOT NULL DEFAULT 0,
  `porcentaje_interaccion_oral` DECIMAL(5,2) NULL,
  `porcentaje_general` DECIMAL(5,2) NULL,
  `criterios_json` TEXT NULL,
  `resumen_ia` TEXT NULL,
  `estado` VARCHAR(30) NOT NULL DEFAULT 'pendiente_revision',
  `retroalimentacion_docente` TEXT NULL,
  `revisada_por` VARCHAR(50) NULL,
  `revisada_en` DATETIME NULL,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_evaluacion_sesion` (`id_sesion`),
  INDEX `ix_evaluacion_estado` (`estado`),
  CONSTRAINT `fk_evaluacion_sesion`
    FOREIGN KEY (`id_sesion`) REFERENCES `sesion_interaccion` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `evento_reconocimiento` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `id_sesion` INT NULL,
  `id_persona_institucional` VARCHAR(50) NOT NULL,
  `tipo_persona` VARCHAR(30) NOT NULL,
  `nombre_persona` VARCHAR(255) NULL,
  `confianza` DECIMAL(5,4) NOT NULL,
  `estado` VARCHAR(30) NOT NULL,
  `motivo` VARCHAR(255) NULL,
  `recibida_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_evento_sesion` (`id_sesion`),
  INDEX `ix_evento_persona` (`id_persona_institucional`),
  CONSTRAINT `fk_evento_sesion`
    FOREIGN KEY (`id_sesion`) REFERENCES `sesion_interaccion` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
