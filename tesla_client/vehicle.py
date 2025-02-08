from dataclasses import dataclass

import time

from .client import APIClient
from .client import HOST


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


@dataclass
class ChargeState:
    """
    - time_to_full_charge is in hours
    - battery_range is in miles
    """
    battery_level: float
    battery_range: float
    charge_limit_soc: float
    charging_state: str
    fast_charger_present: bool
    minutes_to_full_charge: float | None
    time_to_full_charge: float | None


@dataclass
class ClimateState:
    """
    - temperatures are in Fahrenheit
    """
    inside_temp: float
    is_auto_conditioning_on: bool
    is_climate_on: bool
    outside_temp: float


@dataclass
class DriveState:
    """
    - heading is in degrees
    - speed is in mph
    """
    active_route_destination: str
    active_route_latitude: float
    active_route_longitude: float
    active_route_minutes_to_arrival: float
    heading: float
    latitude: float
    longitude: float
    shift_state: str | None
    speed: float | None


@dataclass
class VehicleState:
    locked: bool
    vehicle_name: str


class Vehicle(APIClient):
    DOC_WHITELIST = [
        'vin',
        'display_name',
        'auto_conditioning_start',
        'auto_conditioning_stop',
        'charge_start',
        'charge_stop',
        'door_lock',
        'door_unlock',
        'flash_lights',
        'honk_horn',
        'navigation_request',
        'set_charge_limit',
    ]

    client: APIClient
    vin: str
    display_name: str
    wait_for_wake: bool
    cached_vehicle_data: dict | None

    def __init__(
        self,
        client: APIClient,
        vehicle_json: dict,
        wait_for_wake: bool = True,
    ) -> None:
        self.client = client
        self.vin = vehicle_json['vin']
        self.display_name = vehicle_json['display_name']
        self.wait_for_wake = wait_for_wake
        self.cached_vehicle_data: dict | None = None

    def _api_get(
        self,
        endpoint: str,
        wait_for_wake: bool | None = None
    ) -> dict:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        resp_json = self.client.api_get(endpoint)

        if resp_json and resp_json.get('response'):
            return resp_json
        elif wait_for_wake:
            self.wake_up(wait_for_wake)
            return self.client.api_get(endpoint)
        else:
            self.wake_up(wait_for_wake)
            raise VehicleAsleepError(self)

    def _api_post(
        self,
        endpoint: str,
        json: dict | None = None,
        wait_for_wake: bool | None = None
    ) -> dict:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        resp_json = self.client.api_post(endpoint, json)
        if resp_json and resp_json.get('response'):
            return resp_json
        elif wait_for_wake:
            self.wake_up(wait_for_wake)
            return self.client.api_post(endpoint, json)
        else:
            self.wake_up(wait_for_wake)
            raise VehicleAsleepError(self)

    def wake_up(self, wait_for_wake: bool | None = None) -> None:
        wait_for_wake = wait_for_wake if wait_for_wake is not None else self.wait_for_wake

        if wait_for_wake:
            self._wait_for_wake_up()
        else:
            self._wake_up()

    def _wake_up(self) -> dict | None:
        return self.client.api_post(
            '/api/1/vehicles/{}/wake_up'.format(self.vin)
        )['response']

    def _wait_for_wake_up(
        self,
        retry_interval_seconds: list[int] = [1, 1, 1, 2, 5, 5, 5, 5, 5, 10, 10, 10, 20, 20]
    ) -> None:
        tries = 0
        for secs in retry_interval_seconds:
            status = self._wake_up()
            if status and status['state'] == 'online':
                if tries > 0:
                    # if the car wasn't awake already, wait another second
                    time.sleep(1)
                return
            time.sleep(secs)
            tries += 1
        raise VehicleDidNotWakeError(self)

    def is_awake(self) -> bool:
        try:
            self._get_vehicle_data(
                wait_for_wake=False,
                do_not_wake=True,
            )
            return True
        except VehicleAsleepError:
            return False

    def load_vehicle_data(self, wait_for_wake: bool | None = None, do_not_wake: bool = False) -> None:
        self.cached_vehicle_data = self._get_vehicle_data(
            wait_for_wake=wait_for_wake,
            do_not_wake=do_not_wake,
        )

    def get_charge_state(self) -> ChargeState:
        if not self.cached_vehicle_data:
            self.load_vehicle_data(wait_for_wake=True)
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)

        charge_state_dict = self.cached_vehicle_data['charge_state']
        return ChargeState(**{
            k: charge_state_dict.get(k)
            for k in ChargeState.__annotations__
        })

    def get_climate_state(self) -> ClimateState:
        if not self.cached_vehicle_data:
            self.load_vehicle_data(wait_for_wake=True)
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)

        climate_state_dict = self.cached_vehicle_data['climate_state']
        return ClimateState(**{
            k: climate_state_dict.get(k)
            for k in ClimateState.__annotations__
        })

    def get_drive_state(self) -> DriveState:
        if not self.cached_vehicle_data:
            self.load_vehicle_data(wait_for_wake=True)
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)

        drive_state_dict = self.cached_vehicle_data['drive_state']
        return DriveState(**{
            k: drive_state_dict.get(k)
            for k in DriveState.__annotations__
        })

    def get_vehicle_state(self) -> VehicleState:
        if not self.cached_vehicle_data:
            self.load_vehicle_data(wait_for_wake=True)
        if not self.cached_vehicle_data:
            raise VehicleNotLoadedError(self)

        vehicle_state_dict = self.cached_vehicle_data['vehicle_state']
        return VehicleState(**{
            k: vehicle_state_dict.get(k)
            for k in VehicleState.__annotations__
        })

    def _get_vehicle_data(self, wait_for_wake: bool | None = None, do_not_wake: bool = False) -> dict:
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

        if do_not_wake:
            resp_json = self.client.api_get(
                f'/api/1/vehicles/{self.vin}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}'
            )['response']
            if not resp_json:
                raise VehicleAsleepError(self)
            return resp_json
        else:
            return self._api_get(
                f'/api/1/vehicles/{self.vin}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}',
                wait_for_wake=wait_for_wake
            )['response']

    def _command(self, command, json: dict | None = None) -> None:
        self._api_post(
            '/api/1/vehicles/{}/command/{}'.format(self.vin, command),
            json=json,
        )

    def auto_conditioning_start(self) -> None:
        self._command('auto_conditioning_start')

    def auto_conditioning_stop(self) -> None:
        self._command('auto_conditioning_stop')

    def charge_start(self) -> None:
        self._command('charge_start')

    def charge_stop(self) -> None:
        self._command('charge_stop')

    def door_lock(self) -> None:
        self._command('door_lock')

    def door_unlock(self) -> None:
        self._command('door_unlock')

    def flash_lights(self) -> None:
        self._command('flash_lights')

    def honk_horn(self) -> None:
        self._command('honk_horn')

    def navigation_request(self, location_and_address: str) -> None:
        # navigation requests are special and should go directly to the API HOST instead of being
        # routed through the vcmd proxy
        APIClient(self.client.access_token, HOST).api_post(
            '/api/1/vehicles/{}/command/navigation_request'.format(self.vin),
            json={
                'type': 'share_ext_content_raw',
                'locale': 'en-US',
                'timestamp_ms': int(time.time() * 1000),
                'value': {
                    'android.intent.extra.TEXT': location_and_address,
                },
            },
        )

    def set_charge_limit(self, percent: int) -> None:
        self._command('set_charge_limit', json={'percent': percent})
