# xArm controller prototypes

Prototype scripts `XARM_Controller1.py`, `XARM_ContJoint.py` and `xarm_pos_read.py` were previously nested under an MG400 keyboard folder despite controlling the xArm. The integrated controller/drawer app was placed in its own separate project.

## Why this controller work followed MG400

The author reports that the MG400 Xbox controller app worked, and `FinalControllerAPP.py` is probably the last used version. However, the MG400's one-axis-at-a-time `MoveJog` joystick workflow was not sufficiently smooth for manual control of two or more axes. The author moved to xArm 850 / UF850 **specifically to pursue better simultaneous multi-axis joystick motion**. The MG400 limitation is not a claim that the robot cannot carry out any multi-axis planned trajectory; it describes the tested manual jog experience. Whether and which xArm variant fulfilled that aim is to be established in the xArm source review.

See [MG400 controller history](../../MG400/controller/).
