"""
Modbus 驱动实现 (基于 pymodbus)
支持 Modbus TCP 和 Modbus RTU(串口)
"""
import asyncio
import logging
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient, AsyncModbusSerialClient
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.pdu import ExceptionResponse

from driver_base import (
    PLCDriver, ConnectionConfig, ConnectionState,
    DriverType, PLCInfo, TagInfo,
)

logger = logging.getLogger(__name__)


class ModbusDriver(PLCDriver):
    """Modbus 协议驱动"""

    def __init__(self, driver_type: DriverType = DriverType.MODBUS_TCP):
        super().__init__()
        self._driver_type = driver_type
        self._client: Optional[AsyncModbusTcpClient | AsyncModbusSerialClient] = None
        self._lock = asyncio.Lock()
        self._slave_id = 1

    @property
    def driver_type(self) -> DriverType:
        return self._driver_type

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.connected

    # ── 连接管理 ──────────────────────────────

    async def connect(self, config: ConnectionConfig) -> bool:
        self._state = ConnectionState.CONNECTING
        self._slave_id = config.unit_id

        try:
            if self._driver_type == DriverType.MODBUS_TCP:
                self._client = AsyncModbusTcpClient(
                    host=config.host,
                    port=config.port,
                    timeout=config.timeout,
                    retries=config.retries,
                )
            elif self._driver_type == DriverType.MODBUS_RTU:
                self._client = AsyncModbusSerialClient(
                    port=config.serial_port,
                    baudrate=config.baudrate,
                    timeout=config.timeout,
                    retries=config.retries,
                )
            else:
                self._error_message = f"不支持的驱动类型: {self._driver_type}"
                self._state = ConnectionState.ERROR
                return False

            connected = await self._client.connect()

            if connected:
                self._state = ConnectionState.CONNECTED
                self._error_message = ""
                logger.info(f"Modbus 连接成功: {config.host}:{config.port}")
                return True
            else:
                self._state = ConnectionState.ERROR
                self._error_message = "无法建立 Modbus 连接"
                return False

        except Exception as e:
            self._state = ConnectionState.ERROR
            self._error_message = f"连接失败: {e}"
            logger.error(f"Modbus 连接异常: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._state = ConnectionState.DISCONNECTED
        logger.info("Modbus 已断开")

    # ── 寄存器读写 ────────────────────────────

    async def read_register(self, address: int, count: int = 1) -> list[int]:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        if result.isError():
            raise ConnectionException(f"读取寄存器失败: {result}")

        return list(result.registers) if result.registers else []

    async def write_register(self, address: int, value: int) -> bool:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.write_register(
                    address=address,
                    value=value,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        return not result.isError()

    async def write_registers(self, address: int, values: list[int]) -> bool:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.write_registers(
                    address=address,
                    values=values,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        return not result.isError()

    # ── 线圈读写 ──────────────────────────────

    async def read_coil(self, address: int, count: int = 1) -> list[bool]:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.read_coils(
                    address=address,
                    count=count,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        if result.isError():
            raise ConnectionException(f"读取线圈失败: {result}")

        return list(result.bits[:count]) if result.bits else []

    async def write_coil(self, address: int, value: bool) -> bool:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.write_coil(
                    address=address,
                    value=value,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        return not result.isError()

    async def read_discrete_input(self, address: int, count: int = 1) -> list[bool]:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.read_discrete_inputs(
                    address=address,
                    count=count,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        if result.isError():
            raise ConnectionException(f"读取离散输入失败: {result}")

        return list(result.bits[:count]) if result.bits else []

    async def read_input_register(self, address: int, count: int = 1) -> list[int]:
        if not self.is_connected or self._client is None:
            raise ConnectionException("未连接到 PLC")

        async with self._lock:
            try:
                result = await self._client.read_input_registers(
                    address=address,
                    count=count,
                    slave=self._slave_id,
                )
            except ModbusIOException as e:
                raise ConnectionException(f"Modbus IO 错误: {e}") from e

        if result.isError():
            raise ConnectionException(f"读取输入寄存器失败: {result}")

        return list(result.registers) if result.registers else []
