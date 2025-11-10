"""
Station Controller
Manages station processing with state machine
"""

import logging
import time
from enum import Enum #For named constants group
from threading import Thread, Event # For simultaneously run the station control loop in the background

class StationState(Enum):
    """Station's possible states"""
    IDLE = "idle"
    ADVANCING_TO_PROCESS = "advancing_to_process"
    PROCESSING = "processing"
    ADVANCING_TO_EXIT = "advancing_to_exit"
    EXITING = "exiting"


class StationController:
    """
    Controls a single station

    State machine loop:
    IDLE to ADVANCING_TO_PROCESS to PROCESSING to ADVANCING_TO_EXIT to EXITING back to IDLE

    """

    def __init__(self, station_num, motors, sensors, nfc, data_logger, config):
        """
        Initialize station controller
        """
        self.logger = logging.getLogger(f"Station{station_num}")
        self.station_num = station_num
        self.station_id = f"S{station_num}"

        # References to subsystems
        self.motors = motors
        self.sensors = sensors
        self.nfc = nfc
        self.data_logger = data_logger

        # Configuration
        self.config = config
        self.process_time = config['stations'][f'station{station_num}_process_time']

        # Determine motor speed and direction based on station number
        if self.station_num == 1:
            # Station 1 (M3) moves down (forward)
            self.motor_speed = config['motors']['station_speed']
        else:
            # Station 2 (M4) must move up (reverse)
            self.motor_speed = -config['motors']['station_speed']

        # Assign motor number (Motor 3 for Station 1, Motor 4 for Station 2)
        self.motor_num = 2 + station_num

        # Initial state always IDLE and not processing anything
        self.state = StationState.IDLE
        self.current_part = None
        self.queue = []

        # Background thread control
        self.running = False
        self.stop_event = Event()
        self.thread = None

        self.logger.info(f"Station {station_num} initialized")

    def start(self):
        """Start station control thread"""
        if self.running:
            return      # Don't start again if already running

        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._run, daemon=True) # Daemon thread to exit with main program
        self.thread.start()
        self.logger.info(f"Station {self.station_num} started")

    def stop(self):
        """Stop station control thread"""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        self.motors.stop(self.motor_num) # Ensure station motor is stopped
        self.logger.info(f"Station {self.station_num} stopped")

    def _run(self):
        """Main station control loop"""
        self.logger.info(f"Station {self.station_num} control loop started")

        while self.running and not self.stop_event.is_set():
            try:
                # State machine logic
                if self.state == StationState.IDLE:
                    self._state_idle()

                elif self.state == StationState.ADVANCING_TO_PROCESS:
                    self._state_advancing_to_process()

                elif self.state == StationState.PROCESSING:
                    self._state_processing()

                elif self.state == StationState.ADVANCING_TO_EXIT:
                    self._state_advancing_to_exit()

                elif self.state == StationState.EXITING:
                    self._state_exiting()

                time.sleep(0.05)  # Small delay for loop iteration

            except Exception as e:
                self.logger.error(f"Error in control loop: {e}", exc_info=True)
                self.motors.stop(self.motor_num)
                time.sleep(1)

    def _state_idle(self):
        """Idle state - waiting for part at entry sensor"""

        # Check if part at entry
        entry_sensor_check = self.sensors.station1_entry() if self.station_num == 1 else self.sensors.station2_entry()

        if entry_sensor_check:
            self.logger.info("Part detected at entry. Reading NFC tag...")

            # Read the NFC tag while the sensor is blocked
            tag_uid = self.nfc.read_tag(timeout=2.0)  # 2 second read timeout

            # Re-check sensor: is the part STILL there after the read?
            entry_sensor_check_after = self.sensors.station1_entry() if self.station_num == 1 else self.sensors.station2_entry()

            if not entry_sensor_check_after:
                self.logger.warning("Part detected but disappeared during NFC read. Resetting.")
                return  # Stay in IDLE state

            if tag_uid:
                # Create part object
                from nfc_reader import Part
                self.current_part = Part(tag_uid)
                self.logger.info(f"Part identified: {tag_uid}")
            else:
                # Generate part ID if no tag
                from nfc_reader import Part
                part_id = f"P{int(time.time() * 1000) % 10000}"
                self.current_part = Part(part_id)
                self.logger.warning(f"No NFC tag - generated ID: {part_id}")

            # Log ENTER event
            self.data_logger.log_event(
                self.current_part.part_id,
                self.station_id,
                "ENTER"
            )
            self.current_part.add_event(self.station_id, "ENTER")

            # Advance to process
            self.state = StationState.ADVANCING_TO_PROCESS

    def _state_advancing_to_process(self):
        """Advancing part to process position"""
        self.logger.info("Advancing to process position...")
        self.motors.set_speed(self.motor_num, self.motor_speed)

        # Wait for process sensor
        sensor_triggered = False
        if self.station_num == 1:
            sensor_triggered = self.sensors.wait_for_pi(
                self.sensors.STATION1_PROCESS,
                timeout=10
            )
        else:
            sensor_triggered = self.sensors.wait_for_pi(
                self.sensors.STATION2_PROCESS,
                timeout=10
            )

        self.motors.stop(self.motor_num)

        if sensor_triggered:
            self.logger.info("Part at process position")
            self.state = StationState.PROCESSING
        else:
            self.logger.error("Timeout waiting for process sensor")
            self.data_logger.log_event(
                self.current_part.part_id,
                self.station_id,
                "ERROR_TIMEOUT_PROCESS"
            )
            self.current_part = None
            self.state = StationState.IDLE

    def _state_processing(self):
        """Processing part"""
        self.logger.info(f"Processing for {self.process_time}s...")

        # Wait for the defined "processing" time
        time.sleep(self.process_time)

        self.logger.info("Processing complete")
        self.state = StationState.ADVANCING_TO_EXIT

    def _state_advancing_to_exit(self):
        """Advancing part to exit"""
        self.logger.info("Advancing to exit...")
        self.motors.set_speed(self.motor_num, self.motor_speed)

        # Wait for exit sensor
        sensor_triggered = False
        if self.station_num == 1:
            sensor_triggered = self.sensors.wait_for_pi(
                self.sensors.STATION1_EXIT,
                timeout=10
            )
        else:
            sensor_triggered = self.sensors.wait_for_pi(
                self.sensors.STATION2_EXIT,
                timeout=10
            )

        self.motors.stop(self.motor_num)

        if sensor_triggered:
            self.logger.info("Part at exit")
            self.state = StationState.EXITING
        else:
            self.logger.error("Timeout waiting for exit sensor")
            self.data_logger.log_event(
                self.current_part.part_id,
                self.station_id,
                "ERROR_TIMEOUT_EXIT"
            )
            self.current_part = None
            self.state = StationState.IDLE

    def _state_exiting(self):
        """Exiting part from station"""
        # Run motor briefly to clear the sensor
        self.motors.set_speed(self.motor_num, self.motor_speed)

        # Wait for sensor to clear with timeout
        start_time = time.time()
        timeout = 5.0

        exit_sensor = (self.sensors.station1_exit if self.station_num == 1
                       else self.sensors.station2_exit)

        while time.time() - start_time < timeout:
            if not exit_sensor():  # Sensor cleared
                time.sleep(0.5)  # Brief extra time to ensure part is fully clear
                break
            time.sleep(0.1)

        self.motors.stop(self.motor_num)

        # Log EXIT event
        if self.current_part:
            self.data_logger.log_event(
                self.current_part.part_id,
                self.station_id,
                "EXIT"
            )
            self.current_part.add_event(self.station_id, "EXIT")
            self.logger.info(f"Part {self.current_part.get_short_id()} completed")

        # Reset the station
        self.current_part = None
        self.state = StationState.IDLE