from typing import Any
from typing import List
from typing import Optional

import requests
import time


HOST = 'https://owner-api.teslamotors.com'


class AuthenticationError(Exception):
    pass


class VehicleError(Exception):
    def __init__(self, vehicle: 'Vehicle') -> None:
        self.vehicle = vehicle


class VehicleAsleepError(VehicleError):
    pass


class VehicleDidNotWakeError(VehicleError):
    pass


class VehicleNotLoadedError(VehicleError):
    pass


class APIClient():
    def get_access_token(self) -> str:
        raise NotImplementedError

    def api_get(self, endpoint: str) -> dict:
        resp = requests.get(
            HOST + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError

        return resp.json()

    def api_post(self, endpoint: str, json: dict = None) -> dict:
        resp = requests.post(
            HOST + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
            json=json,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError

        return resp.json()


class Account(APIClient):
    def get_vehicles(self) -> List['Vehicle']:
        vehicles_json = self.api_get(
            '/api/1/vehicles'
        )['response']

        return [
            Vehicle(self, vehicle_json)
            for vehicle_json in vehicles_json
        ]


class Vehicle(APIClient):
    def __init__(self, account: Account, vehicle_json: dict) -> None:
        self.account = account
        self.id = vehicle_json['id']
        self.display_name = vehicle_json['display_name']
        self.cached_vehicle_data: Optional[dict] = None

    def get_access_token(self) -> str:
        return self.account.get_access_token()

    def wake_up(self) -> dict:
        return self.api_post(
            '/api/1/vehicles/{}/wake_up'.format(self.id)
        )['response']

    def wait_for_wake_up(
        self,
        retry_interval_seconds: List[int] = [1, 1, 1, 2, 5, 5, 5, 5, 5]
    ) -> dict:
        tries = 0
        for secs in retry_interval_seconds:
            status = self.wake_up()
            if status['state'] == 'online':
                if tries > 0:
                    # if the car wasn't awake already, wait another second
                    time.sleep(1)
                return status
            time.sleep(secs)
            tries += 1
        raise VehicleDidNotWakeError(self)

    def load_vehicle_data(self, wait: bool = True) -> None:
        self.cached_vehicle_data = self.get_vehicle_data()
        if not self.cached_vehicle_data:
            if not wait:
                self.wake_up()
                raise VehicleAsleepError(self)
            self.wait_for_wake_up()
            self.cached_vehicle_data = self.get_vehicle_data()

    def __getattr__(self, name: Any) -> Any:
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)
        return self.cached_vehicle_data[name]

    def get_vehicle_data(self) -> dict:
        return self.api_get(
            '/api/1/vehicles/{}/vehicle_data'.format(self.id)
        )['response']

    def get_nearby_charging_sites(self) -> dict:
        return self.api_get(
            '/api/1/vehicles/{}/nearby_charging_sites'.format(self.id)
        )['response']

    def data_request(self, resource) -> dict:
        return self.api_get(
            '/api/1/vehicles/{}/data_request/{}'.format(self.id, resource)
        )['response']

    def command(self, command, json=None) -> dict:
        return self.api_post(
            '/api/1/vehicles/{}/command/{}'.format(self.id, command),
            json=json,
        )['response']
