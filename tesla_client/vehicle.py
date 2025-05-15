from dataclasses import dataclass

import random
import time

from .client import APIClient
from .client import HOST
from .client import VehicleAsleepError


LEGACY_FLEET_TELEMETRY_VERSION = 'unknown'


class VehicleNotFoundError(Exception):
    pass


class VehicleDidNotWakeError(Exception):
    pass


class VehicleNotLoadedError(Exception):
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
    time_to_full_charge: float | None


@dataclass
class ClimateState:
    """
    - temperatures are in Fahrenheit
    """
    inside_temp: float
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


class Vehicle:
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
    online_as_of: int | None
    _fleet_telemetry_version: str | None
    _cached_vehicle_data: dict

    def __init__(
        self,
        client: APIClient,
        vehicle_json: dict,
    ) -> None:
        self.client = client
        self.vin = vehicle_json['vin']
        self.display_name = vehicle_json['display_name']
        self.online_as_of = int(time.time()) if vehicle_json['state'] == 'online' else None
        self._fleet_telemetry_version = None
        self._cached_vehicle_data: dict = {}

    def wake_up(self) -> None:
        for attempt in range(3):
            # jitter to prevent burst of wakeup requests
            time.sleep(random.uniform(2, 10))

            status = self.client.api_post(
                '/api/1/vehicles/{}/wake_up'.format(self.vin)
            ).json()['response']
            if status and status['state'] == 'online':
                return

        raise VehicleDidNotWakeError

    def supports_fleet_telemetry(self) -> bool:
        return self.get_fleet_telemetry_version() != LEGACY_FLEET_TELEMETRY_VERSION

    def get_fleet_telemetry_version(self) -> str:
        if self._fleet_telemetry_version is None:
            self._fleet_telemetry_version = self.fetch_fleet_telemetry_version()
        return self._fleet_telemetry_version

    def fetch_fleet_telemetry_version(self) -> str:
        resp_json = self.client.api_post(
            '/api/1/vehicles/fleet_status',
            json={'vins': [self.vin]}
        ).json()
        return resp_json['response']['vehicle_info'][self.vin]['fleet_telemetry_version']

    def get_cached_vehicle_data(self) -> dict:
        return self._cached_vehicle_data

    def set_cached_vehicle_data(self, vehicle_data: dict) -> None:
        self._cached_vehicle_data = vehicle_data

    def load_vehicle_data(self, should_wake: bool = True) -> None:
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

        try:
            vehicle_data_from_api = self.client.api_get(
                f'/api/1/vehicles/{self.vin}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}',
            ).json()['response']
        except VehicleAsleepError:
            if not should_wake:
                raise

            self.wake_up()
            vehicle_data_from_api = self.client.api_get(
                f'/api/1/vehicles/{self.vin}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}',
            ).json()['response']

        now = int(time.time())
        vehicle_data_from_api['last_update'] = now
        vehicle_data_from_api['last_load_from_api'] = now

        self.set_cached_vehicle_data(vehicle_data_from_api)

    def get_last_update(self) -> int | None:
        return self.get_cached_vehicle_data().get('last_update', None)

    def get_last_load_from_api(self) -> int | None:
        return self.get_cached_vehicle_data().get('last_load_from_api', None)

    def _get_data_for_state(self, state_key: str, state_class: type) -> type:
        cvd = self.get_cached_vehicle_data()

        for attempt in range(3):
            try:
                data = state_class(**{  # type: ignore
                    k: cvd[state_key].get(k)
                    for k in state_class.__annotations__
                })
            except KeyError:
                if attempt < 2:
                    self.load_vehicle_data()
                else:
                    raise VehicleNotLoadedError

        return data

    def get_charge_state(self) -> ChargeState:
        return self._get_data_for_state('charge_state', ChargeState)  # type: ignore

    def get_climate_state(self) -> ClimateState:
        return self._get_data_for_state('climate_state', ClimateState)  # type: ignore

    def get_drive_state(self) -> DriveState:
        return self._get_data_for_state('drive_state', DriveState)  # type: ignore

    def get_vehicle_state(self) -> VehicleState:
        return self._get_data_for_state('vehicle_state', VehicleState)  # type: ignore

    def _command(self, command, json: dict | None = None) -> None:
        try:
            self.client.api_post(
                '/api/1/vehicles/{}/command/{}'.format(self.vin, command),
                json=json,
            )
        except VehicleAsleepError:
            self.wake_up()
            self.client.api_post(
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
