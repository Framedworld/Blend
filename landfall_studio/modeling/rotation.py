"""Orientation edits that preserve the object's native rotation representation."""


def euler(obj):
    """Native Euler order, or an XYZ orientation view for four-component modes."""
    if obj.rotation_mode == 'QUATERNION':
        return obj.rotation_quaternion.to_euler('XYZ')
    if obj.rotation_mode == 'AXIS_ANGLE':
        from mathutils import Quaternion
        angle, *axis = obj.rotation_axis_angle
        return Quaternion(axis, angle).to_euler('XYZ')
    return obj.rotation_euler.copy()


def quaternion(obj):
    return euler(obj).to_quaternion()


def write_euler(obj, value):
    if obj.rotation_mode == 'QUATERNION':
        obj.rotation_quaternion = value.to_quaternion()
    elif obj.rotation_mode == 'AXIS_ANGLE':
        axis, angle = value.to_quaternion().to_axis_angle()
        obj.rotation_axis_angle = (angle, *axis)
    else:
        obj.rotation_euler = value


def set_component(obj, index, value):
    orientation = euler(obj)
    orientation[index] = value
    write_euler(obj, orientation)


def set_mode(obj, mode):
    orientation = quaternion(obj)
    obj.rotation_mode = mode
    if mode == 'QUATERNION':
        obj.rotation_quaternion = orientation
    elif mode == 'AXIS_ANGLE':
        axis, angle = orientation.to_axis_angle()
        obj.rotation_axis_angle = (angle, *axis)
    else:
        obj.rotation_euler = orientation.to_euler(mode)


def snapshot(obj):
    return (obj.rotation_mode, tuple(obj.rotation_euler),
            tuple(obj.rotation_quaternion), tuple(obj.rotation_axis_angle))


def restore(obj, saved):
    mode, angles, quat, axis = saved
    obj.rotation_mode = mode
    obj.rotation_euler = angles
    obj.rotation_quaternion = quat
    obj.rotation_axis_angle = axis
