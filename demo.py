import asyncio
import struct
import logging
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SERVICE_UUID = "19B10000-E8F2-537E-4F6C-D104768A1214"
AUDIO_DATA_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"
PHOTO_DATA_UUID = "19B10005-E8F2-537E-4F6C-D104768A1214"
PHOTO_CONTROL_UUID = "19B10006-E8F2-537E-4F6C-D104768A1214"

DEVICE_NAME = "OpenGlass"


class OpenGlassClient:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self._photo_data = bytearray()
        self._audio_data = bytearray()
        self._on_photo = None
        self._on_audio = None
        self._address = None

    async def discover(
        self, timeout: float = 5.0, retries: int = 10
    ) -> Optional[BLEDevice]:
        """扫描并返回 OpenGlass 设备"""
        for attempt in range(retries):
            logger.info(f"Scanning for devices... (attempt {attempt + 1}/{retries})")
            scanner = BleakScanner()
            await scanner.start()
            await asyncio.sleep(timeout)
            await scanner.stop()
            devices = scanner.discovered_devices

            logger.info(f"Found {len(devices)} devices:")
            for device in devices:
                logger.info(f"  - {device.name or 'Unknown'}: {device.address}")

            for device in devices:
                if device.address and device.name == DEVICE_NAME:
                    logger.info(f"✓ Found {DEVICE_NAME}: {device.address}")
                    return device

            if attempt < retries - 1:
                logger.info("OpenGlass not found, retrying in 2s...")
                await asyncio.sleep(2)

        logger.warning("OpenGlass device not found")
        return None

    async def connect(self, device: BLEDevice, max_retries: int = 10):
        """连接到 OpenGlass 设备"""
        address = device.address

        for attempt in range(max_retries):
            logger.info(
                f"Connecting to {address} (attempt {attempt + 1}/{max_retries})..."
            )

            self.client = BleakClient(device, timeout=30.0, disconnected_timeout=4.0)

            try:
                await self.client.connect()

                if self.client.is_connected:
                    logger.info(f"✓ Connected to {address}")
                    break
            except Exception as e:
                logger.warning(f"Connection attempt failed: {e}")
                await asyncio.sleep(1)
                continue
        else:
            raise Exception("Failed to connect after max retries")

        if not self.client.is_connected:
            raise Exception("Connection failed")

        self.client.on_disconnected = self._on_disconnect

        logger.info("Subscribing to notifications...")
        try:
            await self.client.start_notify(PHOTO_DATA_UUID, self._handle_photo_data)
            logger.info(f"✓ Subscribed to Photo Data ({PHOTO_DATA_UUID})")

            await self.client.start_notify(AUDIO_DATA_UUID, self._handle_audio_data)
            logger.info(f"✓ Subscribed to Audio Data ({AUDIO_DATA_UUID})")
        except Exception as e:
            logger.error(f"Failed to subscribe to notifications: {e}")
            raise

        logger.info("Connection ready!")

    def _on_disconnect(self, client: BleakClient, disconnected: bool):
        logger.warning(f"Device disconnected: {disconnected}")

    def _handle_photo_data(self, sender, data: bytearray):
        if len(data) < 2:
            return

        frame_num = struct.unpack("<H", data[:2])[0]

        if frame_num == 0xFFFF:
            logger.info(f"Photo complete: {len(self._photo_data)} bytes")
            if self._on_photo:
                self._on_photo(bytes(self._photo_data))
            self._photo_data.clear()
        else:
            self._photo_data.extend(data[2:])

    def _handle_audio_data(self, sender, data: bytearray):
        if self._on_audio:
            self._on_audio(bytes(data))

    async def take_photo(self):
        """拍摄单张照片"""
        logger.info("Sending command: TAKE_PHOTO (0xFF)")
        await self.client.write_gatt_char(PHOTO_CONTROL_UUID, bytes([255]))
        logger.info("✓ Command sent")

    async def start_photo_timelapse(self, interval_seconds: int):
        """启动间隔拍照"""
        value = (interval_seconds // 5) * 5
        if value < 5:
            value = 5
        if value > 300:
            value = 300
        logger.info(f"Starting timelapse: {value}s interval")
        await self.client.write_gatt_char(PHOTO_CONTROL_UUID, bytes([value]))

    async def stop_photos(self):
        """停止拍照"""
        logger.info("Sending command: STOP (0x00)")
        await self.client.write_gatt_char(PHOTO_CONTROL_UUID, bytes([0]))

    async def get_services(self):
        """获取所有服务和特征"""
        logger.info("Fetching services...")
        services = self.client.services
        for service in services:
            logger.info(f"  Service: {service.uuid}")
            for char in service.characteristics:
                logger.info(f"    Char: {char.uuid} ({', '.join(char.properties)})")

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected")


async def main():
    client = OpenGlassClient()

    while True:
        device = await client.discover()
        if not device:
            logger.info("OpenGlass not found, retrying in 3s...")
            await asyncio.sleep(3)
            continue

        try:
            await client.connect(device)
            break
        except Exception as e:
            logger.error(f"Connection failed: {e}, retrying...")
            await asyncio.sleep(2)
            continue

    try:
        await client.get_services()

        def on_photo(jpeg_data: bytes):
            logger.info(f"Received photo: {len(jpeg_data)} bytes")
            with open("photo.jpg", "wb") as f:
                f.write(jpeg_data)
            logger.info("✓ Saved photo.jpg")

        client._on_photo = on_photo

        logger.info("Taking photo...")
        await client.take_photo()

        logger.info("Waiting 5 seconds...")
        await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
