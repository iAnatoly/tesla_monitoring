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
from influxdb import InfluxDBClient


def log(msg):
    print(msg)

async def main():
    with open('/etc/homebridge/hbr-tesla/config.json') as conf_file:
        config = json.load(conf_file)

    #try:
        target_vin = config["accessories"][0]['vin']
        token = {
                "access_token": config["accessories"][0]["authToken"],
                "expires_in": 3888000,
                "created_at": int(time.time()-1),
                "refresh_token": ""
        }
        client = TeslaApiClient(token=token)

        vehicles = await client.list_vehicles()
        log(vehicles)
        
        vehicle = [ vehicle for vehicle in vehicles if vehicle.vin == target_vin ][0]

        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(vin))

        # if vehicle is offline, check if any of the schedules allow waking up. Wake up or quit
        if vehicle.state != 'online':
            raise Exception("Vehicle is offline. That is OK.")


        # TODO: maybe grab the whole config?
        drive_state = await vehicle.get_drive_state()
        charge_state = await vehicle.charge.get_state()
        
        print(json.dumps(charge_state, indent=4))

        # TODO: dump json into influx

    try:
        pass
    except Exception as ex:
        log(ex)
    finally:
        await client.close()

if __name__=='__main__':
    asyncio.run(main())
