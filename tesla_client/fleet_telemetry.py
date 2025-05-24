import copy
import logging
import time
from typing import Any
from kafka import KafkaConsumer  # type: ignore
from tesla_client.vehicle import Vehicle
from tesla_client.vehicle import VehicleDidNotWakeError
from tesla_client.vehicle_data_pb2 import (  # type: ignore
    DetailedChargeStateValue,
    Field,
    HvacPowerState,
    LocationValue,
    Payload,
    ShiftState,
)


class FleetTelemetryListener:
    vin_to_vehicle: dict[str, Vehicle]
    vehicle_consumer: KafkaConsumer

    def __init__(
        self,
        vehicles: list[Vehicle],
        bootstrap_server: str,
        kafka_group_id: str,
        kafka_topic: str = 'tesla_V',
    ) -> None:
        logging.info('Starting ' + self.__class__.__name__)

        for vehicle in vehicles:
            try:
                vehicle.load_vehicle_data()
            except VehicleDidNotWakeError:
                logging.warning(f'At startup, failed to wake and load vehicle {vehicle.vin}')

        self.vin_to_vehicle = {vehicle.vin: vehicle for vehicle in vehicles}
        self.vehicle_consumer = KafkaConsumer(
            kafka_topic,
            bootstrap_servers=[bootstrap_server],
            group_id=kafka_group_id,
        )

    def listen(self) -> None:
        logging.info('Listening for fleet telemetry messages')

        while True:
            for message in self.vehicle_consumer:
                payload = Payload.FromString(message.value)
                try:
                    self.handle_vehicle_message(payload)
                except Exception:
                    logging.exception(f'Error handling vehicle message for vehicle {payload.vin}')

    def handle_vehicle_message(self, payload: Payload) -> None:
        if payload.vin not in self.vin_to_vehicle:
            logging.warning(f'Ignoring vehicle message for unknown vehicle {payload.vin}')
            return

        logging.info(f'Handling vehicle message for vehicle {payload.vin}:\n{payload}')

        vehicle = self.vin_to_vehicle[payload.vin]

        last_load_from_api = vehicle.get_last_load_from_api()
        if not last_load_from_api:
            vehicle.load_vehicle_data()

        data_dict = {datum.key: datum.value for datum in payload.data}

        logging.info(f'data_dict: {data_dict}')

        cvd = vehicle.get_cached_vehicle_data()
        cvd_before = copy.deepcopy(cvd)

        # ChargeState

        if Field.BatteryLevel in data_dict:
            cvd['charge_state']['battery_level'] = data_dict[Field.BatteryLevel].double_value

        if Field.EstBatteryRange in data_dict:
            cvd['charge_state']['battery_range'] = data_dict[Field.EstBatteryRange].double_value

        if Field.ChargeLimitSoc in data_dict:
            cvd['charge_state']['charge_limit_soc'] = data_dict[Field.ChargeLimitSoc].int_value

        if Field.DetailedChargeState in data_dict and data_dict[Field.DetailedChargeState]:
            charge_state = data_dict[Field.DetailedChargeState].detailed_charge_state_value
            match charge_state:
                case DetailedChargeStateValue.DetailedChargeStateUnknown:
                    cvd['charge_state']['charging_state'] = 'Unknown'
                case DetailedChargeStateValue.DetailedChargeStateDisconnected:
                    cvd['charge_state']['charging_state'] = 'Disconnected'
                case DetailedChargeStateValue.DetailedChargeStateNoPower:
                    cvd['charge_state']['charging_state'] = 'NoPower'
                case DetailedChargeStateValue.DetailedChargeStateStarting:
                    cvd['charge_state']['charging_state'] = 'Starting'
                case DetailedChargeStateValue.DetailedChargeStateCharging:
                    cvd['charge_state']['charging_state'] = 'Charging'
                case DetailedChargeStateValue.DetailedChargeStateComplete:
                    cvd['charge_state']['charging_state'] = 'Complete'
                case DetailedChargeStateValue.DetailedChargeStateStopped:
                    cvd['charge_state']['charging_state'] = 'Stopped'

        if Field.FastChargerPresent in data_dict:
            cvd['charge_state']['fast_charger_present'] = data_dict[Field.FastChargerPresent].boolean_value

        if Field.TimeToFullCharge in data_dict:
            cvd['charge_state']['time_to_full_charge'] = data_dict[Field.TimeToFullCharge].double_value

        # ClimateState

        if Field.InsideTemp in data_dict:
            cvd['climate_state']['inside_temp'] = data_dict[Field.InsideTemp].double_value

        if Field.HvacPower in data_dict:
            hvac_power_state = data_dict[Field.HvacPower].hvac_power_value
            if hvac_power_state == HvacPowerState.HvacPowerStateOn:
                cvd['climate_state']['is_climate_on'] = True
            elif hvac_power_state == HvacPowerState.HvacPowerStateOff:
                cvd['climate_state']['is_climate_on'] = False
            elif hvac_power_state == HvacPowerState.HvacPowerStatePrecondition:
                cvd['climate_state']['is_climate_on'] = False
            elif hvac_power_state == HvacPowerState.HvacPowerStateOverheatProtect:
                cvd['climate_state']['is_climate_on'] = True

        if Field.OutsideTemp in data_dict:
            cvd['climate_state']['outside_temp'] = data_dict[Field.OutsideTemp].double_value

        # DriveState

        if Field.DestinationName in data_dict:
            cvd['drive_state']['active_route_destination'] = data_dict[Field.DestinationName].string_value

        if Field.DestinationLocation in data_dict:
            destination_location: LocationValue = data_dict[Field.DestinationLocation].location_value
            cvd['drive_state']['active_route_latitude'] = destination_location.latitude
            cvd['drive_state']['active_route_longitude'] = destination_location.longitude

        if Field.MinutesToArrival in data_dict:
            cvd['drive_state']['active_route_minutes_to_arrival'] = data_dict[Field.MinutesToArrival].double_value

        if Field.GpsHeading in data_dict:
            cvd['drive_state']['heading'] = data_dict[Field.GpsHeading].double_value

        if Field.Location in data_dict and data_dict[Field.Location]:
            location: LocationValue = data_dict[Field.Location].location_value
            cvd['drive_state']['latitude'] = location.latitude
            cvd['drive_state']['longitude'] = location.longitude

        if Field.Gear in data_dict:
            shift_state = data_dict[Field.Gear].shift_state_value
            if shift_state == ShiftState.ShiftStateP:
                cvd['drive_state']['shift_state'] = 'P'
            elif shift_state == ShiftState.ShiftStateR:
                cvd['drive_state']['shift_state'] = 'R'
            elif shift_state == ShiftState.ShiftStateN:
                cvd['drive_state']['shift_state'] = 'N'
            elif shift_state == ShiftState.ShiftStateD:
                cvd['drive_state']['shift_state'] = 'D'
            elif shift_state == ShiftState.ShiftStateSNA:
                cvd['drive_state']['shift_state'] = 'SNA'
            elif shift_state == ShiftState.ShiftStateUnknown:
                cvd['drive_state']['shift_state'] = 'Unknown'
            elif shift_state == ShiftState.ShiftStateInvalid:
                cvd['drive_state']['shift_state'] = 'Invalid'

        if Field.VehicleSpeed in data_dict:
            cvd['drive_state']['speed'] = data_dict[Field.VehicleSpeed].double_value

        # VehicleState

        if Field.Locked in data_dict:
            cvd['vehicle_state']['locked'] = data_dict[Field.Locked].boolean_value

        cvd['last_update'] = int(time.time())

        vehicle.set_cached_vehicle_data(cvd)

        for k1, v1 in cvd.items():
            if isinstance(v1, dict):
                for k2, v2 in v1.items():
                    try:
                        assert cvd_before[k1][k2] == v2
                    except KeyError:
                        try:
                            self.notify_vehicle_data_changed(payload.vin, k1, k2, None, v2)
                        except Exception:
                            logging.exception('Exception while notifying vehicle data change')
                    except AssertionError:
                        try:
                            self.notify_vehicle_data_changed(payload.vin, k1, k2, cvd_before[k1][k2], v2)
                        except Exception:
                            logging.exception('Exception while notifying vehicle data change')

    def notify_vehicle_data_changed(self, vin: str, k1: str, k2: str, value_before: Any, value_after: Any) -> None:
        logging.info(f'Vehicle {vin} data changed: {k1}.{k2}: {value_before} → {value_after}')
