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
import traceback
import teslapy
from datetime import datetime
from aioinflux import InfluxDBClient

REFRESH_BACKOFF = 15*60
WAKEUP_BACKOFF = 60*60*4

def log(msg):
    print(msg)

class SoftException(Exception):
    pass

class VehicleOfflineException(SoftException):
    pass

class VehicleNotFoundException(Exception):
    pass

class TooSoonException(SoftException):
    pass

def get_influx(influx_config):
    assert influx_config 
    return InfluxDBClient(
            host=influx_config['host'], 
            port=influx_config['port'], 
            username=influx_config['username'],
            password=influx_config['password'],
            db=influx_config['db'])


async def get_influx_measurement(influx_config,measurement,field):
    async with get_influx(influx_config) as influx_client:
        try:
            resp = await influx_client.query('select * from drive_state order by time desc limit 1')
            values = resp['results'][0]['series'][0]['values'][0]
            columns = resp['results'][0]['series'][0]['columns']
            return (values[columns.index('time')],values[columns.index(field)])
        except:
            return (0,0)

async def dump_to_influx(influx_config, json_body):
    async with get_influx(influx_config) as influx_client:
        await influx_client.write(json_body)

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
                "refresh_token": hbr_config["accessories"][0]["refreshToken"]
        }

        client = teslapy.Tesla(hbr_config["accessories"][0]["email"])
        if not client.authorized:
            client.refresh_token(refresh_token=token["refresh_token"])

        vehicles = client.vehicle_list()
        vehicle = [ vehicle for vehicle in vehicles if vehicle["vin"] == target_vin ][0]

        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(vin))

        (lasttime,power) = await get_influx_measurement(config['influx'], 'drive_state','power')
        lasttime = datetime.fromtimestamp(lasttime/(10**9))

        # backoff if the car is napping
        if power is None or power==0:
            diff = datetime.now() - lasttime
            if diff.seconds < REFRESH_BACKOFF: 
                raise TooSoonException("Too soon")
        else:
            print('not waiting because power is {}'.format(power))

        # if vehicle is offline, do not wake it up - just skip the whole thing
        if vehicle["state"] != 'online':
            diff = datetime.now() - lasttime
            if diff.seconds < WAKEUP_BACKOFF:
                raise VehicleOfflineException("Vehicle is offline. That is OK.")
            else:
                log(f'Waking up the vehicle since it has been {diff.seconds} seconds since last update')
                vehicle.sync_wake_up()

        vehicle_data = vehicle.get_vehicle_data()
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
                    'needs_alert': 0,
                }
            }
        ]
        
        print(json_body)
        await dump_to_influx(config['influx'], json_body)


    except Exception as ex:
        # print(traceback.format_exc())
        log(type(ex).__name__)
        log(ex)
        needs_alert = 1 if isinstance(ex,SoftException) else 1
        if needs_alert and "token" not in str(ex).lower():
            needs_alert = 0
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
        client.close()

if __name__=='__main__':
    asyncio.run(main())
