from typing import Any
from typing import List
from typing import Optional

import requests
import time
from abc import ABCMeta
from abc import abstractmethod


HOST = 'https://fleet-api.prd.na.vn.cloud.tesla.com'
VEHICLE_DATA_ENDPOINTS_QS = '%3B'.join([
    'charge_state',
    'climate_state',
    'closures_state',
    'drive_state',
    'gui_settings',
    'location_data',
    'vehicle_config',
    'vehicle_state',
    'vehicle_data_combo',
])


class AuthenticationError(Exception):
    pass


class VehicleNotFoundError(Exception):
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


class APIClient(metaclass=ABCMeta):
    def __init__(self, api_host: str = HOST) -> None:
        self.api_host = api_host

    @abstractmethod
    def get_access_token(self) -> str:
        pass

    def api_get(self, endpoint: str) -> dict:
        resp = requests.get(
            self.api_host + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
            verify=False,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError

        return resp.json()

    def api_post(self, endpoint: str, json: Optional[dict] = None) -> dict:
        resp = requests.post(
            self.api_host + endpoint,
            headers={
                'Authorization': 'Bearer ' + self.get_access_token(),
                'Content-type': 'application/json',
            },
            json=json,
            verify=False,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise AuthenticationError

        return resp.json()


class Account(APIClient):
    def __init__(self, api_host: str = HOST, wait_for_wake: bool = True) -> None:
        super().__init__(api_host)
        self.wait_for_wake = wait_for_wake

    def get_vehicles(self) -> List['Vehicle']:
        vehicles_json = self.api_get(
            '/api/1/vehicles'
        )['response']

        return [
            Vehicle(self, vehicle_json, self.api_host, self.wait_for_wake)
            for vehicle_json in vehicles_json
        ]

    def get_vehicle_by_id(self, vehicle_id: str) -> 'Vehicle':
        id_to_vehicle = {v.id: v for v in self.get_vehicles()}
        vehicle = id_to_vehicle.get(vehicle_id)
        if not vehicle:
            raise VehicleNotFoundError
        return vehicle


class Vehicle(APIClient):
    def __init__(
        self,
        account: Account,
        vehicle_json: dict,
        api_host: str = HOST,
        wait_for_wake: bool = True,
    ) -> None:
        super().__init__(api_host)

        self.account = account
        self.id = vehicle_json['id']
        self.display_name = vehicle_json['display_name']
        self.wait_for_wake = wait_for_wake
        self.cached_vehicle_data: Optional[dict] = None

    def get_access_token(self) -> str:
        return self.account.get_access_token()

    def api_get(
        self,
        endpoint: str,
        wait_for_wake: Optional[bool] = None
    ) -> dict:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        resp_json = super().api_get(endpoint)

        if resp_json and resp_json.get('response'):
            return resp_json
        elif wait_for_wake:
            self.wake_up(wait_for_wake)
            return super().api_get(endpoint)
        else:
            self.wake_up(wait_for_wake)
            raise VehicleAsleepError(self)

    def api_post(
        self,
        endpoint: str,
        json: Optional[dict] = None,
        wait_for_wake: Optional[bool] = None
    ) -> dict:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        resp_json = super().api_post(endpoint, json)
        if resp_json and resp_json.get('response'):
            return resp_json
        elif wait_for_wake:
            self.wake_up(wait_for_wake)
            return super().api_post(endpoint, json)
        else:
            self.wake_up(wait_for_wake)
            raise VehicleAsleepError(self)

    def wake_up(self, wait_for_wake: Optional[bool] = None) -> dict:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        if wait_for_wake:
            return self._wait_for_wake_up()
        else:
            return self._wake_up()

    def _wake_up(self) -> dict:
        return super().api_post(
            '/api/1/vehicles/{}/wake_up'.format(self.id)
        )['response']

    def _wait_for_wake_up(
        self,
        retry_interval_seconds: List[int] = [1, 1, 1, 2, 5, 5, 5, 5, 5]
    ) -> dict:
        tries = 0
        for secs in retry_interval_seconds:
            status = self._wake_up()
            if status['state'] == 'online':
                if tries > 0:
                    # if the car wasn't awake already, wait another second
                    time.sleep(1)
                return status
            time.sleep(secs)
            tries += 1
        raise VehicleDidNotWakeError(self)

    def is_awake(self) -> bool:
        try:
            self.get_vehicle_data(
                wait_for_wake=False,
                do_not_wake=True,
            )
            return True
        except VehicleAsleepError:
            return False

    def load_vehicle_data(self, wait_for_wake: Optional[bool] = None, do_not_wake: bool = False) -> None:
        self.cached_vehicle_data = self.get_vehicle_data(
            wait_for_wake=wait_for_wake,
            do_not_wake=do_not_wake,
        )

    def __getattr__(self, name: Any) -> Any:
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)
        return self.cached_vehicle_data[name]

    def get_vehicle_data(self, wait_for_wake: Optional[bool] = None, do_not_wake: bool = False) -> dict:
        if do_not_wake:
            resp_json = super().api_get(
                f'/api/1/vehicles/{self.id}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}'
            )['response']
            if not resp_json:
                raise VehicleAsleepError(self)
            return resp_json
        else:
            return self.api_get(
                f'/api/1/vehicles/{self.id}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}',
                wait_for_wake=wait_for_wake
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
