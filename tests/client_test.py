import pytest
import requests_mock

from tesla_client.client import HOST
from tesla_client.account import Account
from tesla_client.vehicle import Vehicle


ACCESS_TOKEN = 'aCCESStOKEN'
VIN = '5YJ3E1EA7HF000000'
VEHICLE_NAME = 'Red Car'


class FakeAccount(Account):
    def get_fresh_access_token(self) -> str:
        return ACCESS_TOKEN


@pytest.fixture
def mock_vehicle():
    return Vehicle(
        account=FakeAccount(),
        vehicle_json={'vin': VIN, 'display_name': VEHICLE_NAME, 'state': 'online'},
    )


class Test_load_vehicle_data:
    def test_fills_vehicle_attrs(self, mock_vehicle: Vehicle) -> None:
        battery_range = 123.45
        latitude = 33.111111
        with requests_mock.Mocker() as m:
            m.get(
                f'{HOST}/api/1/vehicles/{VIN}/vehicle_data',
                response_list=[
                    {'json': {'response': {
                        'charge_state': {'battery_range': battery_range},
                        'drive_state': {'latitude': latitude},
                    }}, 'status_code': 200},
                ],
            )

            mock_vehicle.load_vehicle_data()

            assert mock_vehicle.get_charge_state().battery_range == battery_range
            assert mock_vehicle.get_drive_state().latitude == latitude


class Test_command:
    def test_executes(self, mock_vehicle: Vehicle) -> None:
        with requests_mock.Mocker() as m:
            m.post(
                f'{HOST}/api/1/vehicles/{VIN}/command/door_lock',
                response_list=[
                    {'json': {'response': {'result': 'true'}}, 'status_code': 200},
                ],
            )

            mock_vehicle.door_lock()
