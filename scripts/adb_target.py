"""Select only the explicitly authorized ADB target, regardless of other devices."""


def authorized_target(serial, devices_output):
    if not isinstance(serial, str) or not serial or any(c.isspace() for c in serial):
        raise ValueError('An explicitly configured device serial is required')
    matches = [line.split() for line in devices_output.splitlines()
               if line.split() and line.split()[0] == serial]
    if len(matches) != 1 or len(matches[0]) < 2 or matches[0][1] != 'device':
        raise ValueError('Configured device is not connected and authorized')
    return serial
