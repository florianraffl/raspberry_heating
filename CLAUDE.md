# CLAUDE.md — AI guidance for the Raspberry Heating HA integration

## What this repo is

A Home Assistant custom integration (HACS) that talks to a .NET 10 REST API running on a Raspberry Pi. The Pi reads DS18B20 temperature sensors and controls pump relays via GPIO. This integration surfaces all of that as HA entities.

**GitHub (source of truth for HACS):** `https://github.com/florianraffl/raspberry_heating`
**Azure DevOps (optional mirror):** `https://heating.visualstudio.com/Heating/_git/home_assistant`

This repo is also a **git submodule** of the parent `Heating` repository (Azure), mounted at `home_assistant/`.

---

## Repo layout

```
custom_components/raspberry_heating/
├── __init__.py          Entry point — sets up coordinator and forwards to platforms
├── manifest.json        HACS metadata (domain, version, iot_class, codeowners)
├── const.py             DOMAIN constant, logger, pump type strings
├── api.py               Async HTTP client + DTOs for the .NET REST API
├── coordinator.py       DataUpdateCoordinator — polls /api/sensor and /api/pump every 30 s
├── data.py              ConfigEntry runtime_data type alias and RaspberryHeatingCoordinatorData
├── entity.py            IntegrationRaspberryHeatingEntity base class (DeviceInfo for Pi)
├── config_flow.py       Config flow (host entry) + Options flow (add pumps)
├── sensor.py            Temperature sensor entities
├── binary_sensor.py     Pump "Running" entity
├── switch.py            Power / Enabled / Auto Mode / Swim Mode switches
├── number.py            Power-on / Power-off threshold entities (heating pump)
├── time.py              Start / End time entities (filter pump), UTC ↔ local conversion
└── translations/
    ├── en.json          English strings
    └── de.json          German strings
```

---

## Tech stack

| Concern | Detail |
|---|---|
| HA version | 2026.3.x (tested) |
| Python | 3.13 |
| HTTP | `aiohttp` via `async_create_clientsession` |
| Coordinator | `DataUpdateCoordinator`, 30 s poll interval |
| Dev environment | VS Code devcontainer; `scripts/setup` pre-installs all deps |

---

## Key patterns and conventions

### One class per file — except DTO dataclasses
`api.py` holds all DTOs (`SensorDto`, `FilterPumpDto`, `HeatingPumpDto`, base `PumpDto`) together because they are simple frozen dataclasses and travel as a unit. All platform classes (sensor, switch, …) are one class per file.

### DTOs are dataclasses, not dicts
The coordinator stores typed `RaspberryHeatingCoordinatorData` with `.sensors: dict[str, SensorDto]` and `.pumps: dict[str, PumpDto]` (where `PumpDto` is `FilterPumpDto | HeatingPumpDto`). Always use `isinstance(pump, HeatingPumpDto)` to branch on pump type — never inspect the `"type"` string after parsing.

### Polymorphic pump JSON
The .NET API returns pumps with a `"type"` discriminator field (`"FilterPump"` or `"HeatingPump"`). Parsing happens in `api.py` via a factory function; nowhere else should raw pump dicts be inspected.

### UTC times everywhere
The .NET service stores and compares all times in UTC. The HA integration is responsible for converting:
- **API → UI:** `_utc_time_str_to_local()` in `time.py` — uses `dt_util.as_local()` anchored to today's date (DST-safe)
- **UI → API:** `_local_time_to_utc_str()` in `time.py` and `_local_time_str_to_utc()` in `config_flow.py` — uses `dt_util.DEFAULT_TIME_ZONE` + `dt_util.as_utc()`

Always anchor to today's date when constructing a `datetime` for DST correctness.

### Translation keys, not `_attr_name`
All entities use `_attr_has_entity_name = True` (set on the base class in `entity.py`) and a `_attr_translation_key` that maps to a key in `translations/en.json` + `translations/de.json`. Never set `_attr_name` on entities that have a translation key — it overrides the translation.

