#!/usr/bin/env python3
"""
read config, strip out sensitive info, save as .template
"""
import json

with open('tesla-monitoring.conf.json') as conf_file:
    config = json.load(conf_file)

dummy = "<CENSORED>"

config["vehicle_name"] = dummy
config["token"]["access_token"] = dummy
config["token"]["refresh_token"] = dummy

for loc in config["locations"]:
    loc["coordinates"]["latitude"] = 10.123456
    loc["coordinates"]["longitude"] = -10.123456

for al in config["alerting"]:
    for field in ["account_sid", "auth_token", "from", "to"]:
        if field in al:
            al[field] = dummy
   
with open('tesla-monitoring.conf.json.example','w') as conf_file:
    json.dump(config, conf_file, indent=4)

