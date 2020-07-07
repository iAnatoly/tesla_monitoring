#!/usr/bin/env python3

"""
    1. Read token from homebridge tesla plugin, to alert on token expiration
    2. Read json from tesla *only if the vehicle is awake*
    3. Dump tesla json info influx

"""

import asyncio
import json
import time
from datetime import datetime
from tesla_api import TeslaApiClient
#from influxdb import InfluxDBClient
from aioinflux import InfluxDBClient


def log(msg):
    print(msg)

async def main():
    with open('tesla-influx.conf.json') as conf_file:
        config = json.load(conf_file)
        assert config

    with open(config['homebridge_conf_path']) as hbr_conf_file:
        hbr_config = json.load(hbr_conf_file)
        assert hbr_config

    try:
        timestamp = int(time.time()-1)
        target_vin = hbr_config["accessories"][0]['vin']
        # mock a token structure to match the target format
        token = {
                "access_token": hbr_config["accessories"][0]["authToken"],
                "expires_in": 3888000,      # does not matter
                "created_at": timestamp,    # just now
                "refresh_token": ""         # does not matter
        }
        client = TeslaApiClient(token=token)

        vehicles = await client.list_vehicles()
        
        vehicle = [ vehicle for vehicle in vehicles if vehicle.vin == target_vin ][0]

        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(vin))

        # if vehicle is offline, check if any of the schedules allow waking up. Wake up or quit
        if vehicle.state != 'online':
            raise Exception("Vehicle is offline. That is OK.")


        # TODO: maybe grab the whole config?
        drive_state = await vehicle.get_drive_state()
        charge_state = await vehicle.charge.get_state()
        
        json_body = [
            {
                'measurement': 'charge_state',
        '        tags': {
                    'vin': target_vin,
                },
                'time': timestamp,
                'fields': charge_state,
            },
            {
                'measurement': 'drive_state',
        '        tags': {
                    'vin': target_vin,
                },
                'time': timestamp,
                'fields': drive_state,
            }
        ]
        # TODO: place this in local conf
        influx_config=config['influx']
        assert influx_config 

        async with InfluxDBClient(
                host=influx_config['host'], 
                port=influx_config['port'], 
                username=influx_config['username'],
                password=influx_config['password'],
                db=influx_config['db']) as influx_client:
            await influx_client.write(json_body)

    except Exception as ex:
        log(ex)
    finally:
        await client.close()
        
if __name__=='__main__':
    asyncio.run(main())
