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


-- Volcando estructura de base de datos para maxcim_app
CREATE DATABASE IF NOT EXISTS `maxcim_app` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `maxcim_app`;

-- Volcando estructura para tabla maxcim_app.interaccion
CREATE TABLE IF NOT EXISTS `interaccion` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_material` int DEFAULT NULL,
  `fk_alumno` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `fecha_hora` datetime NOT NULL,
  `pregunta` text NOT NULL,
  `respuesta` text NOT NULL,
  `path_audio_rpta` varchar(500) NOT NULL,
  `apreciacion_robot` text NOT NULL COMMENT 'Campo en el cual el robot dirá su "crítica" sobre la respuesta del alumno.',
  `rpta_correcta` tinyint(1) NOT NULL,
  `id_periodo` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_interaccion_alumno` (`fk_alumno`),
  KEY `ix_interaccion_material` (`id_material`),
  KEY `ix_interaccion_periodo` (`id_periodo`),
  CONSTRAINT `interaccion_id_material_foreign` FOREIGN KEY (`id_material`) REFERENCES `material` (`id`),
  CONSTRAINT `interaccion_id_periodo_foreign` FOREIGN KEY (`id_periodo`) REFERENCES `periodo` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=128 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Volcando datos para la tabla maxcim_app.interaccion: ~0 rows (aproximadamente)
