"""
Data Logger
Logs events and calculates KPIs

Event format: {timestamp, part_id, station_id, activity}

"""

import logging
import csv # For spreadsheets
import os # For creating directories and checking if files exist
from datetime import datetime
from threading import Lock # For preventing file corruption in case of same time processes


class DataLogger:
    """
    Logs system events and calculates KPIs

    Event format matches requirements:
        Time | Station ID | Part ID | Activity
    """

    def __init__(self, log_file="data/events.csv"):
        """
        Initialize data logger

        log_file: Path to CSV log file
        """
        self.logger = logging.getLogger("DataLogger")
        self.log_file = log_file
        self.lock = Lock()

        # Create data directory if needed or do nothing if it exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Create CSV file with headers if it doesn't exist
        if not os.path.exists(log_file):
            self._create_csv()

        self.logger.info(f"Data logger initialized: {log_file}")

        # KPI tracking initialization as a dictionary
        self.kpis = {
            'total_parts': 0,
            'station1_count': 0,
            'station2_count': 0,
            'total_process_time': 0,
            'total_queue_time': 0
        }

    def _create_csv(self):
        """Create CSV file with headers"""
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'Station ID', 'Part ID', 'Activity'])
        self.logger.info("Created new event log file")

    def log_event(self, part_id, station_id, activity):
        """
        Log an event
            part_id: Part ID (e.g., "P001", "04a1b2c3d4e5f6")

            station_id: Station ID (e.g., "S1", "S2", "C1", "C2", "C3", "C4")

            activity: Activity type (e.g., "ENTER", "EXIT", "PROCESS")

        """
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.lock:
            # Write to CSV
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, station_id, part_id, activity])

            # Log to console
            self.logger.info(f"Event: {timestamp} | {station_id} | {part_id} | {activity}")

            # Update KPIs
            self._update_kpis(station_id, activity)

    def _update_kpis(self, station_id, activity):
        """Update KPI counters"""
        if activity == "EXIT":
            self.kpis['total_parts'] += 1
            if station_id == "S1":
                self.kpis['station1_count'] += 1
            elif station_id == "S2":
                self.kpis['station2_count'] += 1

    def get_kpis(self):
        """
        Gets a current copy of the KPIs for other modules functions

        Returns:
            dict: KPI dictionary
        """
        return self.kpis.copy()

    def print_kpis(self):
        """Print KPIs to console"""
        print("\n" + "=" * 50)
        print("SYSTEM KPIs")
        print("=" * 50)
        print(f"Station 1 processed: {self.kpis['station1_count']}")
        print(f"Station 2 processed: {self.kpis['station2_count']}")
        print(f"Total parts: {self.kpis['total_parts']}")
        print("=" * 50 + "\n")