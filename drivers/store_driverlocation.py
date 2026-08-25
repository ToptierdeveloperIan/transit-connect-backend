from Loginandauthentication.finalOTP import r


def store_driverlocationredis(driverid,lat,lng):
    r.geoadd("drivers_location", (driverid,lat,lng))
