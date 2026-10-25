"""Контрактные тесты для исследовательского судна «Карась-1»."""

import unittest

from crucian_one import (
    CrazyVehicleError,
    CrucianOne,
    KarasCannotMoveOnLand,
    KarasError,
    KarasNoEnergy,
)


def make_vehicle(**overrides: object) -> CrucianOne:
    """Создать судно с базовыми параметрами, заменяя указанные значения."""
    params: dict[str, object] = {
        "name": "Карась-1",
        "mass_kg": 0.4,
        "body_length_cm": 25.0,
        "max_speed_kmh": 4.0,
        "max_depth_m": 3.0,
        "energy": 100.0,
    }
    params.update(overrides)
    return CrucianOne(**params)  # type: ignore[arg-type]


class Pilot:
    """Тестовая обёртка: отдаёт команды судну на языке сценариев."""

    def __init__(self, vehicle: CrucianOne) -> None:
        self._vehicle = vehicle

    def включить_камеру(self) -> None:
        self._vehicle.start_recording()

    def плыть(self, distance_km: float, direction: str, depth_m: float = 0.0) -> float:
        return self._vehicle.move(distance_km, direction, depth_m)

    def проверить_препятствие(self, obstacle: str) -> bool:
        return self._vehicle.can_pass(obstacle)

    def выключить_камеру(self) -> None:
        self._vehicle.stop_recording()


