from .client import APIClient
from .client import HOST
from .vehicle import Vehicle
from .vehicle import VehicleNotFoundError


class Account:
    DOC_WHITELIST = [
        'get_vehicles',
        'get_vehicle_by_vin',
    ]

    client: APIClient
    wait_for_wake: bool

    def __init__(self, access_token: str, api_host: str = HOST, wait_for_wake: bool = True) -> None:
        self.client = APIClient(access_token, api_host)
        self.wait_for_wake = wait_for_wake

    def get_vehicles(self) -> list[Vehicle]:
        vehicles_json = self.client.api_get(
            '/api/1/vehicles'
        )['response']

        return [
            Vehicle(self.client, vehicle_json, self.wait_for_wake)
            for vehicle_json in vehicles_json
        ]

    def get_vehicle_by_vin(self, vin: str) -> Vehicle:
        vin_to_vehicle = {v.vin: v for v in self.get_vehicles()}
        vehicle = vin_to_vehicle.get(vin)
        if not vehicle:
            raise VehicleNotFoundError
        return vehicle
