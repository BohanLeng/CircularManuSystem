"""
Sensor Reader
Reads all 18 sensors:
- 10 sensors on Pi's native GPIO (6 station + 4 corner)
- 8 sensors on a GPIO Expander (8 corner pusher limit switches)
"""

import logging
import time
from threading import Lock # For data corruption prevention

# Try to import hardware libraries
try:
    # Pi native GPIO
    import RPi.GPIO as GPIO

    # I2C and MCP23017 (GPIO Expander used in the project) libraries
    import board
    import busio
    import digitalio
    from adafruit_mcp230xx.mcp23017 import MCP23017

    # Library detection to ba able run with or without hardware as "Simulation mode"
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError, RuntimeError) as e:
    HARDWARE_AVAILABLE = False
    logging.warning(f"GPIO/I2C libraries not available, using simulation mode: {e}")


class SensorReader:
    """
    Manages all sensors in the system
    """
    """The GPIO pin numbers are random at the moment as they have not yet been specified."""
    # Pi-connected native GPIO Pins
    # Station 1
    STATION1_ENTRY = 17
    STATION1_PROCESS = 27
    STATION1_EXIT = 22

    # Station 2
    STATION2_ENTRY = 5
    STATION2_PROCESS = 6
    STATION2_EXIT = 13

    # Corner Position Sensors
    CORNER1_POS = 21
    CORNER2_POS = 12
    CORNER3_POS = 0
    CORNER4_POS = 1

    # List of all Pi-connected pins
    PI_PINS = [
        STATION1_ENTRY, STATION1_PROCESS, STATION1_EXIT,
        STATION2_ENTRY, STATION2_PROCESS, STATION2_EXIT,
        CORNER1_POS, CORNER2_POS, CORNER3_POS, CORNER4_POS
    ]

    # GPIO Expander Pins "lookup table"
    MCP_PIN_MAP = {
        'CORNER1_RET': 0,  # GPA0
        'CORNER2_RET': 1,  # GPA1
        'CORNER3_RET': 2,  # GPA2
        'CORNER4_RET': 3,  # GPA3
        'CORNER1_EXT': 4,  # GPA4
        'CORNER2_EXT': 5,  # GPA5
        'CORNER3_EXT': 6,  # GPA6
        'CORNER4_EXT': 7,  # GPA7
    }

    def __init__(self, simulation=False):
        """
        Initialize sensor reader
        """
        self.logger = logging.getLogger("SensorReader")
        self.simulation = simulation or not HARDWARE_AVAILABLE
        self.lock = Lock()
        self.mcp_pins = {}
        self.mcp = None

        if not self.simulation:
            try:
                # Setup Pi Native GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in self.PI_PINS:
                    # Sets the pin to be an input with a pull-up resistor
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                self.logger.info(f"Initialized {len(self.PI_PINS)} native GPIO sensors")

                # Setup MCP23017 Expander
                self.logger.info("Initializing MCP23017 GPIO expander...")
                i2c = busio.I2C(board.SCL, board.SDA)
                self.mcp = MCP23017(i2c) # Default address 0x20

                # Configure all 8 expander pins as inputs with pull-ups
                for name, pin_num in self.MCP_PIN_MAP.items():
                    pin = self.mcp.get_pin(pin_num)
                    pin.direction = digitalio.Direction.INPUT
                    pin.pull = digitalio.Pull.UP
                    self.mcp_pins[name] = pin # Save pin object into pins dictioanry using its name as key for easy access

                self.logger.info(f"Initialized {len(self.mcp_pins)} expander sensors")

            except Exception as e:
                self.logger.error(f"Failed to initialize hardware: {e}", exc_info=True)
                self.logger.error("Falling back to simulation mode")
                self.simulation = True
        else:
            self.logger.info("Running in SIMULATION mode")