class CrucianOneModuleTests(unittest.TestCase):
    """Модульные проверки публичного интерфейса в стиле Arrange-Act-Assert."""

    def test_TC_01_constructor_initial_state(self) -> None:
        """TC-01: корректный конструктор задаёт описанное начальное состояние."""
        # Arrange
        vehicle = CrucianOne("Карась-1", 0.4, 25.0, 4.0, 3.0)

        # Act
        status = vehicle.get_status()

        # Assert
        self.assertEqual(vehicle.name, "Карась-1")
        self.assertEqual(vehicle.mass_kg, 0.4)
        self.assertEqual(vehicle.body_length_cm, 25.0)
        self.assertEqual(vehicle.max_speed_kmh, 4.0)
        self.assertEqual(vehicle.max_depth_m, 3.0)
        self.assertEqual(vehicle.energy, 100.0)
        self.assertEqual(vehicle.position_km, 0.0)
        self.assertTrue(vehicle.is_swimming)
        self.assertFalse(vehicle.gopro_recording)
        self.assertEqual(status["name"], "Карась-1")

    def test_TC_02_empty_name(self) -> None:
        """TC-02: пустое или состоящее из пробелов имя запрещено."""
        # Arrange / Act / Assert
        for name in ("", "   "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                make_vehicle(name=name)

    def test_TC_03_non_positive_physical_values(self) -> None:
        """TC-03: физические параметры конструктора должны быть положительными."""
        # Arrange
        invalid_values = {
            "mass_kg": 0,
            "body_length_cm": -1,
            "max_speed_kmh": 0,
            "max_depth_m": -0.1,
        }

        # Act / Assert
        for parameter, value in invalid_values.items():
            with self.subTest(parameter=parameter), self.assertRaises(ValueError):
                make_vehicle(**{parameter: value})

    def test_TC_04_energy_range(self) -> None:
        """TC-04: конструктор принимает только энергию в диапазоне 0…100."""
        # Arrange / Act / Assert
        for energy in (-0.1, 100.1, float("nan"), float("inf")):
            with self.subTest(energy=energy), self.assertRaises(ValueError):
                make_vehicle(energy=energy)
        self.assertEqual(make_vehicle(energy=0).energy, 0)
        self.assertEqual(make_vehicle(energy=100).energy, 100)

    def test_TC_05_wrong_argument_types(self) -> None:
        """TC-05: неверные типы аргументов публичного API вызывают TypeError."""
        # Arrange
        invalid_constructor_params = (
            {"name": 1},
            {"mass_kg": "0.4"},
            {"body_length_cm": "25"},
            {"max_speed_kmh": "4"},
            {"max_depth_m": "3"},
            {"energy": "100"},
            {"energy": True},
        )

        # Act / Assert
        for params in invalid_constructor_params:
            with self.subTest(params=params), self.assertRaises(TypeError):
                make_vehicle(**params)

        vehicle = make_vehicle()
        invalid_calls = (
            lambda: vehicle.move("1", "north"),
            lambda: vehicle.move(1, None),
            lambda: vehicle.move(1, "north", depth_m="0"),
            lambda: vehicle.move(1, "north", environment=None),
            lambda: vehicle.can_pass(None),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(TypeError):
                call()

    def test_TC_06_move_updates_state(self) -> None:
        """TC-06: успешный ход возвращает время и обновляет энергию и позицию."""
        # Arrange
        vehicle = make_vehicle(energy=100)

        # Act
        elapsed = vehicle.move(2, "east")

        # Assert
        self.assertAlmostEqual(elapsed, 0.5)
        self.assertEqual(vehicle.position_km, 2)
        self.assertEqual(vehicle.energy, 96)
        self.assertTrue(vehicle.is_swimming)

    def test_TC_07_exact_energy_boundary(self) -> None:
        """TC-07: расход ровно всего запаса допустим, следующий ход — нет."""
        # Arrange
        vehicle = make_vehicle(energy=4)

        # Act
        vehicle.move(2, "east")

        # Assert
        self.assertEqual(vehicle.energy, 0)
        self.assertEqual(vehicle.position_km, 2)
        with self.assertRaises(KarasNoEnergy):
            vehicle.move(1, "east")
        self.assertEqual(vehicle.energy, 0)
        self.assertEqual(vehicle.position_km, 2)

    def test_TC_08_move_without_energy(self) -> None:
        """TC-08: при нехватке энергии ход отклоняется без изменения состояния."""
        # Arrange
        vehicle = make_vehicle(energy=3)

        # Act / Assert
        with self.assertRaises(KarasNoEnergy):
            vehicle.move(2, "east")
        self.assertEqual(vehicle.energy, 3)
        self.assertEqual(vehicle.position_km, 0)

    def test_TC_09_invalid_route_parameters(self) -> None:
        """TC-09: неверные расстояние, курс, среда и глубина дают ValueError."""
        # Arrange
        vehicle = make_vehicle(energy=50)
        invalid_routes = (
            (0, "north", 0, "water"),
            (1, "northeast", 0, "water"),
            (1, "north", 0, "air"),
            (1, "north", -0.1, "water"),
            (1, "north", 3.1, "water"),
        )

        # Act / Assert
        for distance, direction, depth, environment in invalid_routes:
            with self.subTest(route=(distance, direction, depth, environment)):
                with self.assertRaises(ValueError):
                    vehicle.move(distance, direction, depth, environment)
                self.assertEqual(vehicle.position_km, 0)
                self.assertEqual(vehicle.energy, 50)

    def test_TC_10_cannot_move_on_land(self) -> None:
        """TC-10: движение по суше вызывает доменное исключение без побочного эффекта."""
        # Arrange
        vehicle = make_vehicle(energy=50)

        # Act / Assert
        with self.assertRaises(KarasCannotMoveOnLand):
            vehicle.move(1, "north", environment="land")
        self.assertEqual(vehicle.position_km, 0)
        self.assertEqual(vehicle.energy, 50)

    def test_TC_11_open_water(self) -> None:
        """TC-11: открытый водоём всегда проходим и проверка ничего не меняет."""
        # Arrange
        vehicle = make_vehicle(energy=50)

        # Act
        result = vehicle.can_pass("open_water")

        # Assert
        self.assertTrue(result)
        self.assertEqual(vehicle.energy, 50)
        self.assertEqual(vehicle.position_km, 0)

    def test_TC_12_narrow_channel_boundary(self) -> None:
        """TC-12: рыба длиной ровно 30 см проходит узкий канал."""
        # Arrange
        vehicle = make_vehicle(body_length_cm=30)

        # Act
        result = vehicle.can_pass("narrow_channel")

        # Assert
        self.assertTrue(result)

    def test_TC_13_channel_net_and_unknown(self) -> None:
        """TC-13: длинная рыба и сеть непроходимы, неизвестное препятствие ошибочно."""
        # Arrange
        vehicle = make_vehicle(body_length_cm=30.1)

        # Act / Assert
        self.assertFalse(vehicle.can_pass("narrow_channel"))
        self.assertFalse(vehicle.can_pass("net"))
        with self.assertRaises(ValueError):
            vehicle.can_pass("rock")
        self.assertEqual(vehicle.position_km, 0)

    def test_TC_14_start_recording_once(self) -> None:
        """TC-14: повторный запуск записи не списывает энергию второй раз."""
        # Arrange
        vehicle = make_vehicle(energy=10)

        # Act
        vehicle.start_recording()
        vehicle.start_recording()

        # Assert
        self.assertTrue(vehicle.gopro_recording)
        self.assertEqual(vehicle.energy, 9)

    def test_TC_15_recording_without_energy(self) -> None:
        """TC-15: запуск GoPro без энергии отклоняется без смены состояния."""
        # Arrange
        vehicle = make_vehicle(energy=0)

        # Act / Assert
        with self.assertRaises(KarasNoEnergy):
            vehicle.start_recording()
        self.assertFalse(vehicle.gopro_recording)
        self.assertEqual(vehicle.energy, 0)

    def test_TC_16_stop_recording(self) -> None:
        """TC-16: остановка выключенной записи идемпотентна и бесплатна."""
        # Arrange
        vehicle = make_vehicle(energy=10)

        # Act
        vehicle.stop_recording()
        vehicle.stop_recording()

        # Assert
        self.assertFalse(vehicle.gopro_recording)
        self.assertEqual(vehicle.energy, 10)

    def test_TC_17_status_snapshot(self) -> None:
        """TC-17: статус содержит публичный снимок, не связанный с объектом."""
        # Arrange
        vehicle = make_vehicle(energy=20)
        expected_keys = {"name", "energy", "position_km", "is_swimming", "gopro_recording"}

        # Act
        status = vehicle.get_status()
        status["energy"] = -100
        status["extra"] = "изменено снаружи"

        # Assert
        self.assertEqual(
            set(vehicle.get_status()),
            expected_keys,
        )
        self.assertEqual(vehicle.energy, 20)

    def test_TC_18_public_attributes_are_read_only(self) -> None:
        """TC-18: публичные атрибуты нельзя переназначать."""
        # Arrange
        vehicle = make_vehicle()
        original_values = {
            "name": vehicle.name,
            "mass_kg": vehicle.mass_kg,
            "body_length_cm": vehicle.body_length_cm,
            "max_speed_kmh": vehicle.max_speed_kmh,
            "max_depth_m": vehicle.max_depth_m,
            "energy": vehicle.energy,
            "position_km": vehicle.position_km,
            "is_swimming": vehicle.is_swimming,
            "gopro_recording": vehicle.gopro_recording,
        }

        # Act / Assert
        for attribute, original in original_values.items():
            with self.subTest(attribute=attribute), self.assertRaises(AttributeError):
                setattr(vehicle, attribute, original)
            self.assertEqual(getattr(vehicle, attribute), original)

    def test_TC_19_domain_exception_hierarchy(self) -> None:
        """TC-19: экспортируемые доменные исключения имеют заданную иерархию."""
        # Arrange / Act / Assert
        self.assertTrue(issubclass(CrazyVehicleError, Exception))
        self.assertTrue(issubclass(KarasError, CrazyVehicleError))
        self.assertTrue(issubclass(KarasNoEnergy, KarasError))
        self.assertTrue(issubclass(KarasCannotMoveOnLand, KarasError))


class CrucianOneScenarioTests(unittest.TestCase):
    """Сценарные проверки GWT через тестовую обёртку-пилота."""

    def test_TC_20_record_and_pass_channel(self) -> None:
        """TC-20: пилот снимает маршрут и проверяет узкий канал."""
        # Given
        vehicle = make_vehicle(body_length_cm=25, max_speed_kmh=4, energy=20)
        pilot = Pilot(vehicle)

        # When
        pilot.включить_камеру()
        elapsed = pilot.плыть(2, "east")
        can_pass = pilot.проверить_препятствие("narrow_channel")

        # Then
        self.assertTrue(vehicle.gopro_recording)
        self.assertAlmostEqual(elapsed, 0.5)
        self.assertEqual(vehicle.position_km, 2)
        self.assertEqual(vehicle.energy, 15)
        self.assertTrue(can_pass)

    def test_TC_21_depth_limit_scenario(self) -> None:
        """TC-21: допустимая глубина проходит, превышение лимита не меняет состояние."""
        # Given
        vehicle = make_vehicle(max_speed_kmh=4, max_depth_m=3, energy=50)
        pilot = Pilot(vehicle)

        # When
        elapsed = pilot.плыть(1, "south", depth_m=2.5)

        # Then
        self.assertAlmostEqual(elapsed, 0.25)
        self.assertEqual(vehicle.position_km, 1)
        self.assertEqual(vehicle.energy, 48)

        # When / Then
        with self.assertRaises(ValueError):
            pilot.плыть(1, "south", depth_m=3.5)
        self.assertEqual(vehicle.position_km, 1)
        self.assertEqual(vehicle.energy, 48)

    def test_TC_22_recording_and_empty_charge(self) -> None:
        """TC-22: недостаточный заряд прерывает ход, запись можно остановить."""
        # Given
        vehicle = make_vehicle(energy=5)
        pilot = Pilot(vehicle)

        # When
        pilot.включить_камеру()

        # Then
        self.assertEqual(vehicle.energy, 4)
        self.assertTrue(vehicle.gopro_recording)

        # When / Then
        with self.assertRaises(KarasNoEnergy):
            pilot.плыть(2.5, "west")
        self.assertEqual(vehicle.position_km, 0)
        self.assertEqual(vehicle.energy, 4)
        self.assertTrue(vehicle.gopro_recording)

        # When / Then
        pilot.выключить_камеру()
        self.assertFalse(vehicle.gopro_recording)
        self.assertEqual(vehicle.energy, 4)

    def test_TC_23_obstacle_route_scenario(self) -> None:
        """TC-23: пилот проверяет препятствия, не меняя состояние судна."""
        # Given
        vehicle = make_vehicle(body_length_cm=35, energy=30)
        pilot = Pilot(vehicle)

        # When
        results = (
            pilot.проверить_препятствие("open_water"),
            pilot.проверить_препятствие("narrow_channel"),
            pilot.проверить_препятствие("net"),
        )

        # Then
        self.assertEqual(results, (True, False, False))
        self.assertEqual(vehicle.position_km, 0)
        self.assertEqual(vehicle.energy, 30)


if __name__ == "__main__":
    unittest.main()
