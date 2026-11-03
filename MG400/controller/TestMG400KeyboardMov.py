from dobot_api import DobotApiDashboard, DobotApiMove

ROBOT_IP = "192.168.2.6"

dashboard = DobotApiDashboard(ROBOT_IP, 29999)
move = DobotApiMove(ROBOT_IP, 30003)

dashboard.ClearError()
dashboard.EnableRobot()

move.MoveJog("X+")