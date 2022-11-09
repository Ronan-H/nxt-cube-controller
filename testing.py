#!/usr/bin/python3
"""NXT-Python tutorial: find the brick."""
import getch
import nxt.locator
import nxt.motcont
import nxt.motor
from time import sleep

# Find a brick.
b = None
while b is None:
    try:
        b = nxt.locator.find()
    except Exception as e:
        print(e)

# Once found, print its name.
print("Found brick:", b.get_device_info()[0])

motor_a = b.get_motor(nxt.motor.Port.A)
mc = nxt.motcont.MotCont(b)

mc.start()

def wait():
    while not mc.is_ready(nxt.motor.Port.A):
        sleep(0.25)

rot_delta = 90
expected_rotation = motor_a.get_tacho().tacho_count


def turn(power, rotation):
    global expected_rotation

    mc.cmd(nxt.motor.Port.A, power, rotation, smoothstart=True, brake=True)
    wait()

    relative_rotation = rotation * (1 if power > 0 else -1)
    expected_rotation += relative_rotation

    # tacho = motor_a.get_tacho()
    actual_rotation = b.get_output_state(nxt.motor.Port.A)[6]

    print('Expected:', expected_rotation, 'Actual:', actual_rotation)

    delta = expected_rotation - actual_rotation

    # if abs(delta) > 5:
    #     if delta > 0:
    #         mc.cmd(nxt.motor.Port.A, -10, abs(delta), smoothstart=True, brake=True)
    #     else:
    #         mc.cmd(nxt.motor.Port.A, 10, abs(delta), smoothstart=True, brake=True)

while True:
    key = getch.getche()
    print(f'Pressed: {key}')
    if key == 'q':
        break
    elif key == 'w':
        turn(75, rot_delta)
    elif key == 's':
        turn(-75, rot_delta)

mc.stop()
