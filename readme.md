# Wunderground Weather Integration

Home Assistant integration for Weather Underground personal weather stations.

## Features
- Weather entity with current conditions
- Individual sensors for:
  - Temperature
  - Humidity
  - Pressure
  - Wind speed and direction
  - Precipitation
  - UV index
  - Solar radiation

## Installation
1. Add this repository to HACS:
   - Go to HACS → Settings → Repositories
   - Add repository: `DmitryBoiadji/wunderground_weather`
   - Category: Integration
2. Install the integration via HACS
3. Add your Weather Underground station ID in Home Assistant
4. (Optional) Set a custom name for your station

## Configuration
1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Wunderground Weather"
4. Enter your station ID
5. (Optional) Set a custom name for your station
6. Set update interval (default: 60 seconds)

![Screenshot 2024-12-22 at 18 59 40](https://github.com/user-attachments/assets/b95259d8-e5e0-4aab-8308-8638f1227b4a)
