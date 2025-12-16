import numpy as np


class Pose:
    """Simple 6DoF pose"""

    def __init__(self, orientation: tuple[float, float, float], position: tuple[float, float, float]):
        self.orientation = np.array(orientation, dtype=np.float64)
        self.position = np.array(position, dtype=np.float64)

    def add_angle_delta(self, angle_delta):
        # VISION_POSITION_DELTA.angle_delta should be radians, but there's a bug in the WL A50 DVL extension:
        # https://github.com/bluerobotics/BlueOS-Water-Linked-DVL/issues/36
        is_degrees = False
        if is_degrees:
            self.orientation += angle_delta
        else:
            self.orientation += np.degrees(angle_delta)

        # Normalize to [-180, 180)
        self.orientation = (self.orientation + 180) % 360 - 180

    def add_position_delta(self, position_delta):
        # VISION_POSITION_DELTA.position_delta is in meters, body frame

        # Convert orientation (degrees) to radians
        r, p, y = np.radians(self.orientation)

        cr, sr = np.cos(r), np.sin(r)
        cp, sp = np.cos(p), np.sin(p)
        cy, sy = np.cos(y), np.sin(y)

        # Body (FRD) to world (NED) rotation
        # R = Rz(y) * Ry(p) * Rx(r)
        R = np.array([
            [cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
            [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
            [-sp,     sr * cp,                cr * cp]
        ])

        # Rotate the delta
        self.position += R @ position_delta
