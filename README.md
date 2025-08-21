# Thorlab Control Kit
## Motorized Stage Control
All examples are built using the libraries provided with Thorlabs' Kinesis software package, which can be found [here](https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=Motion_Control&viewtab=0). 

After install the Motion Control software by default, please test
'''python
os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")
lib: CDLL = cdll.LoadLibrary(
    "Thorlabs.MotionControl.KCube.DCServo.dll"
)
'''
to see if the dll is at the right location.

### Example kdc101
'''python
serial_num = c_char_p(b"27007518")
STEPS_PER_REV = c_double(34555)  # for the PRM1-Z8
gbox_ratio = c_double(1.0)
pitch = c_double(1.0)
pos_min = 0
pos_max = 25
'''
serial_num can be lookup through the Motion Control software
STEPS_PER_REV can be lookup from the manual of the equipment, which means how many full steps a stepper motor takes to turn exactly one full revolution (360°).

## Power Meter Control
TLPMX.py gives all the functions related to Power Meter Control. Please make sure this file is correctly imported by the main file, which link the c code with Python code.

## References
See the Reference https://github.com/Thorlabs
