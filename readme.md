# Wunderground Weather

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/DmitryBoiadji/wunderground_weather/actions/workflows/validate.yaml/badge.svg)](https://github.com/DmitryBoiadji/wunderground_weather/actions/workflows/validate.yaml)

Home Assistant integration for [Weather Underground](https://www.wunderground.com) personal weather stations (PWS). It works with any public station, no API key or Weather Underground account is needed.

![Screenshot 2024-12-22 at 18 59 40](https://github.com/user-attachments/assets/b95259d8-e5e0-4aab-8308-8638f1227b4a)

## Features

- A device per station with these sensors:

  | Sensor | Unit | Notes |
  |---|---|---|
  | Temperature, dew point, heat index, wind chill | °C | |
  | Humidity | % | |
  | Atmospheric pressure | hPa | |
  | Wind speed, wind gust | km/h | |
  | Wind direction | ° | |
  | Solar radiation | W/m² | only if the station has the sensor |
  | UV index | | only if the station has the sensor |
  | Precipitation intensity | mm/h | |
  | Precipitation today | mm | resets at local midnight |
  | Last observation | timestamp | diagnostic |

  All sensors have device and state classes, so Home Assistant converts units to your unit system and keeps long-term statistics.
- A weather entity with the station readings, the current condition and daily, day/night and hourly forecasts.
- Sensors become unavailable when the station stops reporting for more than an hour, so automations do not act on frozen values.
- Diagnostics download for bug reports.

## Requirements

Home Assistant 2025.4 or newer.

## Installation

### HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DmitryBoiadji&repository=wunderground_weather&category=integration)

Or manually:

1. In HACS open the menu in the top right corner and choose **Custom repositories**.
2. Add `https://github.com/DmitryBoiadji/wunderground_weather` with the type **Integration**.
3. Download **Wunderground Weather** and restart Home Assistant.

### Manual

Copy `custom_components/wunderground_weather` into the `custom_components` folder of your Home Assistant configuration and restart Home Assistant.

## Configuration

1. Find the station on [wunderground.com](https://www.wunderground.com/wundermap). The station ID is the last part of the dashboard URL, for example `KCASANFR1753` in `https://www.wunderground.com/dashboard/pws/KCASANFR1753`.
2. Go to **Settings > Devices & services > Add integration** and search for **Wunderground Weather**.
3. Enter the station ID. The name is optional, by default the neighborhood reported by the station is used.

The observation update interval (30 to 3600 seconds, default 60) can be changed later with **Configure** on the integration card.

## How it works

The integration reads the public API key that the Weather Underground website embeds in the station dashboard page, then uses it to request:

- the current observation of the station, every update interval;
- the current conditions and forecasts for the station location from weather.com, every 15 minutes.

The key is cached and fetched again only when the API rejects it. This is not an official API: if Weather Underground changes its website, the integration may stop working until it is updated.

The current condition comes from weather.com. If the station rain gauge measures precipitation that weather.com does not report, the station wins. When weather.com is not available, the condition is estimated from the station sensors.

## Upgrading from 0.1.x

Existing entities keep their entity IDs and history. Entities are now grouped into a device, so their friendly names change to the `<station> <sensor>` format, for example `Garden Temperature`.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.wunderground_weather: debug
```

When opening an issue, attach the diagnostics file from the device page (**Download diagnostics**). Station coordinates are removed from it.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```