INSERT INTO `interaccion` (`id`, `id_material`, `fk_alumno`, `fecha_hora`, `pregunta`, `respuesta`, `path_audio_rpta`, `apreciacion_robot`, `rpta_correcta`, `id_periodo`) VALUES
	(1, 2, '79398411', '2026-08-20 08:40:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña la soga', 'seed/79398411/9887aa4e01b64802a7ad763dcb221365.wav', 'Omitió una palabra al leer; conviene repasar la oración.', 0, 3),
	(2, 1, '79398411', '2026-08-21 10:10:00', '¿Qué nos da a entender la expresión \'pasito a pasito\' sobre el avance de la tortuga?', 'Que aunque el progreso sea pequeño y lento, si es constante permite llegar lejos y cumplir las metas.', 'seed/79398411/82705c3c71d74af6b00585c1789d6e54.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(3, 1, '79398411', '2026-08-22 10:15:00', '¿Qué error cometió la liebre que le costó perder la competencia?', 'Subestimar a su rival y confiarse demasiado hasta el punto de quedarse dormida.', 'seed/79398411/b08dcc5f789c4f1291b66c3116747a43.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(4, 2, '79398411', '2026-08-22 12:30:00', 'Lee en voz alta: "El sol calienta toda la mañana."', 'El sol calienta toda la mañana.', 'seed/79398411/e9b9b6017f654a099a6c3f57e716c709.wav', 'Lectura fluida y sin errores.', 1, 3),
	(5, 2, '79398411', '2026-08-26 08:00:00', 'Lee en voz alta: "Ese oso ama la miel."', 'oso ama la miel', 'seed/79398411/ed563e202a3949beb2fd35f503999742.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(6, 2, '79398411', '2026-08-26 12:40:00', 'Lee en voz alta: "Mi perro se llama Toto."', 'Mi se llama Toto', 'seed/79398411/d2a471608d2241dcabf818d363e11d9a.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(7, 1, '79398411', '2026-08-27 10:10:00', '¿Por qué la liebre era muy orgullosa?', 'Que el búho se fue volando y perdió todo.', 'seed/79398411/27f454b64fc849fba6fdaee178c9b731.wav', 'No logró inferir la razón; se sugiere reforzar la comprensión.', 0, 3),
	(8, 2, '79398411', '2026-08-27 10:30:00', 'Lee en voz alta: "Sale el sol."', 'Sale el sol.', 'seed/79398411/bfdc099a761c4ac9b7df6131ea69abc6.wav', 'Pronunció cada palabra con claridad.', 1, 3),
	(9, 1, '79398411', '2026-08-27 12:45:00', '¿Qué consejo le darías a una persona que presume mucho de sus habilidades frente a otros?', 'Se valora la propuesta de consejos orientados a la humildad, la empatía y el valor de respetar las capacidades ajenas.', 'seed/79398411/ff544fb74ebe43c095707698ed887fc3.wav', 'Respondió con seguridad y buen vocabulario.', 1, 3),
	(10, 2, '79398411', '2026-08-29 08:15:00', 'Lee en voz alta: "Mañana iré a la escuela muy temprano."', 'Mañana iré a la escuela muy temprano.', 'seed/79398411/2cd9f2ee95c94c48be8ecd2d9ddd8a5d.wav', 'Respetó los signos y el ritmo de la oración.', 1, 3),
	(11, 2, '79398411', '2026-08-29 08:45:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña salta la soga.', 'seed/79398411/75706bf5b4f1487c989935a84938c70c.wav', 'Lectura fluida y sin errores.', 1, 3),
	(12, 1, '79398411', '2026-08-29 11:10:00', '¿Por qué fue inútil que la liebre corriera con todas sus fuerzas al despertar?', 'Porque la tortuga ya había avanzado suficiente distancia y estaba cruzando la meta.', 'seed/79398411/ac5acb60bf6249cb9db9dedb6cefea19.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(13, 1, '79398411', '2026-08-29 12:30:00', '¿Quiénes se reunieron para presenciar la carrera?', 'Todos los animales.', 'seed/79398411/398a6fab30bc4468904155544f145d27.wav', 'Respuesta clara y bien fundamentada.', 1, 3),
	(14, 1, '79398411', '2026-08-31 11:10:00', '¿Alguna vez te has confiado demasiado al hacer una tarea o juego y tuviste un mal resultado? ¿Qué aprendiste?', 'Se evalúa la capacidad de autoanálisis y de relacionar la moraleja del texto con experiencias personales.', 'seed/79398411/fbff5f1bfd974ce6a8c3c193eebc5690.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(15, 2, '79333645', '2026-08-20 08:40:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña la soga', 'seed/79333645/22802e9b61924600b06dae2c93625fed.wav', 'Omitió una palabra al leer; conviene repasar la oración.', 0, 3),
	(16, 1, '79333645', '2026-08-21 10:10:00', '¿Qué nos da a entender la expresión \'pasito a pasito\' sobre el avance de la tortuga?', 'Que aunque el progreso sea pequeño y lento, si es constante permite llegar lejos y cumplir las metas.', 'seed/79333645/fee6122c7ee645b4ab80965c07f87d12.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(17, 1, '79333645', '2026-08-22 10:15:00', '¿Qué error cometió la liebre que le costó perder la competencia?', 'Subestimar a su rival y confiarse demasiado hasta el punto de quedarse dormida.', 'seed/79333645/929913708ef743d299e6a642cfdd1002.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(18, 2, '79333645', '2026-08-22 12:30:00', 'Lee en voz alta: "El sol calienta toda la mañana."', 'El sol calienta toda la mañana.', 'seed/79333645/afbcbc3a1c094d32859a2d1926cf54f2.wav', 'Lectura fluida y sin errores.', 1, 3),
	(19, 2, '79333645', '2026-08-26 08:00:00', 'Lee en voz alta: "Ese oso ama la miel."', 'oso ama la miel', 'seed/79333645/d985bcd7ee134f7b9a5fb422d326d26f.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(20, 2, '79333645', '2026-08-26 12:40:00', 'Lee en voz alta: "Mi perro se llama Toto."', 'Mi se llama Toto', 'seed/79333645/974752490cb7470c904e3626b63c78d2.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(21, 1, '79333645', '2026-08-27 10:10:00', '¿Por qué la liebre era muy orgullosa?', 'Que el búho se fue volando y perdió todo.', 'seed/79333645/317a0f74d6024253903a1c7604eef11a.wav', 'No logró inferir la razón; se sugiere reforzar la comprensión.', 0, 3),
	(22, 2, '79333645', '2026-08-27 12:45:00', 'Lee en voz alta: "Sale el sol."', 'Sale el sol.', 'seed/79333645/05b21123c4024f27a87bf48bdf2b321b.wav', 'Pronunció cada palabra con claridad.', 1, 3),
	(23, 1, '79333645', '2026-08-28 10:30:00', '¿Qué consejo le darías a una persona que presume mucho de sus habilidades frente a otros?', 'Se valora la propuesta de consejos orientados a la humildad, la empatía y el valor de respetar las capacidades ajenas.', 'seed/79333645/75a1eb63d001413bb0cbe284052f872a.wav', 'Respondió con seguridad y buen vocabulario.', 1, 3),
	(24, 2, '79333645', '2026-08-29 08:15:00', 'Lee en voz alta: "Mañana iré a la escuela muy temprano."', 'Mañana iré a la escuela muy temprano.', 'seed/79333645/87587caef14c4e31b95be089e1f37c34.wav', 'Respetó los signos y el ritmo de la oración.', 1, 3),
	(25, 2, '79333645', '2026-08-29 08:45:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña salta la soga.', 'seed/79333645/539da2e4bb5a4e4c9152fea3576fe177.wav', 'Lectura fluida y sin errores.', 1, 3),
	(26, 1, '79333645', '2026-08-29 11:10:00', '¿Por qué fue inútil que la liebre corriera con todas sus fuerzas al despertar?', 'Porque la tortuga ya había avanzado suficiente distancia y estaba cruzando la meta.', 'seed/79333645/fbbffa9b7b1b4f9e919cab29c4b075ba.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(27, 1, '79333645', '2026-08-29 12:30:00', '¿Quiénes se reunieron para presenciar la carrera?', 'Todos los animales.', 'seed/79333645/323a015d6d9f49e9a332a9af195f67ba.wav', 'Respuesta clara y bien fundamentada.', 1, 3),
	(28, 1, '79333645', '2026-08-31 11:10:00', '¿Alguna vez te has confiado demasiado al hacer una tarea o juego y tuviste un mal resultado? ¿Qué aprendiste?', 'Se evalúa la capacidad de autoanálisis y de relacionar la moraleja del texto con experiencias personales.', 'seed/79333645/745717e0c301427f832cc67b3397c718.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(43, 2, '79211796', '2026-08-20 08:40:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña la soga', 'seed/79211796/900236b5842546a18a7ed14c4463a22a.wav', 'Omitió una palabra al leer; conviene repasar la oración.', 0, 3),
	(44, 1, '79211796', '2026-08-21 10:10:00', '¿Qué nos da a entender la expresión \'pasito a pasito\' sobre el avance de la tortuga?', 'Que aunque el progreso sea pequeño y lento, si es constante permite llegar lejos y cumplir las metas.', 'seed/79211796/36a95d09b14745e488b723c67fa959a4.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(45, 1, '79211796', '2026-08-22 10:15:00', '¿Qué error cometió la liebre que le costó perder la competencia?', 'Subestimar a su rival y confiarse demasiado hasta el punto de quedarse dormida.', 'seed/79211796/34ce474cc71a456ab7359bfe5298cf0f.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(46, 2, '79211796', '2026-08-22 12:30:00', 'Lee en voz alta: "El sol calienta toda la mañana."', 'El sol calienta toda la mañana.', 'seed/79211796/439a0155e38147679f8925923faa9be9.wav', 'Lectura fluida y sin errores.', 1, 3),
	(47, 2, '79211796', '2026-08-26 08:00:00', 'Lee en voz alta: "Ese oso ama la miel."', 'oso ama la miel', 'seed/79211796/1c29d0f424b940e2912039cfad7d1175.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(48, 2, '79211796', '2026-08-26 12:40:00', 'Lee en voz alta: "Mi perro se llama Toto."', 'Mi se llama Toto', 'seed/79211796/f27501c0149c4e6bb9cbfe171db45f5d.wav', 'Se trabó en una palabra y no volvió a intentarlo.', 0, 3),
	(49, 1, '79211796', '2026-08-27 10:10:00', '¿Por qué la liebre era muy orgullosa?', 'Que el búho se fue volando y perdió todo.', 'seed/79211796/dca21c7d621542f3899545c74f906c7c.wav', 'No logró inferir la razón; se sugiere reforzar la comprensión.', 0, 3),
	(50, 2, '79211796', '2026-08-27 12:45:00', 'Lee en voz alta: "Sale el sol."', 'Sale el sol.', 'seed/79211796/5cd0f7aeb941419091e0e7479146d23d.wav', 'Pronunció cada palabra con claridad.', 1, 3),
	(51, 1, '79211796', '2026-08-28 10:30:00', '¿Qué consejo le darías a una persona que presume mucho de sus habilidades frente a otros?', 'Se valora la propuesta de consejos orientados a la humildad, la empatía y el valor de respetar las capacidades ajenas.', 'seed/79211796/d9d469104f00419e8cc2d9adf6a6a147.wav', 'Respondió con seguridad y buen vocabulario.', 1, 3),
	(52, 2, '79211796', '2026-08-29 08:15:00', 'Lee en voz alta: "Mañana iré a la escuela muy temprano."', 'Mañana iré a la escuela muy temprano.', 'seed/79211796/4371e844ab74491789c22b0f6f7e3b3c.wav', 'Respetó los signos y el ritmo de la oración.', 1, 3),
	(53, 2, '79211796', '2026-08-29 08:45:00', 'Lee en voz alta: "La niña salta la soga."', 'La niña salta la soga.', 'seed/79211796/099fa162ac4d41c099120ccce06f7161.wav', 'Lectura fluida y sin errores.', 1, 3),
	(54, 1, '79211796', '2026-08-29 11:10:00', '¿Por qué fue inútil que la liebre corriera con todas sus fuerzas al despertar?', 'Porque la tortuga ya había avanzado suficiente distancia y estaba cruzando la meta.', 'seed/79211796/803f26af7649419490311a5c4b36e172.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(55, 1, '79211796', '2026-08-29 12:30:00', '¿Quiénes se reunieron para presenciar la carrera?', 'Todos los animales.', 'seed/79211796/1c93c2c5c6a0440a8329f46ea09bae2c.wav', 'Respuesta clara y bien fundamentada.', 1, 3),
	(56, 1, '79211796', '2026-08-31 11:10:00', '¿Alguna vez te has confiado demasiado al hacer una tarea o juego y tuviste un mal resultado? ¿Qué aprendiste?', 'Se evalúa la capacidad de autoanálisis y de relacionar la moraleja del texto con experiencias personales.', 'seed/79211796/70372ee28993497a83081a9e188ee981.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(100, 2, '79211796', '2026-08-20 08:40:00', 'Lee en voz alta: "La abuela cuenta un cuento antes de dormir."', 'La abuela cuenta un cuento antes ...', 'seed/79211796/e2a5bac2eb5344759a79956bbe49a40d.wav', 'Omitió una palabra al leer; conviene repasar la oración.', 0, 3),
	(101, 1, '79211796', '2026-08-21 10:10:00', '¿Qué nos da a entender la expresión \'pasito a pasito\' sobre el avance de la tortuga?', 'Que aunque el progreso sea pequeño y lento, si es constante permite llegar lejos y cumplir las metas.', 'seed/79211796/7d18d7e4dc0f4ce68a76ceb659f1f8a5.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(102, 1, '79211796', '2026-08-22 10:15:00', '¿Qué error cometió la liebre que le costó perder la competencia?', 'Subestimar a su rival y confiarse demasiado hasta el punto de quedarse dormida.', 'seed/79211796/e9837b51fe004db590f00acbdcacc3e7.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(103, NULL, '79211796', '2026-08-22 12:30:00', '¿Cómo te sentiste hoy en clase?', 'Me sentí contento porque entendí la lectura y participé en clase.', 'seed/79211796/2b2a0edd979e43f29f07adb9e1a5f964.wav', 'Buen intercambio: escuchó, respondió y hasta preguntó de vuelta.', 1, 3),
	(104, 1, '79211796', '2026-08-26 08:00:00', '¿Qué consejo le darías a una persona que presume mucho de sus habilidades frente a otros?', 'No me acuerdo muy bien.', 'seed/79211796/f8d8213ad4f34f44a14a4ddd297d80e8.wav', 'Confundió a los personajes de la historia.', 0, 3),
	(105, NULL, '79211796', '2026-08-26 12:40:00', '¿Qué te gustaría ser cuando seas grande?', 'Mmm... nada.', 'seed/79211796/a0a504d39b554f4c8a71f7504ba748d3.wav', 'Respuestas muy cortas; conviene animarlo a desarrollar sus ideas.', 0, 3),
	(106, 1, '79211796', '2026-08-27 10:10:00', '¿Qué lección aprendió la liebre al final del cuento?', 'Nada, no pasó nada.', 'seed/79211796/79453f1234eb4b9793ba90a4eaf3ba85.wav', 'Respondió de forma vaga; conviene volver a leer ese pasaje.', 0, 3),
	(107, 2, '79211796', '2026-08-27 12:45:00', 'Lee en voz alta: "El gato sube al techo."', 'El gato sube al techo.', 'seed/79211796/d8920745513c4688b95d417fbdfa7201.wav', 'Respetó los signos y el ritmo de la oración.', 1, 3),
	(108, 1, '79211796', '2026-08-28 10:30:00', '¿Por qué crees que es importante respetar el ritmo de aprendizaje o de trabajo de cada persona?', 'Se evalúa la reflexión sobre la diversidad de habilidades, la paciencia y la inclusión en el entorno escolar y social.', 'seed/79211796/87aef7e2173f4931878a45f1ede22933.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(109, 1, '79211796', '2026-08-29 08:15:00', '¿Dónde acordaron poner su apuesta?', 'En una piedra.', 'seed/79211796/9d0088fdcb71409faa97601b12398216.wav', 'Respondió con seguridad y buen vocabulario.', 1, 3),
	(110, NULL, '79211796', '2026-08-29 08:45:00', '¿Cómo te sentiste hoy en clase?', 'Me pongo nervioso en las exposiciones, pero practico en casa con mi mamá.', 'seed/79211796/b8d798b88a7047fc92c0ab36e39657ba.wav', 'Se expresó con confianza y buen vocabulario para su edad.', 1, 3),
	(111, 2, '79211796', '2026-08-29 11:10:00', 'Lee en voz alta: "La luna sale de noche."', 'La luna sale de noche.', 'seed/79211796/71fb6ac7ace34d13b5f9a959623ba03c.wav', 'Lectura fluida y sin errores.', 1, 3),
	(112, 2, '79211796', '2026-08-29 12:30:00', 'Lee en voz alta: "Ana ama a su papá."', 'Ana ama a su papá.', 'seed/79211796/05a2555b463e461aaad4f64927549bd1.wav', 'Leyó la oración completa con buena pronunciación.', 1, 3),
	(113, NULL, '79211796', '2026-08-31 11:10:00', 'Cuéntame algo nuevo que hayas aprendido esta semana.', 'Elegiría un perro, porque podría pasearlo y cuidarlo todos los días.', 'seed/79211796/1e966cdc944a42839611836baf19e377.wav', 'Se mantuvo en el tema y aportó detalles propios.', 1, 3),
	(114, 2, '79567351', '2026-08-20 08:40:00', 'Lee en voz alta: "La abuela cuenta un cuento antes de dormir."', 'La abuela cuenta un cuento antes ...', 'seed/79567351/ef8ec4f297c241c087b0ad10eebc16c9.wav', 'Omitió una palabra al leer; conviene repasar la oración.', 0, 3),
	(115, 1, '79567351', '2026-08-21 10:10:00', '¿Qué nos da a entender la expresión \'pasito a pasito\' sobre el avance de la tortuga?', 'Que aunque el progreso sea pequeño y lento, si es constante permite llegar lejos y cumplir las metas.', 'seed/79567351/0a6d9e79be984883a5687c9736a08c93.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(116, 1, '79567351', '2026-08-22 10:15:00', '¿Qué error cometió la liebre que le costó perder la competencia?', 'Subestimar a su rival y confiarse demasiado hasta el punto de quedarse dormida.', 'seed/79567351/319b21a1db144f4db6b4e4b97298f6cf.wav', 'Identificó correctamente el dato del texto.', 1, 3),
	(117, NULL, '79567351', '2026-08-22 12:30:00', '¿Cómo te sentiste hoy en clase?', 'Me sentí contento porque entendí la lectura y participé en clase.', 'seed/79567351/62d2bad3e1cc4990919a22cf24f16c4b.wav', 'Buen intercambio: escuchó, respondió y hasta preguntó de vuelta.', 1, 3),
	(118, 1, '79567351', '2026-08-26 08:00:00', '¿Qué consejo le darías a una persona que presume mucho de sus habilidades frente a otros?', 'No me acuerdo muy bien.', 'seed/79567351/92fb18e0d065430b99a3c305e2f78863.wav', 'Confundió a los personajes de la historia.', 0, 3),
	(119, NULL, '79567351', '2026-08-26 12:40:00', '¿Qué te gustaría ser cuando seas grande?', 'Mmm... nada.', 'seed/79567351/651fabbb394e4210b6f345546cac372b.wav', 'Respuestas muy cortas; conviene animarlo a desarrollar sus ideas.', 0, 3),
	(120, 1, '79567351', '2026-08-27 10:10:00', '¿Qué lección aprendió la liebre al final del cuento?', 'Nada, no pasó nada.', 'seed/79567351/80e45f1927cf4d4a952fabe03d587cd7.wav', 'Respondió de forma vaga; conviene volver a leer ese pasaje.', 0, 3),
	(121, 2, '79567351', '2026-08-27 12:45:00', 'Lee en voz alta: "El gato sube al techo."', 'El gato sube al techo.', 'seed/79567351/a954218004974c45bd96d0c67ecdd6aa.wav', 'Respetó los signos y el ritmo de la oración.', 1, 3),
	(122, 1, '79567351', '2026-08-28 10:30:00', '¿Por qué crees que es importante respetar el ritmo de aprendizaje o de trabajo de cada persona?', 'Se evalúa la reflexión sobre la diversidad de habilidades, la paciencia y la inclusión en el entorno escolar y social.', 'seed/79567351/c0e69ebbc1ca4cfab3e3d9dc09f93278.wav', 'Comprendió la idea principal y la explicó con sus palabras.', 1, 3),
	(123, 1, '79567351', '2026-08-29 08:15:00', '¿Dónde acordaron poner su apuesta?', 'En una piedra.', 'seed/79567351/1bb763060cda4276ac4c3cc9f94de830.wav', 'Respondió con seguridad y buen vocabulario.', 1, 3),
	(124, NULL, '79567351', '2026-08-29 08:45:00', '¿Cómo te sentiste hoy en clase?', 'Me pongo nervioso en las exposiciones, pero practico en casa con mi mamá.', 'seed/79567351/a929d389bdb34d7aa930b802a2b04666.wav', 'Se expresó con confianza y buen vocabulario para su edad.', 1, 3),
	(125, 2, '79567351', '2026-08-29 11:10:00', 'Lee en voz alta: "La luna sale de noche."', 'La luna sale de noche.', 'seed/79567351/a3e4cd25b46544abbdc296c71235861a.wav', 'Lectura fluida y sin errores.', 1, 3),
	(126, 2, '79567351', '2026-08-29 12:30:00', 'Lee en voz alta: "Ana ama a su papá."', 'Ana ama a su papá.', 'seed/79567351/0bb5b53ceb594381b6c768875129188e.wav', 'Leyó la oración completa con buena pronunciación.', 1, 3),
	(127, NULL, '79567351', '2026-08-31 11:10:00', 'Cuéntame algo nuevo que hayas aprendido esta semana.', 'Elegiría un perro, porque podría pasearlo y cuidarlo todos los días.', 'seed/79567351/16be2474b5814b4397d449fe535e8232.wav', 'Se mantuvo en el tema y aportó detalles propios.', 1, 3);

-- Volcando estructura para tabla maxcim_app.material
CREATE TABLE IF NOT EXISTS `material` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre_material` varchar(255) NOT NULL,
  `tipo_material` varchar(255) NOT NULL,
  `path_audio` varchar(500) DEFAULT NULL,
  `path_texto` varchar(500) DEFAULT NULL,
  `path_audio_resumen` varchar(500) DEFAULT NULL,
  `path_texto_resumen` varchar(500) DEFAULT NULL,
  `path_preguntas` text NOT NULL,
  `fecha_subido` date NOT NULL,
  `fk_user` varchar(50) NOT NULL,
  `fk_user_name` varchar(255) DEFAULT NULL,
  `id_periodo` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_material_docente` (`fk_user`),
  KEY `ix_material_periodo` (`id_periodo`),
  CONSTRAINT `material_id_periodo_foreign` FOREIGN KEY (`id_periodo`) REFERENCES `periodo` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Volcando datos para la tabla maxcim_app.material: ~0 rows (aproximadamente)
INSERT INTO `material` (`id`, `nombre_material`, `tipo_material`, `path_audio`, `path_texto`, `path_audio_resumen`, `path_texto_resumen`, `path_preguntas`, `fecha_subido`, `fk_user`, `fk_user_name`, `id_periodo`) VALUES
	(1, 'La Liebre y La Tortuga', 'cuento', 'uploads/f977996050744f7ea328365d8624a50b/audio.wav', 'uploads/f977996050744f7ea328365d8624a50b/texto.txt', 'uploads/f977996050744f7ea328365d8624a50b/audio_resumen.wav', 'uploads/f977996050744f7ea328365d8624a50b/resumen.txt', 'uploads/f977996050744f7ea328365d8624a50b/preguntas.json', '2026-08-31', '70385', 'OSCAR ALEXIS RODAS ROSALES', 3),
	(2, 'Oraciones Test', 'oracion', NULL, NULL, NULL, NULL, 'uploads/d17ba11d1f85448f92ea87897757bf31/oraciones.json', '2026-08-31', '70385', 'OSCAR ALEXIS RODAS ROSALES', 3);

-- Volcando estructura para tabla maxcim_app.periodo
CREATE TABLE IF NOT EXISTS `periodo` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(50) NOT NULL,
  `anio` int NOT NULL,
  `fecha_inicio` date NOT NULL,
  `fecha_fin` date NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_periodo_anio_nombre` (`anio`,`nombre`),
  CONSTRAINT `chk_periodo_fechas` CHECK ((`fecha_fin` >= `fecha_inicio`))
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Volcando datos para la tabla maxcim_app.periodo: ~4 rows (aproximadamente)
INSERT INTO `periodo` (`id`, `nombre`, `anio`, `fecha_inicio`, `fecha_fin`) VALUES
	(1, 'I BIMESTRE', 2026, '2026-03-02', '2026-05-08'),
	(2, 'II BIMESTRE', 2026, '2026-05-11', '2026-07-24'),
	(3, 'III BIMESTRE', 2026, '2026-08-03', '2026-10-09'),
	(4, 'IV BIMESTRE', 2026, '2026-10-12', '2026-12-18');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
