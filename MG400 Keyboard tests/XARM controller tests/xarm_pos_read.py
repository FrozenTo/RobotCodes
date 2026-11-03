from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

arm = XArmAPI(ROBOT_IP, is_radian=False)
arm.connect()

code_j, joints = arm.get_servo_angle(is_radian=False)
code_p, pose = arm.get_position(is_radian=False)

print()
print("JOINTS:")
print(joints)

print()
print("TCP:")
print(pose)

arm.disconnect()