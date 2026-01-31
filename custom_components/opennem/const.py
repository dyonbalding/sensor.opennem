"""OpenNEM Constants"""

# API
API_ENDPOINT = "https://data.openelectricity.org.au/v4/stats/au/NEM/{}/power/7d.json"
API_ENDPOINT_NEM = "https://data.openelectricity.org.au/v4/stats/au/NEM/power/7d.json"
API_ENDPOINT_WA = "https://data.openelectricity.org.au/v4/stats/au/WEM/power/7d.json"
API_ENDPOINT_AU = "https://data.openelectricity.org.au/v4/stats/au/AU/power/7d.json"

# Config
CONF_REGION = "region"
CONF_REGION_DEFAULT = "nem"
CONF_REGION_LIST = {
    "au": "All Regions",
    "nem": "NEM",
    "nsw": "New South Wales",
    "qld": "Queensland",
    "sa": "South Australia",
    "tas": "Tasmania",
    "vic": "Victoria",
    "wa": "Western Australia",
}
CONF_REGION_SIMP = ["au", "nem", "nsw", "qld", "sa", "tas", "vic", "wa"]

# Defaults
DEFAULT_ICON = "mdi:transmission-tower"
DEFAULT_NAME = "OpenNEM"
DEFAULT_FORCE_UPDATE = True

# Misc
VERSION = "2023.09.1"
DOMAIN = "opennem"
PLATFORM = "sensor"
ATTRIBUTION = "Data provided by OpenNEM"
COORDINATOR = "coordinator"
PLATFORMS = ["sensor"]
DEVICE_CLASS = "connectivity"

FOSSIL_FUEL_POWER = [
    "coal_black",
    "coal_brown",
    "distillate",
    "gas_ccgt",
    "gas_ocgt",
    "gas_recip",
    "gas_steam",
    "gas_wcmg",
]

RENEWABLE_POWER = [
    "bioenergy_biomass",
    "bioenergy_biogas",
    "hydro",
    "solar_utility",
    "wind",
    "solar_rooftop",
]

# ratio of renewable energy that is curtailed, above which we deem generation to
# be "free" from direct emissions
CURTAILMENT_THRESHOLD = 0.02
