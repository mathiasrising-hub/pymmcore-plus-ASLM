from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Optional

@dataclass(frozen=True)
class AcqConfig:
    # geometry
    z_depth: float                 # required by engine.setup_sequence
    z_stepsize: float              # maps to z_stepsize

    # tiling / acquisition structure
    x_tiles: int = 1
    y_tiles: int = 1
    meta: int = 1                  # whatever "meta" represents in your pipeline
    cameras: int = 1
    overlap: float = 5.0

    # channels: engine expects something with len() and iterable semantics
    channels: Sequence[str] = ("488",)

    # saving / naming
    saving: bool = True
    foldername: Optional[str] = 'Default'
    filename: Optional[str] = None
    save_path: Optional[Path] = None   # your engine currently ignores this (see note)

    # camera settings you likely want
    exposure_ms: Optional[float] = None  # requires adding support in engine
    trigger_mode: Optional[str] = None   # requires adding support in engine

    lag_limit: Optional[int] = None
    silence: Optional[bool] = None

    def validate(self) -> None:
        if self.z_depth <= 0:
            raise ValueError("z_depth must be > 0")
        if self.z_stepsize is None or self.z_stepsize <= 0:
            raise ValueError("z_stepsize must be > 0")
        if self.x_tiles <= 0 or self.y_tiles <= 0:
            raise ValueError("x_tiles/y_tiles must be >= 1")
        if self.meta <= 0:
            raise ValueError("meta must be >= 1")
        if self.cameras <= 0:
            raise ValueError("cameras must be >= 1")
        if not self.channels or len(self.channels) == 0:
            raise ValueError("At least one channel is required")