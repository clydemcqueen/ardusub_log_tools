
import numpy as np
import pytest
from geometry import Pose

def test_initialization():
    orientation = (10.0, 20.0, 30.0)
    position = (1.0, 2.0, 3.0)
    pose = Pose(orientation, position)
    
    np.testing.assert_array_equal(pose.orientation, np.array(orientation))
    np.testing.assert_array_equal(pose.position, np.array(position))

def test_add_angle_delta_no_wrap():
    # Initial: 10, 20, 30 degrees
    pose = Pose((10.0, 20.0, 30.0), (0.0, 0.0, 0.0))
    
    # Delta: 0.1 radians ~ 5.7 degrees
    delta = np.array([0.1, 0.1, 0.1])
    pose.add_angle_delta(delta)
    
    expected_degrees = np.array([10.0, 20.0, 30.0]) + np.degrees(delta)
    np.testing.assert_array_almost_equal(pose.orientation, expected_degrees)

def test_add_angle_delta_wrapping():
    # Initial near boundary: 179 degrees
    pose = Pose((179.0, 179.0, 179.0), (0.0, 0.0, 0.0))
    
    # Add small amount to cross 180
    # 2 degrees in radians
    delta_deg = 2.0
    delta_rad = np.radians(delta_deg)
    delta = np.array([delta_rad, delta_rad, delta_rad])
    
    pose.add_angle_delta(delta)
    
    # 179 + 2 = 181 -> -179
    expected = -179.0
    np.testing.assert_almost_equal(pose.orientation[0], expected)
    np.testing.assert_almost_equal(pose.orientation[1], expected)
    np.testing.assert_almost_equal(pose.orientation[2], expected)

    # Test negative wrapping
    pose = Pose((-179.0, -179.0, -179.0), (0.0, 0.0, 0.0))
    # Subtract 2 degrees
    delta = np.array([-delta_rad, -delta_rad, -delta_rad])
    pose.add_angle_delta(delta)
    
    # -179 - 2 = -181 -> 179
    expected = 179.0
    np.testing.assert_almost_equal(pose.orientation[0], expected)
    np.testing.assert_almost_equal(pose.orientation[1], expected)
    np.testing.assert_almost_equal(pose.orientation[2], expected)

def test_add_position_delta_identity_rotation():
    # 0 rotation
    pose = Pose((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    delta = np.array([1.0, 0.0, 0.0])
    
    pose.add_position_delta(delta)
    
    # Should just add to X
    expected_pos = np.array([2.0, 2.0, 3.0])
    np.testing.assert_array_almost_equal(pose.position, expected_pos)

def test_add_position_delta_yaw_90():
    # 90 degrees yaw
    pose = Pose((0.0, 0.0, 90.0), (0.0, 0.0, 0.0))
    
    # Move forward in body X
    delta = np.array([1.0, 0.0, 0.0])
    
    pose.add_position_delta(delta)
    
    # Body X is now Earth Y because of 90 deg yaw
    # Rotated vector should be roughly [0, 1, 0]
    expected_pos = np.array([0.0, 1.0, 0.0])
    np.testing.assert_array_almost_equal(pose.position, expected_pos)

def test_add_position_delta_pitch_90():
    # 90 degrees pitch (nose up)
    pose = Pose((0.0, 90.0, 0.0), (0.0, 0.0, 0.0))
    
    # Move forward in body X
    delta = np.array([1.0, 0.0, 0.0])
    
    pose.add_position_delta(delta)
    
    # Body X is now Earth -Z (up)
    # Wait, NED frame: Z is down.
    # Pitch 90 nose up: Body X aligns with Earth -Z.
    expected_pos = np.array([0.0, 0.0, -1.0])
    np.testing.assert_array_almost_equal(pose.position, expected_pos)

def test_add_position_delta_roll_90():
    # 90 degrees roll (right wing down)
    pose = Pose((90.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    
    # Move right in body Y
    delta = np.array([0.0, 1.0, 0.0])
    
    pose.add_position_delta(delta)
    
    # Roll 90: Body Y aligns with Earth Z (down)
    expected_pos = np.array([0.0, 0.0, 1.0])
    np.testing.assert_array_almost_equal(pose.position, expected_pos)
