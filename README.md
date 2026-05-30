# Raspberry Heating — Home Assistant Integration

A [HACS](https://hacs.xyz) custom integration for Home Assistant that exposes temperature sensors and pump control from a Raspberry Pi running the [Raspberry Heating service](https://heating.visualstudio.com/Heating/_git/Heating).

---

## Features

- **Temperature sensors** — all DS18B20 1-Wire sensors connected to the Pi, updated every 30 s
- **Filter pump control** — turn on/off, enable/disable, edit start/end times (stored in UTC, displayed in local time)
- **Heating pump control** — turn on/off, enable/disable, automatic mode (driven by solar-panel vs pool temperature differential), configurable power-on/off thresholds
- **Sensor–device binding** — sensors assigned to a heating pump appear under that pump's device in HA, not the generic Pi device
- **Swim Mode** — a global switch (visible when ≥ 2 pumps are configured) that disables all pumps at once so it is safe to swim, and re-enables them all when turned off
- **English + German translations** — full UI strings in both languages via HA translation keys

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Home Assistant 2024.1+ | Tested on 2026.3.x |
| HACS | For easy installation and updates |
| Raspberry Heating service | Must be running and reachable at `http://<pi-host>:8080` |

---

## Installation via HACS

1. In HA, go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/florianraffl/raspberry_heating` as an **Integration**
3. Search for **Raspberry Heating** and click **Download**
4. Restart Home Assistant

---

## Manual Installation

```bash
# From your HA config directory
git clone https://github.com/florianraffl/raspberry_heating.git /tmp/raspberry_heating
cp -r /tmp/raspberry_heating/custom_components/raspberry_heating \
      config/custom_components/raspberry_heating
```

Restart Home Assistant after copying.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Raspberry Heating**
3. Enter the hostname or IP address of your Raspberry Pi (e.g. `192.168.1.50`)
   - The service listens on port **8080** by default
4. Click **Submit** — HA will test the connection and create the integration entry

### Adding pumps

After the integration is set up, click **Configure** on the integration entry:

- **Filter Pump** — GPIO pin, start time (local), end time (local)
- **Heating Pump** — GPIO pin, solar-panel sensor ID, pool sensor ID, power-on threshold (°C), power-off threshold (°C)

Sensor IDs are shown on the Pi device's sensor entities, e.g. `w1_bus_master1_28-00000fake0001`.

---

## Entities

### Per filter pump

| Entity | Type | Description |
|---|---|---|
| Running | Binary sensor | Whether the relay is currently energised |
| Power | Switch | Manually turn the relay on/off (unavailable when pump is disabled) |
| Enabled | Switch | Enable or disable the pump |
| Start Time | Time | Daily start time — displayed in local timezone, stored in UTC |
| End Time | Time | Daily end time — displayed in local timezone, stored in UTC |

### Per heating pump

| Entity | Type | Description |
|---|---|---|
| Running | Binary sensor | Whether the relay is currently energised |
| Power | Switch | Manually turn the relay on/off (unavailable when disabled or in auto mode) |
| Enabled | Switch | Enable or disable the pump |
| Automatic Mode | Switch | Let the pump self-regulate based on temperature thresholds |
| Power-On Threshold | Number | Solar panel must be this many °C warmer than pool to turn on |
| Power-Off Threshold | Number | Turn off when the temperature difference drops below this value |
| Solar Panel Temperature | Sensor | Linked DS18B20 (appears under the pump device) |
| Pool Temperature | Sensor | Linked DS18B20 (appears under the pump device) |

### Pi device (global)

| Entity | Type | Description |
|---|---|---|
| Unassigned temperature sensors | Sensor | DS18B20 sensors not linked to any pump |
| Swim Mode | Switch | Disables all pumps at once; visible when ≥ 2 pumps are configured |

---

## Development

See [CLAUDE.md](CLAUDE.md) for architecture details and coding conventions used in this repo.

### Quick start (devcontainer)

1. Open the repo in VS Code with the **Dev Containers** extension
2. VS Code will build the container and run `scripts/setup` automatically
   - This pre-installs all HA runtime dependencies and downloads the `go2rtc` binary
3. Run `scripts/develop` to start Home Assistant with the integration loaded
4. HA is available at `http://localhost:8123`

### Connecting to the .NET backend

- **Linux host** — `.devcontainer.json` uses `--network=host`, so `<pi-ip>:8080` works directly
- **Windows/macOS host** — run the .NET service locally and use `host.docker.internal:8080` as the host in the HA config flow

### Fake sensors (no Pi needed)

Configure test sensors in the .NET service's `appsettings.Development.json`:

```json
"FakeSensors": {
  "Sensors": [
    { "BusId": "w1_bus_master1", "DeviceId": "28-00000fake0001", "Temperature": 22.5 },
    { "BusId": "w1_bus_master1", "DeviceId": "28-00000fake0002", "Temperature": 35.0 }
  ]
}
```

---

## Raspberry Pi service setup

The backend service is part of the [Heating repository](https://heating.visualstudio.com/Heating/_git/Heating) on the `new_home_assistant` branch.

Enable 1-Wire in `/boot/config.txt`:
```
dtoverlay=w1-gpio,gpiopin=12
```

Run via Docker or `rc.local`. The service auto-creates its SQLite database on first start.

---

## License

MIT — see [LICENSE](LICENSE).
