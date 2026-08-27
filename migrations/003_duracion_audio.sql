-- Duración objetivo elegida por la docente y duración real medida del WAV.
-- Aplicar una sola vez después de 002_sesiones_web.sql sobre MySQL 8.

ALTER TABLE `material`
  ADD COLUMN `duracion_objetivo_minutos` SMALLINT NULL
    AFTER `path_preguntas`,
  ADD COLUMN `duracion_audio_segundos` DECIMAL(8,2) NULL
    AFTER `duracion_objetivo_minutos`;
