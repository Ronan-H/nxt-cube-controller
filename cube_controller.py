import sys
from enum import Enum

import nxt.locator
import nxt.motcont
import nxt.motor
from time import sleep
from pyjoystick.sdl2 import Key, run_event_loop
import queue
import threading

claw_motor_port = nxt.motor.Port.A
table_motor_port = nxt.motor.Port.B

quarter_turn_degrees = 270
double_turn_degrees = quarter_turn_degrees * 2

max_input_queue_size = 1

motor_power=100
claw_hold_rotation=-100
claw_full_flip_rotation=-195

action_queue = queue.Queue()


class RobotAction(Enum):
    CLEAR_ACTION_QUEUE, EXIT, LEFT_ROT, RIGHT_ROT, DOUBLE_ROT, CLAW_HOLD, CLAW_UNHOLD, CLAW_FLIP = range(8)


ps3_button_down_mapping = {
    1: RobotAction.CLEAR_ACTION_QUEUE,
    2: RobotAction.EXIT,

    7: RobotAction.LEFT_ROT,
    5: RobotAction.RIGHT_ROT,

    10: RobotAction.DOUBLE_ROT,
    11: RobotAction.CLAW_HOLD,

    12: RobotAction.CLAW_FLIP,
    13: RobotAction.CLAW_FLIP,
    14: RobotAction.CLAW_FLIP,
    15: RobotAction.CLAW_FLIP,
}

ps3_button_up_mapping = {
    10: RobotAction.CLAW_UNHOLD,
    11: RobotAction.CLAW_UNHOLD,
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
                b = nxt.locator.find(backends=['usb'])
            except Exception as e:
                print(e)
                sleep(0.1)
        print('Found a brick!')
        return b

    def wait_for_motors(self):
        motors = (claw_motor_port, table_motor_port)
        while not all(self.mc.is_ready(motor) for motor in motors):
            sleep(0.1)

    def rotate_motor(self, port: nxt.motor.Port, degrees):
        relative_power = self.motor_power if degrees > 0 else -self.motor_power
        self.mc.cmd(port, relative_power, abs(degrees), smoothstart=True, brake=True, speedreg=False)
        self.wait_for_motors()

    def stop(self):
        self.mc.stop()


class RobotController:
    def __init__(self, motor_power, claw_hold_rotation, claw_full_flip_rotation):
        self.table_rotation = 0 # degrees, in the range 0 - 270 (360 would be represented as 0)
        self.is_claw_holding = False
        self.claw_hold_rotation = claw_hold_rotation
        self.claw_full_flip_rotation = claw_full_flip_rotation
        self.claw_hold_flip_rotation = self.claw_full_flip_rotation - self.claw_hold_rotation
        self.nxt = Nxt(motor_power)

    def exec_action(self, action: RobotAction):
        print('Executing action:', action.name)

        if action == RobotAction.LEFT_ROT:
            self.rotate_table_acw()
        elif action == RobotAction.RIGHT_ROT:
            self.rotate_table_cw()
        elif action == RobotAction.DOUBLE_ROT:
            self.rotate_table_double()
        elif action == RobotAction.CLAW_HOLD:
            self.exec_claw_hold_action()
        elif action == RobotAction.CLAW_UNHOLD:
            self.exec_claw_unhold_action()
        elif action == RobotAction.CLAW_FLIP:
            self.exec_claw_flip_action()

        print('New table rotation:', self.table_rotation)

    def exec_table_rotation(self, degrees):
        self.nxt.rotate_motor(table_motor_port, degrees)
        self.table_rotation += degrees

    def rotate_table_cw(self):
        self.exec_table_rotation(quarter_turn_degrees)

    def rotate_table_acw(self):
        self.exec_table_rotation(-quarter_turn_degrees)

    def rotate_table_double(self):
        self.exec_table_rotation(double_turn_degrees)

    def exec_claw_hold_action(self):
        if not self.is_claw_holding:
            self.nxt.rotate_motor(claw_motor_port, self.claw_hold_rotation)
            self.is_claw_holding = True

    def exec_claw_unhold_action(self):
        if self.is_claw_holding:
            self.nxt.rotate_motor(claw_motor_port, -self.claw_hold_rotation)
            self.is_claw_holding = False

    def exec_claw_flip_action(self):
        was_holding = self.is_claw_holding

        self.exec_claw_hold_action()

        self.nxt.rotate_motor(claw_motor_port, self.claw_hold_flip_rotation)

        if was_holding:
            # return to holding position
            self.nxt.rotate_motor(claw_motor_port, -self.claw_hold_flip_rotation)
        else:
            # fully retract claw arm
            self.nxt.rotate_motor(claw_motor_port, -self.claw_full_flip_rotation)
            self.is_claw_holding = False


robot = RobotController(
    motor_power=100,
    claw_hold_rotation=-100,
    claw_full_flip_rotation=-210
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
        if action_queue.qsize() >= max_input_queue_size:
            return

        key_str = str(key)
        if key_str.startswith('Button '):
            button = int(key_str[7:])
            print('button:', button, 'val:', key.get_value())
            if key.get_value() == 0:
                if button in ps3_button_up_mapping:
                    action = ps3_button_up_mapping.get(button)
                    process_action(action)
            elif key.get_value() == 1:
                if button in ps3_button_down_mapping:
                    action = ps3_button_down_mapping.get(button)
                    process_action(action)

    run_event_loop(
        lambda c: print('Controller added:', c),
        lambda c: print('Controller removed:', c),
        lambda key: on_input_received(key)
    )


def action_consumer():
    while True:
        next_action = action_queue.get()
        robot.exec_action(next_action)


threading.Thread(target=action_consumer, daemon=True).start()

init_ps3_controller_events()

