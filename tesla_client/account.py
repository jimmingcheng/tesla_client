from abc import ABC
from abc import abstractmethod

from .client import APIClient
from .client import HOST
from .vehicle import Vehicle
from .vehicle import VehicleNotFoundError


class Account(ABC):
    client: APIClient
    vehicle_cls: type[Vehicle] = Vehicle

    def __init__(self, api_host: str = HOST) -> None:
        self.client = APIClient(self, api_host)

    @abstractmethod
    def get_fresh_access_token(self) -> str:
        pass

    def get_vehicles(self) -> list[Vehicle]:
        vehicles_json = self.client.api_get(
            '/api/1/vehicles'
        ).json()['response']

        return [
            self.vehicle_cls(self, vehicle_json)
            for vehicle_json in vehicles_json
        ]

    def get_vehicle_by_vin(self, vin: str) -> Vehicle:
        vin_to_vehicle = {v.vin: v for v in self.get_vehicles()}
        vehicle = vin_to_vehicle.get(vin)
        if not vehicle:
            raise VehicleNotFoundError
        return vehicle
