import math
import threading
import time
from collections import deque
from typing import Callable

import numpy as np
from sklearn.metrics import pairwise_distances
from enum import Enum
from scipy.spatial.transform import Rotation as R

MIN_PID_WAYPOINT_DISTANCE = 1
STEER_GAIN = 0.7
COAST_FACTOR = 1.75
pid_p = 1.0
pid_d = 0.0
pid_i = 0.05
dt = 1.0 / 5
pid_use_real_time = True

BRAKE_MAX = 1.0
THROTTLE_MAX = 0.5



class DoraStatus(Enum):
    CONTINUE = 0
    STOP = 1


class Operator:
    """
    Compute a `control` based on the position and the waypoints of the car.
    """

    def __init__(self):
        self.waypoints = np.array([[0, 1.5], [3, 1.5]])
        # self.target_speeds = []
        self.metadata = {}
        self.position = []
        self.initial_orientation = None
        self.orientation = None

    def on_input(
        self,
        dora_input: dict,
        send_output: Callable[[str, bytes], None],
    ):
        """Handle input.
        Args:
            dora_input["id"](str): Id of the input declared in the yaml configuration
            dora_input["data"] (bytes): Bytes message of the input
            send_output (Callable[[str, bytes]]): Function enabling sending output back to dora.
        """

        if "position" == dora_input["id"]:
            if self.initial_orientation is not None:
                position = np.frombuffer(dora_input["data"])[:3]
                self.position = self.initial_orientation.apply(position)
                if position[0] >7 or position[1]>7:
                    return DoraStatus.STOP
                    
        elif "imu" == dora_input["id"]:
            data = np.frombuffer(dora_input["data"])
            [rx, ry, rz, rw, vx, vy, vz, ax, ay, az] = data
            rot = R.from_quat([rx, ry, rz, rw])

            if self.initial_orientation is None:
                self.initial_orientation = rot

            self.orientation = rot

            return DoraStatus.CONTINUE

        if len(self.position) == 0:
            return DoraStatus.CONTINUE
        
        [x, y, z] = self.position
        [_, _, yaw] = self.orientation.as_euler("xyz", degrees=True)
        distances = pairwise_distances(self.waypoints, np.array([[x, y]])).T[0]

        index = distances > MIN_PID_WAYPOINT_DISTANCE
        self.waypoints = self.waypoints[index]
        # self.target_speeds = self.target_speeds[index]
        distances = distances[index]

        if len(self.waypoints) == 0:
            target_angle = 0
            target_speed = 0
            self.waypoints = np.array([[0, 1]])
            return DoraStatus.STOP
        else:
            argmin_distance = np.argmin(distances)

            ## Retrieve the closest point to the steer distance
            target_location = self.waypoints[argmin_distance]

            # target_speed = self.target_speeds[argmin_distance]

            ## Compute the angle of steering
            target_vector = target_location - [x, y]
            target_abs_angle = math.atan2(target_vector[1], target_vector[0])
            angle = target_abs_angle - math.radians(yaw)
            if angle > math.pi:
                angle -= 2 * math.pi
            elif angle < -math.pi:
                angle += 2 * math.pi
    
        # throttle, brake = compute_throttle_and_brake(
        #     pid, current_speed, target_speed
        # )

        # steer = radians_to_steer(target_angle, STEER_GAIN)
        # print(f"position: {x, y, yaw}, target: {target_location}, vec: {target_vector}")
        # print(f"steer: angle: {target_angle} x: {np.cos(target_angle)}, y: {np.sin(target_angle)}")
        
        data = np.array([angle])
        print(f"abs: {math.degrees(target_abs_angle)}, rel: {math.degrees(angle)}, current: {(yaw)}")
        send_output("mavlink_control", data.tobytes() )
        return DoraStatus.CONTINUE
