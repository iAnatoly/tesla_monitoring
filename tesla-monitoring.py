#!/usr/bin/env python3
import asyncio
import json
import time
from datetime import datetime

# vendors
import teslapy
from twilio.rest import Client as TwilioClient


class VehicleOfflineException(Exception):
    pass

class NoScheduleException(Exception):
    pass

class NoLocationException(Exception):
    pass

class VehicleNotFoundException(Exception):
    pass

class AlertManager:
    def __init__(self, params):
        self.alerting_providers = []
        for alert_config in params:
            if alert_config["kind"] == 'TwilioAlertProvider':
                self.alerting_providers.append(TwilioAlertProvider(alert_config))
            elif alert_config["kind"] == "ConsoleAlertProvider":
                self.alerting_providers.append(ConsoleAlertProvider(alert_config))
            elif alert_config["kind"] == "TelegramAlertProvider":
                self.alerting_providers.append(TelegramAlertProvider(alert_config))
            else:
                print('Warning: unknown alerting provider: ', alert_config["kind"])

    def alert(self,message):
        for provider in self.alerting_providers:
            provider.alert(message)

    def info(self, message):
        for provider in self.alerting_providers:
            provider.info(message)

class AlertProvider:
    def info(self, message):
        pass
    def alert(self, message):
        pass
    def __init__(self, params):
        self.params = params

class ConsoleAlertProvider(AlertProvider):
    def info(self, message):
        print('{} INFO: {}'.format(datetime.now().isoformat(), message))

    def alert(self,message):
        print('{} ALERT: {}'.format(datetime.now().isoformat(), message))

class TwilioAlertProvider(AlertProvider):
    def alert(self, message):
        client = TwilioClient(self.params["account_sid"], self.params["auth_token"])

        message = client.messages.create(
            body=message,
            from_=self.params["from"],
            to=self.params["to"]
        )

class TelegramAlertProvider(AlertProvider):
    def info(self, message):
        raise NotImplementedError()

    def alert(self,message):
        raise NotImplementedError()

class ScheduleManager:
    def __init__(self, locations, alert_mgr):
        self.locations = locations
        self.alert_mgr = alert_mgr

    def _is_applicable(self, timeslot, now):
        (start_hour, start_min) = [ int(s) for s in timeslot["start"].split(':') ]
        (end_hour, end_min) = [ int (s) for s in timeslot["end"].split(':') ]
        start_time = now.replace(hour=start_hour, minute=start_min)
        end_time = now.replace(hour=end_hour, minute=end_min)
        return start_time<now and end_time>now

    def filter_schedules_by_timeslot(self):
        now = datetime.now()
        self.applicable_schedules = []
        
        for location in self.locations:
            for timeslot in location["schedule"]:
                if self._is_applicable(timeslot, now):
                    # enriching schedule with coordinates to flatten the data structure
                    timeslot["coordinates"] = location["coordinates"]
                    timeslot["name"] = location["name"]
                    self.applicable_schedules.append(timeslot)
        return len(self.applicable_schedules)>0

    def can_wake_up(self):
        return any( schedule["wake_up"] for schedule in self.applicable_schedules )

    
    def filter_schedules_by_location(self, latitude, longitude):
        self.filtered_schedules = []
        precision = 0.00005
        for loc in self.applicable_schedules:
            lat = loc["coordinates"]["latitude"]
            lon = loc["coordinates"]["longitude"]

            print(lat, latitude, lon, longitude)

            if (abs(lat-latitude) < precision and abs(lon-longitude) < precision):
                self.filtered_schedules.append(loc)

        return len(self.filtered_schedules)>0

    def validate_state(self, state):
        for schedule in self.filtered_schedules:
            if state in schedule['valid_states']:
                self.alert_mgr.info('state "{}" is valid : {}'.format(state,schedule['valid_states']))
            else:
                self.alert_mgr.alert('Vehicle state "{}" is invalid at location "{}" for schedule {}-{}'.format(state,schedule["name"],schedule["start"], schedule["end"]))
        return False

    def validate_current(self, current):
        for schedule in self.filtered_schedules:
            if "min_current" in schedule and current < int(schedule["min_current"]):
                self.alert_mgr.alert('Requestedd current "{}" is too low for location "{}" for schedule {}-{}'.format(current,schedule["name"],schedule["start"], schedule["end"]))
            if "max_current" in schedule and current > int(schedule["max_current"]):
                self.alert_mgr.alert('Requestedd current "{}" is too high for location "{}" for schedule {}-{}'.format(current,schedule["name"],schedule["start"], schedule["end"]))


async def main():
    with open('tesla-monitoring.conf.json') as conf_file:
        config = json.load(conf_file)

    alert_mgr = AlertManager(config['alerting'])

    try:
        # client = TeslaApiClient(token=config["token"])
        client = teslapy.Tesla(config["token"]["login"])
        if not client.authorized:
            # print( config["token"]["refresh_token"] )
            client.refresh_token(refresh_token=config["token"]["refresh_token"])


        vehicles = client.vehicle_list()
        print(vehicles)

        vehicle = [ vehicle for vehicle in vehicles if vehicle["display_name"] == config["vehicle_name"] ][0]
        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(config["vehicle_name"]))

        sch_mgr = ScheduleManager(config["locations"], alert_mgr)
        if not sch_mgr.filter_schedules_by_timeslot():
            raise NoScheduleException("Cannot find applicable schedule")
            

        # if vehicle is offline, check if any of the schedules allow waking up. Wake up or quit
        if vehicle["state"] != 'online':
            if sch_mgr.can_wake_up():
                alert_mgr.info("One or more schedules allow vehicle to be woken up")
                vehicle.sync_wake_up()
                while True:
                    try:
                        time.sleep(3)
                        vehicle_data = vehicle.get_vehicle_data()
                        break
                    except:
                        pass

            else:
                raise VehicleOfflineException("Vehicle is offline, and none of the schedules allow wake up")
        else:                
            vehicle_data = vehicle.get_vehicle_data()
        
        charge_state = vehicle_data["charge_state"]
        drive_state = vehicle_data["drive_state"]
        
        if not sch_mgr.filter_schedules_by_location(drive_state["latitude"], drive_state["longitude"]):
            raise NoLocationException("Vehicle is not at a known location")

        sch_mgr.validate_state(charge_state['charging_state'])

        if int(charge_state["charger_pilot_current"])>0:
            req = int(charge_state["charge_current_request"])
            sch_mgr.validate_current(req)
        # print(json.dumps(charge_state, indent=4))

    except (VehicleOfflineException,NoScheduleException,NoLocationException) as ex:
        alert_mgr.info(ex)
    except Exception as ex:
        alert_mgr.alert(ex)
    finally:
        await client.close()

if __name__=='__main__':
    asyncio.run(main())
