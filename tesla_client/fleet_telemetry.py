from kafka import KafkaConsumer  # type: ignore

from tesla_client.vehicle import Vehicle
from tesla_client.vehicle_data_pb2 import (  # type: ignore
    DetailedChargeStateValue,
    Field,
    HvacAutoModeState,
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
        for vehicle in vehicles:
            vehicle.load_vehicle_data(wait_for_wake=True)

        self.vin_to_vehicle = {vehicle.vin: vehicle for vehicle in vehicles}
        self.vehicle_consumer = KafkaConsumer(
            kafka_topic,
            bootstrap_servers=[bootstrap_server],
            group_id=kafka_group_id,
        )

    def listen(self) -> None:
        while True:
            for message in self.vehicle_consumer:
                payload = Payload.FromString(message.value)
                self.handle_vehicle_message(payload)

    def handle_vehicle_message(self, payload: Payload) -> None:
        if payload.vin not in self.vin_to_vehicle:
            return

        vehicle = self.vin_to_vehicle[payload.vin]

        data_dict = {datum.key: datum.value for datum in payload.data}

        cvd = vehicle.get_cached_vehicle_data()

        # ChargeState

        if Field.BatteryLevel in data_dict:
            cvd['charge_state']['battery_level'] = data_dict[Field.BatteryLevel].float_value

        if Field.EstBatteryRange in data_dict:
            cvd['charge_state']['battery_range'] = data_dict[Field.EstBatteryRange].float_value

        if Field.ChargeLimitSoc in data_dict:
            cvd['charge_state']['charge_limit_soc'] = data_dict[Field.ChargeLimitSoc].float_value

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
            cvd['charge_state']['time_to_full_charge'] = data_dict[Field.TimeToFullCharge].float_value

        # ClimateState

        if Field.InsideTemp in data_dict:
            cvd['climate_state']['inside_temp'] = data_dict[Field.InsideTemp].float_value

        if Field.HvacAutoMode in data_dict:
            hvac_auto_mode_state = data_dict[Field.HvacAutoMode].hvac_auto_mode_value
            if hvac_auto_mode_state == HvacAutoModeState.HvacAutoModeOn:
                cvd['climate_state']['is_auto_conditioning_on'] = True
            elif hvac_auto_mode_state == HvacAutoModeState.HvacAutoModeOff:
                cvd['climate_state']['is_auto_conditioning_on'] = False

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
            cvd['climate_state']['outside_temp'] = data_dict[Field.OutsideTemp].float_value

        # DriveState

        if Field.DestinationName in data_dict:
            cvd['drive_state']['active_route_destination'] = data_dict[Field.DestinationName].string_value

        if Field.DestinationLocation in data_dict:
            destination_location: LocationValue = data_dict[Field.DestinationLocation].location_value
            cvd['drive_state']['active_route_latitude'] = destination_location.latitude
            cvd['drive_state']['active_route_longitude'] = destination_location.longitude

        if Field.MinutesToArrival in data_dict:
            cvd['drive_state']['active_route_minutes_to_arrival'] = data_dict[Field.MinutesToArrival].float_value

        if Field.GpsHeading in data_dict:
            cvd['drive_state']['heading'] = data_dict[Field.GpsHeading].float_value

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
            cvd['drive_state']['speed'] = data_dict[Field.VehicleSpeed].float_value

        # VehicleState

        if Field.Locked in data_dict:
            cvd['vehicle_state']['locked'] = data_dict[Field.Locked].boolean_value

        vehicle.set_cached_vehicle_data(cvd)
