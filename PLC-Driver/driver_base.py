"""
PLC 驱动抽象基类
所有具体 PLC 驱动（Modbus、S7、三菱等）均继承此基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class DriverType(Enum):
    MODBUS_TCP = "Modbus TCP"
    MODBUS_RTU = "Modbus RTU"
    SIEMENS_S7 = "Siemens S7"
    MITSUBISHI_MC = "Mitsubishi MC"
    OMROM_FINS = "Omron FINS"


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TagInfo:
    """数据标签定义"""
    name: str
    address: int
    data_type: str = "int16"  # int16, uint16, int32, float32, bool, string
    read_only: bool = False
    description: str = ""
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""


@dataclass
class ConnectionConfig:
    """连接配置"""
    driver_type: DriverType = DriverType.MODBUS_TCP
    host: str = "127.0.0.1"
    port: int = 502
    unit_id: int = 1
    serial_port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    timeout: float = 2.0
    retries: int = 3


@dataclass
class DataPoint:
    """采集的数据点"""
    tag: TagInfo
    value: Any = None
    raw_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    quality: bool = True
    error: str = ""


@dataclass
class PLCInfo:
    """PLC 设备信息"""
    vendor: str = ""
    model: str = ""
    firmware: str = ""
    cpu_status: str = "Unknown"


class PLCDriver(ABC):
    """PLC 驱动抽象基类"""

    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._tags: list[TagInfo] = []
        self._error_message: str = ""
        self._plc_info = PLCInfo()

    # ── 生命周期 ──────────────────────────────────

    @abstractmethod
    async def connect(self, config: ConnectionConfig) -> bool:
        """建立连接，返回是否成功"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        ...

    @abstractmethod
    async def read_register(self, address: int, count: int = 1) -> list[int]:
        """读取保持寄存器"""
        ...

    @abstractmethod
    async def write_register(self, address: int, value: int) -> bool:
        """写入单个保持寄存器"""
        ...

    @abstractmethod
    async def write_registers(self, address: int, values: list[int]) -> bool:
        """批量写入保持寄存器"""
        ...

    # ── 可选覆写 ─────────────────────────────────

    async def read_coil(self, address: int, count: int = 1) -> list[bool]:
        """读取线圈"""
        raise NotImplementedError

    async def write_coil(self, address: int, value: bool) -> bool:
        """写入单个线圈"""
        raise NotImplementedError

    async def read_discrete_input(self, address: int, count: int = 1) -> list[bool]:
        """读取离散输入"""
        raise NotImplementedError

    async def read_input_register(self, address: int, count: int = 1) -> list[int]:
        """读取输入寄存器"""
        raise NotImplementedError

    async def get_plc_info(self) -> PLCInfo:
        """获取 PLC 信息"""
        return self._plc_info

    async def get_cpu_status(self) -> str:
        """获取 CPU 运行状态"""
        return "Unknown"

    # ── 标签管理 ─────────────────────────────────

    def add_tag(self, tag: TagInfo):
        self._tags.append(tag)

    def remove_tag(self, name: str):
        self._tags = [t for t in self._tags if t.name != name]

    def get_tags(self) -> list[TagInfo]:
        return self._tags.copy()

    # ── 批量读取 ─────────────────────────────────

    async def read_all_tags(self) -> list[DataPoint]:
        """批量读取所有已配置标签"""
        results: list[DataPoint] = []
        for tag in self._tags:
            dp = DataPoint(tag=tag)
            try:
                raw = await self.read_register(tag.address)
                dp.raw_value = raw[0] if raw else None
                dp.value = dp.raw_value * tag.scale + tag.offset if dp.raw_value is not None else None
            except Exception as e:
                dp.quality = False
                dp.error = str(e)
            results.append(dp)
        return results

    # ── 属性 ─────────────────────────────────────

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def driver_type(self) -> DriverType:
        raise NotImplementedError
