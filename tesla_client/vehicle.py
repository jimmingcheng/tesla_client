from __future__ import annotations
from typing import Any
from typing import TYPE_CHECKING

import random
import time
from dataclasses import dataclass

import requests

from .client import HOST
from .client import VehicleAsleepError


if TYPE_CHECKING:
    from .account import Account


DEFAULT_FLEET_TELEMETRY_FIELDS = {
    'BatteryLevel': {'interval_seconds': 60, 'minimum_delta': 1.0},
    'ChargeLimitSoc': {'interval_seconds': 60, 'minimum_delta': 1.0},
    'DestinationLocation': {'interval_seconds': 1},
    'DestinationName': {'interval_seconds': 1},
    'DetailedChargeState': {'interval_seconds': 1},
    'EstBatteryRange': {'interval_seconds': 60, 'minimum_delta': 1.0},
    'FastChargerPresent': {'interval_seconds': 1},
    'Gear': {'interval_seconds': 1},
    'GpsHeading': {'interval_seconds': 60},
    'HvacAutoMode': {'interval_seconds': 1},
    'HvacPower': {'interval_seconds': 1},
    'InsideTemp': {'interval_seconds': 60, 'minimum_delta': 1.0},
    'LocatedAtFavorite': {'interval_seconds': 1},
    'LocatedAtHome': {'interval_seconds': 1},
    'Location': {'interval_seconds': 60, 'minimum_delta': 100},
    'Locked': {'interval_seconds': 1},
    'MinutesToArrival': {'interval_seconds': 60},
    'OutsideTemp': {'interval_seconds': 60, 'minimum_delta': 1.0},
    'TimeToFullCharge': {'interval_seconds': 60},
    'VehicleSpeed': {'interval_seconds': 60},
}


class VehicleNotFoundError(Exception):
    pass


class VehicleDidNotWakeError(Exception):
    pass


class VehicleNotLoadedError(Exception):
    pass


@dataclass
class FleetTelemetryStatus:
    virtual_key_required: bool
    virtual_key_added: bool
    fleet_telemetry_paired: bool


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
    account: 'Account'
    vin: str
    display_name: str
    online_as_of: int | None
    _fleet_telemetry_status: FleetTelemetryStatus | None = None
    _cached_vehicle_data: dict

    def __init__(
        self,
        account: 'Account',
        vehicle_json: dict,
    ) -> None:
        self.account = account
        self.vin = vehicle_json['vin']
        self.display_name = vehicle_json['display_name']
        self.online_as_of = int(time.time()) if vehicle_json['state'] == 'online' else None
        self._fleet_telemetry_status = None
        self._cached_vehicle_data: dict = {}

    def wake_up(self) -> None:
        for attempt in range(3):
            # jitter to prevent burst of wakeup requests
            time.sleep(random.uniform(2, 10))

            try:
                status = self.account.client.api_post(
                    '/api/1/vehicles/{}/wake_up'.format(self.vin)
                ).json()['response']
            except requests.HTTPError:
                raise VehicleDidNotWakeError
            if status and status['state'] == 'online':
                return

        raise VehicleDidNotWakeError

    def is_using_fleet_telemetry(self) -> bool:
        return self.get_fleet_telemetry_status().fleet_telemetry_paired

    def get_fleet_telemetry_status(self) -> FleetTelemetryStatus:
        if not self._fleet_telemetry_status:
            self.refresh_fleet_telemetry_status()

        assert self._fleet_telemetry_status is not None

        return self._fleet_telemetry_status

    def set_fleet_telemetry_status(self, fleet_telemetry_status: FleetTelemetryStatus) -> None:
        self._fleet_telemetry_status = fleet_telemetry_status

    def refresh_fleet_telemetry_status(self) -> None:
        fleet_status = self.account.client.api_post(
            '/api/1/vehicles/fleet_status',
            json={'vins': [self.vin]}
        ).json()['response']

        import logging
        logging.info(fleet_status)

        virtual_key_required = fleet_status['vehicle_info'][self.vin]['vehicle_command_protocol_required']
        virtual_key_added = bool(self.vin in fleet_status['key_paired_vins'])

        fleet_config = self.account.client.api_get(
            f'/api/1/vehicles/{self.vin}/fleet_telemetry_config',
        ).json()['response']

        self.set_fleet_telemetry_status(
            FleetTelemetryStatus(
                virtual_key_required=virtual_key_required,
                virtual_key_added=virtual_key_added,
                fleet_telemetry_paired=bool(fleet_config['config']),
            )
        )

    def pair_fleet_telemetry(self) -> None:
        raise NotImplementedError(
            'Implement this method to call _pair_fleet_telemetry with desired parameters.'
        )

    def _pair_fleet_telemetry(
        self,
        hostname: str,
        port: int,
        certificate: str,
        fields: dict[str, Any] = DEFAULT_FLEET_TELEMETRY_FIELDS,
    ) -> None:
        self.account.client.api_post(
            '/api/1/vehicles/fleet_telemetry_config',
            json={
                'config': {
                    'prefer_typed': True,
                    'hostname': hostname,
                    'port': port,
                    'ca': certificate,
                    'fields': fields,
                    'alert_types': ['service'],
                },
                'vins': [self.vin],
            }
        )
        self.refresh_fleet_telemetry_status()

    def unpair_fleet_telemetry(self) -> None:
        self.account.client.api_delete(f'/api/1/vehicles/{self.vin}/fleet_telemetry_config')
        self.refresh_fleet_telemetry_status()

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
            vehicle_data_from_api = self.account.client.api_get(
                f'/api/1/vehicles/{self.vin}/vehicle_data?endpoints={VEHICLE_DATA_ENDPOINTS_QS}',
            ).json()['response']
        except VehicleAsleepError:
            if not should_wake:
                raise

            self.wake_up()
            vehicle_data_from_api = self.account.client.api_get(
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
                    raise VehicleDidNotWakeError

        return data

    def get_vehicle_name(self) -> str:
        return self.get_vehicle_state().vehicle_name

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
            self.account.client.api_post(
                '/api/1/vehicles/{}/command/{}'.format(self.vin, command),
                json=json,
            )
        except VehicleAsleepError:
            self.wake_up()
            self.account.client.api_post(
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
        self.account.client.api_post(
            '/api/1/vehicles/{}/command/navigation_request'.format(self.vin),
            json={
                'type': 'share_ext_content_raw',
                'locale': 'en-US',
                'timestamp_ms': int(time.time() * 1000),
                'value': {
                    'android.intent.extra.TEXT': location_and_address,
                },
            },
            host_override=HOST,
        )

    def set_charge_limit(self, percent: int) -> None:
        self._command('set_charge_limit', json={'percent': percent})
