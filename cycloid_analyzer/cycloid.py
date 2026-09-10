from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin


Point = tuple[float, float]


@dataclass(frozen=True)
class CycloidParameters:
    radius: float = 40.0
    frequency: float = 2.0
    phase_degrees: float = 0.0
    samples: int = 240

    @property
    def phase_radians(self) -> float:
        return (self.phase_degrees / 180.0) * pi


def generate_cycloid_points(start: Point, end: Point, parameters: CycloidParameters) -> list[Point]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = hypot(dx, dy)
    if length == 0:
        return [start]

    sample_count = max(24, int(parameters.samples))
    t_end = max(0.25, parameters.frequency) * (2.0 * pi)
    phase = parameters.phase_radians
    theta = atan2(dy, dx)

    raw_points: list[Point] = []
    min_x = float("inf")
    max_x = float("-inf")
    for index in range(sample_count):
        progress = index / (sample_count - 1)
        t = progress * t_end
        x = t - sin(t + phase)
        y = (1.0 - cos(t + phase)) - (1.0 - cos(phase))
        raw_points.append((x, y))
        min_x = min(min_x, x)
        max_x = max(max_x, x)

    x_span = max(max_x - min_x, 1e-9)
    result: list[Point] = []
    for raw_x, raw_y in raw_points:
        local_x = ((raw_x - min_x) / x_span) * length
        local_y = raw_y * parameters.radius
        world_x = start[0] + (local_x * cos(theta) - local_y * sin(theta))
        world_y = start[1] + (local_x * sin(theta) + local_y * cos(theta))
        result.append((world_x, world_y))
    return result

