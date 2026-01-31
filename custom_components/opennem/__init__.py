"""OpenNEM"""

import logging
import datetime

import voluptuous as vol

import aiohttp
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util
from homeassistant.helpers import config_validation as cv

from .config_flow import configured_instances
from .const import (
    API_ENDPOINT,
    API_ENDPOINT_NEM,
    API_ENDPOINT_WA,
    API_ENDPOINT_AU,
    CONF_REGION,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
    VERSION,
    # DEFAULT_VALUES,
    FOSSIL_FUEL_POWER,
    RENEWABLE_POWER,
    CURTAILMENT_THRESHOLD,
)

KNOWN_FUEL_TYPES = (
    FOSSIL_FUEL_POWER
    + RENEWABLE_POWER
    + ["imports", "exports", "battery_charging", "battery_discharging", "pumps"]
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_REGION): cv.string})}, extra=vol.ALLOW_EXTRA
)

DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=10)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup OpenNEM Component"""
    if DOMAIN not in config:
        return True
    conf = config[DOMAIN]
    region = conf.get[CONF_REGION].upper()
    identifier = f"{DEFAULT_NAME} {region}"
    if identifier in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_REGION: region},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup OpenNEM Component as Config Entry"""
    _LOGGER.info("OpenNEM: Version %s is starting", VERSION)
    hass.data.setdefault(DOMAIN, {})

    coordinator = OpenNEMDataUpdateCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    # _LOGGER.debug("OpenNEM: Feed Coordinator Added for %s", entry.entry_id)

    async def _enable_scheduled_updates(*_):
        """Activate Data Update Coordinator"""
        scan_interval = DEFAULT_SCAN_INTERVAL
        if isinstance(scan_interval, int):
            coordinator.update_interval = datetime.timedelta(minutes=scan_interval)
        else:
            coordinator.update_interval = scan_interval
        await coordinator.async_refresh()

    if hass.state == CoreState.running:
        await _enable_scheduled_updates()
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _enable_scheduled_updates
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenNEM Component"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("OpenNEM: Removed Config for %s", entry.entry_id)
    return unload_ok


async def update_listener(hass, entry):
    """Update Listener"""
    entry.data = entry.options
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, "sensor"))


class OpenNEMDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data"""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        self.config: ConfigEntry = config
        self.hass = hass
        self._region = config.data[CONF_REGION]
        self._config_entry_id = config.entry_id
        self._interval = DEFAULT_SCAN_INTERVAL
        _LOGGER.debug(
            "OpenNEM [%s1]: Data will be updated every %s", self._region, self._interval
        )
        super().__init__(
            self.hass, _LOGGER, name=DOMAIN, update_method=self.async_update
        )

    @property
    def region_name(self) -> str:
        """Return Region Name of Coordinator"""
        return self._region

    async def async_update(self) -> dict:
        """Get Latest Date and Update State"""

        data = None
        attrs = {}
        _LOGGER.debug("OpenNEM [%s]: Default Values - %s", self._region, attrs)

        region = self._region + "1"
        if region == "nem1":
            url = API_ENDPOINT_NEM
        elif region == "au1":
            url = API_ENDPOINT_AU
        elif region == "wa1":
            url = API_ENDPOINT_WA
        else:
            url = API_ENDPOINT.format(region.upper())
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as remotedata:
                _LOGGER.debug("OpenNEM [%s]: Getting State from %s", region, url)
                if remotedata.status == 200:
                    data = await remotedata.json()
                else:
                    _LOGGER.error("OpenNEM [%s]: Issue getting data", region)

        if data is not None:
            _LOGGER.debug(
                "OpenNEM [%s]: Data Downloaded, Commencing Processing", region
            )

            attrs["emission_intensity"] = 0.0
            attrs["fossilfuel"] = 0.0
            attrs["renewables"] = 0.0
            emission_factors = {}

            _LOGGER.debug("OpenNEM [%s]: Values Before - %s", region, attrs)

            # TODO produce a total curtailment value

            for row in data["data"]:
                value = self._last_value_from_data(row["history"]["data"])
                if value is None:
                    value = 0.0

                _LOGGER.debug(
                    "[%s]: id: %s, type: %s, code: %s, value: %f",
                    region,
                    row["id"],
                    row["type"],
                    row.get("code"),
                    value,
                )

                match row["type"]:
                    case "power":
                        fuel = row["code"]
                        if fuel == "NEM":
                            if ".curtailment." in row["id"]:
                                # the fuel_tech key is of the form curtailment_{type}
                                attrs[row["fuel_tech"]] = round(value, 2)
                            elif ".demand" in row["id"]:
                                attrs["demand"] = round(value, 2)

                            else:
                                # ignore others
                                _LOGGER.debug("ignoring NEM with code=%s", row["code"])
                                pass
                        else:
                            # power generation/import/export
                            if fuel in ("exports", "battery_charging", "pumps"):
                                value = -abs(value)

                            attrs[fuel] = round(value, 2)

                            if fuel not in KNOWN_FUEL_TYPES:
                                _LOGGER.warning(
                                    "[%s] unknown fuel type: %s", region, fuel
                                )

                    # we calculate this from emissions_factor below in favour of using these values directly
                    # case "emissions":
                    #     if row["code"] != "exports":
                    #         attrs["emissions"] += value
                    case "emissions_factor":
                        emission_factors[row["code"]] = value
                    case "price":
                        attrs["price"] = value

            fossil_power = sum([attrs.get(power) or 0 for power in FOSSIL_FUEL_POWER])
            attrs["fossilfuel"] = round(fossil_power, 2)

            renewable_power = sum([attrs.get(power) or 0 for power in RENEWABLE_POWER])
            attrs["renewables"] = round(renewable_power, 2)

            genvalue = attrs["fossilfuel"] + attrs["renewables"]
            if genvalue:
                attrs["generation"] = round(genvalue, 2)
                attrs["state"] = round(genvalue, 2)
            else:
                attrs["generation"] = 0
                attrs["state"] = 0

            genvsdemand = None
            if region != "wa1" and "demand" in attrs:
                genvsdemand = attrs["generation"] - attrs["demand"]
                if genvsdemand:
                    attrs["genvsdemand"] = round(genvsdemand, 2)
                else:
                    attrs["genvsdemand"] = 0

            # calculate kg/kWh CO2 equiv rate
            emission_intensity = 0.0
            for fuel, val in emission_factors.items():
                if fuel in ("exports"):
                    # we don't consider cost of exports when considering cost of generated power
                    continue
                # most fuel types appear to divide the emissions factor by 12 for the 5-minute
                # inteval data. but this does not appear to occur for imports(?!)
                if fuel == "imports":
                    emission_factor = val
                else:
                    emission_factor = val * 12
                # _LOGGER.debug(
                #     "[%s] emission factor for %s is %f kg/kWh",
                #     region,
                #     fuel,
                #     emission_factor,
                # )
                emission_intensity += (
                    attrs[fuel] / attrs["generation"]
                ) * emission_factor
            attrs["emission_intensity"] = round(emission_intensity, 3)

            # total curtailment
            attrs["curtailment"] = sum(
                [attrs[fuel] for fuel in attrs.keys() if "curtailment_" in fuel]
            )
            if attrs["renewables"] > 0:
                ratio_curtailed = attrs["curtailment"] / attrs["renewables"]
            else:
                ratio_curtailed = 0.0
            _LOGGER.debug(
                "[%s] %f of renewables are curtailed", region, round(ratio_curtailed, 2)
            )

            # if curtailment is non-trivial, then we can consider consumed electricity as
            # "free" from direct generation emissions
            if ratio_curtailed > CURTAILMENT_THRESHOLD:
                attrs["effective_emission_intensity"] = 0.0
            else:
                attrs["effective_emission_intensity"] = attrs["emission_intensity"]

            _LOGGER.debug("received data current at %s", data["created_at"])

            if region == "wa1":
                attrs["last_update"] = dt_util.as_utc(
                    datetime.datetime.strptime(
                        str(data["created_at"]), "%Y-%m-%dT%H:%M:%S+08:00"
                    )
                )
            else:
                attrs["last_update"] = dt_util.as_utc(
                    datetime.datetime.strptime(
                        str(data["created_at"]), "%Y-%m-%dT%H:%M:%S+10:00"
                    )
                )
        else:
            _LOGGER.debug("OpenNEM [%s]: No Data Found", region)

        _LOGGER.debug("OpenNEM [%s]: Values to pass to Sensor: %s", region, attrs)
        return attrs

    def _last_value_from_data(self, data):
        if data[-1] is not None:
            return data[-1]
        elif data[-2] is not None:
            return data[-2]
        else:
            return data[-3]
