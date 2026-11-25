import enum

from libcamera.controls import draft as draft

class AeFlickerModeEnum(enum.IntEnum):
    Off = 0
    Manual = 1
    Auto = 2
