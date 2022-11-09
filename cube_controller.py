import sys
from enum import Enum

import nxt.locator
import nxt.motcont
import nxt.motor
from time import sleep
from pyjoystick.sdl2 import Key, run_event_loop
import queue
import threading

action_queue = queue.Queue()


class RobotAction(Enum):
    CLEAR_ACTION_QUEUE, EXIT, LEFT_ROT, RIGHT_ROT, CLAW_HOLD, CLAW_FLIP = range(6)


ps3_button_mapping = {
    1: RobotAction.CLEAR_ACTION_QUEUE,
    2: RobotAction.EXIT,

    7: RobotAction.LEFT_ROT,
    5: RobotAction.RIGHT_ROT,

    10: RobotAction.CLAW_HOLD,
    11: RobotAction.CLAW_HOLD,

    12: RobotAction.CLAW_FLIP,
    13: RobotAction.CLAW_FLIP,
    14: RobotAction.CLAW_FLIP,
    15: RobotAction.CLAW_FLIP,
}


class Nxt:
    def __init__(self, motor_power):
        self.motor_power = motor_power
        self.brick = self.find_brick()
        self.mc = nxt.motcont.MotCont(self.brick)
        self.mc.start()

    @staticmethod
    def find_brick():
        b = None
        while b is None:
            try:
                b = nxt.locator.find()
            except Exception as e:
                print(e)
        return b

    def wait_for_motors(self):
        motors = (nxt.motor.Port.A, nxt.motor.Port.B, nxt.motor.Port.C)
        while not all(self.mc.is_ready(motor) for motor in motors):
            sleep(0.1)

    def rotate_motor(self, port: nxt.motor.Port, degrees):
        relative_power = self.motor_power if degrees > 0 else -self.motor_power
        self.mc.cmd(port, relative_power, abs(degrees), smoothstart=False, brake=True)

    def stop(self):
        self.mc.stop()


class RobotController:
    def __init__(self, motor_power, claw_hold_rotation, claw_flip_rotation):
        self.table_rotation = 0 # degrees, in the range 0 - 270 (360 would be represented as 0)
        self.is_claw_holding = False
        self.claw_hold_rotation = claw_hold_rotation
        self.claw_flip_rotation = claw_flip_rotation
        self.nxt = Nxt(motor_power)

    def exec_action_and_wait(self, action: RobotAction):
        print('Executing action:', action.name)

        if action == RobotAction.LEFT_ROT:
            self.rotate_table_acw()
        elif action == RobotAction.RIGHT_ROT:
            self.rotate_table_cw()
        elif action == RobotAction.CLAW_HOLD:
            self.exec_claw_hold_action()
        elif action == RobotAction.CLAW_FLIP:
            self.exec_claw_flip_action()

        print('New table rotation:', self.table_rotation)

        self.nxt.wait_for_motors()

    def exec_table_rotation(self, degrees):
        self.nxt.rotate_motor(nxt.motor.Port.A, degrees)
        self.table_rotation += degrees

    def rotate_table_cw(self):
        if self.table_rotation >= 270:
            self.exec_table_rotation(-270)
        else:
            self.exec_table_rotation(90)

    def rotate_table_acw(self):
        if self.table_rotation <= 0:
            self.exec_table_rotation(270)
        else:
            self.exec_table_rotation(-90)

    def exec_claw_hold_action(self):
        if self.is_claw_holding:
            self.retract_claw()
            self.is_claw_holding = False
        else:
            self.extend_claw()
            self.is_claw_holding = True

    def extend_claw(self):
        self.nxt.rotate_motor(nxt.motor.Port.B, self.claw_hold_rotation)

    def retract_claw(self):
        self.nxt.rotate_motor(nxt.motor.Port.B, -self.claw_hold_rotation)

    def exec_claw_flip_action(self):
        self.nxt.rotate_motor(nxt.motor.Port.B, self.claw_flip_rotation)
        self.nxt.rotate_motor(nxt.motor.Port.B, -self.claw_flip_rotation)


robot = RobotController(
    motor_power=50,
    claw_hold_rotation=75, # TODO: find the right value for this
    claw_flip_rotation=90 # TODO: find the right value for this
)


def process_action(action: RobotAction):
    if action == RobotAction.CLEAR_ACTION_QUEUE:
        with action_queue.mutex:
            action_queue.queue.clear()
    elif action == RobotAction.EXIT:
        robot.nxt.stop()
        sys.exit()
    else:
        action_queue.put(action)


def init_ps3_controller_events():
    def on_input_received(key: Key):
        key_str = str(key)
        if key.get_value() == 1 and key_str.startswith('Button '):
            button = int(key_str[7:])
            print('button:', button, 'val:', key.get_value())
            if button in ps3_button_mapping:
                action = ps3_button_mapping.get(button)
                process_action(action)

    run_event_loop(
        lambda c: print('Controller added:', c),
        lambda c: print('Controller removed:', c),
        lambda key: on_input_received(key)
    )


def action_consumer():
    while True:
        next_action = action_queue.get()
        robot.exec_action_and_wait(next_action)


threading.Thread(target=action_consumer, daemon=True).start()

init_ps3_controller_events()

