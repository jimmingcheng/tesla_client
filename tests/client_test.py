import pytest
import requests_mock

from tesla_client.client import APIClient
from tesla_client.client import HOST
from tesla_client.vehicle import Vehicle
from tesla_client.vehicle import VehicleAsleepError
from tesla_client.vehicle import VehicleDidNotWakeError


ACCESS_TOKEN = 'aCCESStOKEN'
VIN = '5YJ3E1EA7HF000000'
VEHICLE_NAME = 'Red Car'


@pytest.fixture
def mock_vehicle():
    return Vehicle(
        client=APIClient(ACCESS_TOKEN),
        vehicle_json={'vin': VIN, 'display_name': VEHICLE_NAME},
    )


class Test_wake_up:
    def test_without_wait(self, mock_vehicle: Vehicle) -> None:
        expected_response = {'state': 'asleep'}
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': expected_response}, 'status_code': 200},
                ]
            )
            mock_vehicle.wake_up(wait_for_wake=False)

    def test_with_wait(self, mock_vehicle: Vehicle) -> None:
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'online'}}, 'status_code': 200},
                ]
            )
            mock_vehicle.wake_up(wait_for_wake=True)

    def test_wait_failed(self, mock_vehicle: Vehicle) -> None:
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                ]
            )

            with pytest.raises(VehicleDidNotWakeError):
                mock_vehicle._wait_for_wake_up(retry_interval_seconds=[1, 1])


class Test_load_vehicle_data:
    def test_do_not_wake_asleep(self, mock_vehicle: Vehicle) -> None:
        with requests_mock.Mocker() as m:
            m.get(
                f'{HOST}/api/1/vehicles/{VIN}/vehicle_data',
                json={'response': None},
            )

            with pytest.raises(VehicleAsleepError):
                mock_vehicle.load_vehicle_data(wait_for_wake=False, do_not_wake=True)

    def test_waits_for_wake(self, mock_vehicle: Vehicle) -> None:
        battery_range = 123.45
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'online'}}, 'status_code': 200},
                ]
            )

            m.get(
                f'{HOST}/api/1/vehicles/{VIN}/vehicle_data',
                response_list=[
                    {'json': {'response': None}, 'status_code': 200},
                    {'json': {'response': {'charge_state': {'battery_range': battery_range}}, 'status_code': 200}},
                ]
            )

            mock_vehicle.load_vehicle_data(wait_for_wake=True, do_not_wake=False)
            assert mock_vehicle.get_charge_state().battery_range == battery_range

    def test_fills_vehicle_attrs(self, mock_vehicle: Vehicle) -> None:
        battery_range = 123.45
        latitude = 33.111111
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'online'}}, 'status_code': 200},
                ]
            )

            m.get(
                f'{HOST}/api/1/vehicles/{VIN}/vehicle_data',
                response_list=[
                    {'json': {'response': None}, 'status_code': 200},
                    {'json': {'response': {
                        'charge_state': {'battery_range': battery_range},
                        'drive_state': {'latitude': latitude},
                    }}, 'status_code': 200},
                ],
            )

            mock_vehicle.load_vehicle_data(wait_for_wake=True, do_not_wake=False)

            assert mock_vehicle.get_charge_state().battery_range == battery_range
            assert mock_vehicle.get_drive_state().latitude == latitude


class Test_command:
    def test_waits_for_wake_and_executes(self, mock_vehicle: Vehicle) -> None:
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/wake_up',
                response_list=[
                    {'json': {'response': {'state': 'asleep'}}, 'status_code': 200},
                    {'json': {'response': {'state': 'online'}}, 'status_code': 200},
                ]
            )
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/command/door_lock',
                response_list=[
                    {'json': {'response': None}, 'status_code': 200},
                    {'json': {'response': {'result': 'true'}}, 'status_code': 200},
                ],
            )

            mock_vehicle.door_lock()