Unassigned temperature sensors are the one exception: they use `_attr_name = sensor.sensor_id` because the name is dynamic (the sensor's hardware ID).

### Dynamic entity registration
Platforms register entities lazily via `coordinator.async_add_listener(_check_XXX)`. Each listener maintains a `known_ids: set[str]` in closure scope to avoid re-registering entities across coordinator refreshes. Always update `known_ids` **after** building `new_entities`, not before.

### Sensor device assignment
At registration time (`sensor.py`) a `sensor_to_pump` map is built from coordinator data. Sensors that match a heating pump's `solar_panel_sensor_key` or `pool_sensor_key` get:
- `_attr_translation_key = "solar_temperature"` / `"pool_temperature"`
- `_attr_device_info` pointing to the pump device (`identifiers={(DOMAIN, pump_id)}`)

Limitation: if a pump is added *after* a sensor entity has already been registered, the sensor stays on the Pi device until HA restarts.

### Swim Mode
`SwimModeSwitch` lives on the Pi device (not a pump device) and is only registered once at least two pumps appear. It uses a `swim_mode_added` boolean flag in the `_check_pumps` closure in `switch.py`. "On" means all pumps disabled; "off" means all pumps enabled.

### `_api_wrapper` response handling
ASP.NET Core uses chunked transfer encoding — `response.content_length` is always `None` even when there is a body. The wrapper returns `None` only for HTTP 204 or when `content_length == 0` (not when it is `None`). Always call `_verify_response_or_raise(response)` first.

### `switchPinId` type cast
HA `NumberSelector` returns a `float`. The .NET API expects `int`. Always cast: `int(user_input["switch_pin_id"])`.

---

## .NET REST API reference

Base URL: `http://<host>:8080`

### Sensors
| Method | Path | Notes |
|---|---|---|
| GET | `/api/sensor` | Returns list of `{ sensorId, busId, deviceId, temperatureValue }` |
| GET | `/api/sensor/{id}` | Single sensor by composite ID (`{busId}_{deviceId}`) |

### Pumps
| Method | Path | Body fields |
|---|---|---|
| GET | `/api/pump` | Returns array; each item has `"type": "FilterPump"` or `"HeatingPump"` |
| POST | `/api/pump/filter` | `switchPinId` (int), `startTime` (UTC HH:MM:SS), `endTime` |
| PUT | `/api/pump/filter` | `pumpId` (required), `startTime?`, `endTime?` |
| POST | `/api/pump/heating` | `switchPinId`, `solarPanelSensorKey`, `poolSensorKey`, `powerOnThreshold`, `powerOffThreshold` |
| PUT | `/api/pump/heating` | `pumpId`, `powerOnThreshold?`, `powerOffThreshold?`, `useAutomaticMode?` |
| POST | `/api/pump/{id}/on` | — |
| POST | `/api/pump/{id}/off` | — |
| POST | `/api/pump/{id}/disable` | Also powers off immediately |
| POST | `/api/pump/{id}/enable` | Runs automatic switch check immediately |
| DELETE | `/api/pump/{id}` | — |

Pump DTO fields of note:
- `pumpId` — UUID string (used as device identifier in HA)
- `isOn` / `isDisabled` — current state booleans
- HeatingPump also has: `useAutomaticMode`, `powerOnThreshold`, `powerOffThreshold`, `solarPanelSensorKey`, `poolSensorKey`
- FilterPump also has: `startTime`, `endTime` (UTC HH:MM:SS strings)

---

## Devcontainer notes

- `scripts/setup` must be run once after container creation (VS Code does this automatically via `postCreateCommand`)
- It pre-installs all HA runtime packages to prevent the lazy-install race condition that causes "No module named X" errors at startup
- It also downloads the `go2rtc` binary (required by `default_config`; it is a subprocess, not a Python package)
- `scripts/develop` starts HA on port 8123 with the `config/` directory

**Windows dev:** use `host.docker.internal:8080` as the host in the HA config flow, and run the .NET service locally (`dotnet run` in `Heating.Raspberry.Service`). The devcontainer cannot reach the Pi LAN through Docker Desktop NAT.

**Linux dev:** `.devcontainer.json` has `"runArgs": ["--network=host"]` so the container shares the host network and can reach the Pi directly.

---

## Adding a new entity type

1. Create `custom_components/raspberry_heating/<platform>.py`
2. Add the platform name to `"platforms"` in `manifest.json`
3. Implement `async_setup_entry(hass, entry, async_add_entities)` following the lazy-registration pattern (closure + `known_ids` set + `async_add_listener`)
4. Add translation keys to both `translations/en.json` and `translations/de.json` under `entity.<platform>.<key>`
5. Set `_attr_translation_key` and `_attr_icon` on the entity class; do **not** set `_attr_name`

---

## Branch strategy

- `main` — stable / released (HACS pulls from here)
- `add-pumps` — pump integration feature branch (merge → main when stable)
- Feature branches: `<short-description>/<base>`, e.g. `add-heating-schedule/add-pumps`
