# IoT Module

This module handles the ingestion of hardware sensor data into the AgriSense platform.

## Swapping Simulator for Real Hardware

By default, the system runs with a simulated sensor network. To swap to real hardware:

1. Open `.env` and change `IOT_SOURCE=simulator` to `IOT_SOURCE=hardware`.
2. Open `iot/hardware_bridge.py` and implement `get_current_readings()` to fetch from your physical sensors (via MQTT, direct HTTP, Serial, etc.).
3. Restart the API server. Everything else—ingestor, feature_adapter, and routing—remains exactly the same.

## Redis Key Design

- `iot:latest:{farmer_id}:{crop_type}`: (TTL: 10min) Holds the most recent `IoTReading` JSON. Used by the frontend for fast polling without hitting the DB.
- `iot:stats:{farmer_id}`: (TTL: 1hr) Aggregated 24hr stats for the farmer.
- `iot:anomaly:{farmer_id}`: (TTL: 24hr) A list of recent anomalies detected for the farmer.
- `iot:simulator:state`: (Persistent) Holds simulator state if necessary.

## Feature Adapter Integration

The `iot/feature_adapter.py` acts as a bridge. Its `transform_for_pipeline` function takes an `IoTReading` and returns exactly the dictionary shape expected by the `preprocessing/feature_builder.py` pipeline. This ensures the ML forecaster works natively with the IoT data.

## Anomaly Detection

In `iot/ingestor.py`, readings are validated and checked for anomalies. If an anomaly is detected (e.g. temperature > 40C), it is written to Redis, and `feature_adapter.notify_pipeline()` is called to trigger a priority re-run of the forecaster.

## Manual Testing (cURL)

You can manually test hardware ingestion via the API:

```bash
curl -X POST "http://localhost:8000/iot/reading" \
     -H "Content-Type: application/json" \
     -d '{
           "device_id": "DEVICE-FARM001-SOIL",
           "farmer_id": "FARMER-001",
           "crop_type": "wheat",
           "lat": 28.5,
           "lng": 77.2,
           "soil_moisture": 45.5,
           "temperature": 25.1,
           "humidity": 60.0,
           "ph_level": 6.5,
           "source": "hardware",
           "quality_score": 1.0
         }'
```
