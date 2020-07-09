#!/usr/bin/env python3

"""
    1. Read token from homebridge tesla plugin, to alert on token expiration
    2. Read json from tesla *only if the vehicle is awake*
    3. Dump tesla json info influx

"""

import warnings
warnings.filterwarnings("ignore", module="aioinflux")

import asyncio
import json
import time
from datetime import datetime
from tesla_api import TeslaApiClient
#from influxdb import InfluxDBClient
from aioinflux import InfluxDBClient


def log(msg):
    print(msg)

class VehicleOfflineException(Exception):
    pass

class VehicleNotFoundException(Exception):
    pass


async def main():
    with open('tesla-influx.conf.json') as conf_file:
        config = json.load(conf_file)
        assert config

    with open(config['homebridge_conf_path']) as hbr_conf_file:
        hbr_config = json.load(hbr_conf_file)
        assert hbr_config

    try:
        timestamp = int(time.time_ns())
        target_vin = hbr_config["accessories"][0]['vin']
        # mock a token structure to match the target format
        token = {
                "access_token": hbr_config["accessories"][0]["authToken"],
                "expires_in": 3888000,      # does not matter
                "created_at": timestamp/1000000000,    # just now
                "refresh_token": ""         # does not matter
        }
        client = TeslaApiClient(token=token)

        vehicles = await client.list_vehicles()
        
        vehicle = [ vehicle for vehicle in vehicles if vehicle.vin == target_vin ][0]

        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(vin))

        # if vehicle is offline, do not wake it up - just skip the whole thing
        if vehicle.state != 'online':
            raise VehicleOfflineException("Vehicle is offline. That is OK.")

        vehicle_data = await vehicle.get_data()
        drive_state = vehicle_data["drive_state"]
        charge_state = vehicle_data["charge_state"]
        climate_state = vehicle_data["climate_state"]
        vehicle_state = vehicle_data["vehicle_state"]
        
        # inject odometer and temp into drive_state
        drive_state["odometer"] = vehicle_data["vehicle_state"]["odometer"]
        drive_state["outside_temp"] = vehicle_data["climate_state"]["outside_temp"]
        drive_state["inside_temp"] = vehicle_data["climate_state"]["inside_temp"]
        
        json_body = [
            {
                'measurement': 'charge_state',
                'tags': {
                    'vin': target_vin,
                },
                'time': timestamp,
                'fields': charge_state,
            },
            {
                'measurement': 'drive_state',
                'tags': {
                    'vin': target_vin,
                },
                'time': timestamp,
                'fields': drive_state,
            },
            {
                "measurement": "authz_state",
                'time': timestamp,
                'fields': {
                    'authz_state': 1,
                }
            }
        ]

        await dump_to_influx(config['influx'], json_body)


    except Exception as ex:
        log(ex)
        needs_alert = 0 if type(ex) is VehicleOfflineException else 1
        if needs_alert:
            log('error should result in an alert')
        json_body = [
            {
                "measurement": "authz_state",
                'time': timestamp,
                'fields': {
                    'needs_alert': needs_alert,
                }
            }
        ]
        await dump_to_influx(config['influx'], json_body)

        #    raise ex
    finally:
        await client.close()

async def dump_to_influx(influx_config, json_body):
        assert influx_config 

        async with InfluxDBClient(
                host=influx_config['host'], 
                port=influx_config['port'], 
                username=influx_config['username'],
                password=influx_config['password'],
                db=influx_config['db']) as influx_client:
            await influx_client.write(json_body)
        
if __name__=='__main__':
    asyncio.run(main())
