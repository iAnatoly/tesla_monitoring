# tesla-influx

## overview

The purpose of this simple script is twofold:
1. Export data from Tesla API to a time series db (influx)
2. Use the same token as tesla-homebridge plugin, and send auth_successful signal as a separate measurement to grafana, to be able to generate the alert when token expires.

## algorithm

1. read config files:
	- location of homebridge plugin config
	- influx connectibvity params

2. Connect to influx, read last drive_state and charge_state measurememts (select order by time desc limit 1)

3. connect to tesla API, read vehicle online state

4. read mesurements according to following logic 

if last drive_state = driving:
	read measurements immediately
if last drive_state = parked and charge_cable is plugged:
	if offline:
		wake up
	read measurements immediately
else;
	if ofline:
		ignore
	read measurements in 15 minues 

5. send measurements to influx
6. finally, send authz_successful to influx

## scheduling the script

Just schedule to run every minute using cron.

## setting up influx

influx -username admin -password secret

create database tesla;
create user tesla_write with password 'writesecret';
create user tesla_read with password 'readsecret';
grant READ on tesla to tesla_read;
grant WRITE on tesla to tesla_write;

## setting up grafana

jfgi



