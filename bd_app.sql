-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Versión del servidor:         8.4.3 - MySQL Community Server - GPL
-- SO del servidor:              Win64
-- HeidiSQL Versión:             12.8.0.6908
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Volcando estructura de base de datos para test
CREATE DATABASE IF NOT EXISTS `test` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `test`;

-- Volcando estructura para tabla test.material
CREATE TABLE IF NOT EXISTS `material` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre_material` varchar(255) NOT NULL,
  `path_audio` varchar(500) NOT NULL,
  `path_texto` varchar(500) NOT NULL,
  `path_audio_resumen` varchar(500) NOT NULL,
  `path_texto_resumen` varchar(500) NOT NULL,
  `fecha_subido` date NOT NULL DEFAULT (curdate()),
  `fk_user` varchar(50) DEFAULT NULL,
  `path_preguntas` varchar(500) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Volcando datos para la tabla test.material: ~4 rows (aproximadamente)
INSERT INTO `material` (`id`, `nombre_material`, `path_audio`, `path_texto`, `path_audio_resumen`, `path_texto_resumen`, `fecha_subido`, `fk_user`, `path_preguntas`) VALUES
	(8, 'La Liebre y La Tortuga', 'uploads/5a8f32c5d3d34ca78227839951df744a/audio.wav', 'uploads/5a8f32c5d3d34ca78227839951df744a/texto.txt', 'uploads/5a8f32c5d3d34ca78227839951df744a/audio_resumen.wav', 'uploads/5a8f32c5d3d34ca78227839951df744a/resumen.txt', '2026-07-31', '72737674', 'uploads/5a8f32c5d3d34ca78227839951df744a/preguntas.json'),
	(10, 'El Gran Secreto del Bosque Parlanchín', 'uploads/ca88cb573a7b42acae87ee14d7f99aa5/audio.wav', 'uploads/ca88cb573a7b42acae87ee14d7f99aa5/texto.txt', 'uploads/ca88cb573a7b42acae87ee14d7f99aa5/audio_resumen.wav', 'uploads/ca88cb573a7b42acae87ee14d7f99aa5/resumen.txt', '2026-07-31', '72737674', 'uploads/ca88cb573a7b42acae87ee14d7f99aa5/preguntas.json'),
	(11, 'El Día en que Nadie Quería Escuchar', 'uploads/d87f8547252943b4971f1287393d49aa/audio.wav', 'uploads/d87f8547252943b4971f1287393d49aa/texto.txt', 'uploads/d87f8547252943b4971f1287393d49aa/audio_resumen.wav', 'uploads/d87f8547252943b4971f1287393d49aa/resumen.txt', '2026-07-31', '72737674', 'uploads/d87f8547252943b4971f1287393d49aa/preguntas.json'),
	(12, 'Los Tres Cerditos', 'uploads/5574b3711cba42be97223ac0f958dcf8/audio.wav', 'uploads/5574b3711cba42be97223ac0f958dcf8/texto.txt', 'uploads/5574b3711cba42be97223ac0f958dcf8/audio_resumen.wav', 'uploads/5574b3711cba42be97223ac0f958dcf8/resumen.txt', '2026-07-31', '72737674', 'uploads/5574b3711cba42be97223ac0f958dcf8/preguntas.json');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
