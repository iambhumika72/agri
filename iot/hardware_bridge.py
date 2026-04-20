from .simulator import IoTDataSource
from .schemas import IoTReading

class HardwareIoTBridge(IoTDataSource):
    """
    FUTURE: Replace IoTSimulator with this class when real 
    sensors are connected.
    
    To activate real hardware:
    1. Set IOT_SOURCE=hardware in .env
    2. Implement get_current_readings() to read from 
       your physical sensors (MQTT/serial/GPIO/HTTP)
    3. Everything else — ingestor, pipeline, API, frontend — 
       unchanged.
    """
    
    async def get_current_readings(self, farmer_id: str) -> list[IoTReading]:
        # TODO: implement based on hardware protocol
        raise NotImplementedError("Hardware bridge not yet implemented")

    async def start(self): 
        # TODO: Start MQTT listeners or polling threads here
        pass
    
    async def stop(self): 
        # TODO: Stop listeners here
        pass

hardware_bridge = HardwareIoTBridge()
