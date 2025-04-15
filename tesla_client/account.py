from typing import Any

from .client import APIClient
from .client import HOST
from .vehicle import Vehicle
from .vehicle import VehicleNotFoundError


class Account:
    DOC_WHITELIST = [
        'get_vehicles',
        'get_vehicle_by_vin',
    ]

    DEFAULT_FLEET_TELEMETRY_FIELDS = {
        'BatteryLevel': {'interval_seconds': 1, 'minimum_delta': 5},
        'ChargeLimitSoc': {'interval_seconds': 1},
        'DestinationLocation': {'interval_seconds': 1},
        'DestinationName': {'interval_seconds': 1},
        'DetailedChargeState': {'interval_seconds': 1},
        'EstBatteryRange': {'interval_seconds': 1, 'minimum_delta': 5},
        'FastChargerPresent': {'interval_seconds': 1},
        'Gear': {'interval_seconds': 1},
        'GpsHeading': {'interval_seconds': 1},
        'HvacAutoMode': {'interval_seconds': 1},
        'HvacPower': {'interval_seconds': 1},
        'InsideTemp': {'interval_seconds': 1, 'minimum_delta': 5},
        'LocatedAtFavorite': {'interval_seconds': 1},
        'LocatedAtHome': {'interval_seconds': 1},
        'Location': {'interval_seconds': 1, 'minimum_delta': 1000},
        'Locked': {'interval_seconds': 1},
        'MinutesToArrival': {'interval_seconds': 1, 'minimum_delta': 5},
        'OutsideTemp': {'interval_seconds': 1, 'minimum_delta': 5},
        'TimeToFullCharge': {'interval_seconds': 1, 'minimum_delta': 5},
        'VehicleSpeed': {'interval_seconds': 1, 'minimum_delta': 5},
    }

    client: APIClient
    wait_for_wake: bool
    vehicle_cls: type[Vehicle] = Vehicle

    def __init__(self, access_token: str, api_host: str = HOST, wait_for_wake: bool = True) -> None:
        self.client = APIClient(access_token, api_host)
        self.wait_for_wake = wait_for_wake

    def get_vehicles(self) -> list[Vehicle]:
        vehicles_json = self.client.api_get(
            '/api/1/vehicles'
        )['response']

        return [
            self.vehicle_cls(self.client, vehicle_json, self.wait_for_wake)
            for vehicle_json in vehicles_json
        ]

    def get_vehicle_by_vin(self, vin: str) -> Vehicle:
        vin_to_vehicle = {v.vin: v for v in self.get_vehicles()}
        vehicle = vin_to_vehicle.get(vin)
        if not vehicle:
            raise VehicleNotFoundError
        return vehicle

    def register_vin_for_fleet_telemetry(
        self,
        hostname: str,
        port: int,
        certificate: str,
        vin: str,
        fields: dict[str, Any] = DEFAULT_FLEET_TELEMETRY_FIELDS,
    ) -> None:
        self.client.api_post(
            'api/1/vehicles/fleet_telemetry_config',
            json={
                'config': {
                    'prefer_typed': True,
                    'hostname': hostname,
                    'port': port,
                    'ca': certificate,
                    'vins': [vin],
                    'fields': fields,
                    'alert_types': ['service'],
                }
            }
        )
