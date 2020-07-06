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


async def main():
    with open('tesla-monitoring.conf.json') as conf_file:
        config = json.load(conf_file)

    try:
        # TODO: figure out the json path
        client = TeslaApiClient(token=config["token"])

        vehicles = await client.list_vehicles()
        # TODO: use VIN from config
        vehicle = [ vehicle for vehicle in vehicles if vehicle.display_name == config["vehicle_name"] ][0]
        if vehicle is None:
            raise VehicleNotFoundException('Vehicle {} not found'.format(config["vehicle_name"]))

        # if vehicle is offline, check if any of the schedules allow waking up. Wake up or quit
        if vehicle.state != 'online':
            raise VehicleOfflineException("Vehicle is offline, and none of the schedules allow wake up")


        # TODO: maybe grab the whole config?
        drive_state = await vehicle.get_drive_state()
        charge_state = await vehicle.charge.get_state()
        
        # print(json.dumps(charge_state, indent=4))

        # TODO: dump json into influx


    except Exception as ex:
        log(ex)
    finally:
        await client.close()

if __name__=='__main__':
    asyncio.run(main())
