"""
Data Manager
Handles storing Labcom data into SQLite database
"""
from typing import List, Dict, Optional
from datetime import datetime
import logging
from sqlalchemy.exc import IntegrityError

from db_schema import (
    DatabaseManager, Vessel, SamplingPoint, Parameter,
    Measurement, FetchLog, Alert, ParameterLimit
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataManager:
    """Manages data storage operations"""

    def __init__(self, db_path: str = '../data/accubase.sqlite'):
        """Initialize data manager"""
        self.db = DatabaseManager(db_path)
        self.db.create_tables()

    def add_or_update_vessel(
        self,
        vessel_id: str,
        vessel_name: str,
        email: str,
        auth_token: str,
        labcom_account_id: Optional[int] = None
    ) -> Vessel:
        """
        Add or update vessel information

        Args:
            vessel_id: Unique vessel identifier
            vessel_name: Vessel name
            email: Contact email
            auth_token: Labcom auth token
            labcom_account_id: Optional Labcom cloud account ID

        Returns:
            Vessel object
        """
        session = self.db.get_session()

        try:
            # Check if vessel exists
            vessel = session.query(Vessel).filter_by(vessel_id=vessel_id).first()

            if vessel:
                # Update existing vessel
                vessel.vessel_name = vessel_name
                vessel.email = email
                vessel.auth_token = auth_token
                vessel.labcom_account_id = labcom_account_id
                vessel.updated_at = datetime.utcnow()
                logger.info(f"Updated vessel: {vessel_id}")
            else:
                # Create new vessel
                vessel = Vessel(
                    vessel_id=vessel_id,
                    vessel_name=vessel_name,
                    email=email,
                    auth_token=auth_token,
                    labcom_account_id=labcom_account_id
                )
                session.add(vessel)
                logger.info(f"Created new vessel: {vessel_id}")

            session.commit()
            session.refresh(vessel)  # Refresh to get updated data

            # Extract data before closing session
            vessel_data = {
                'id': vessel.id,
                'vessel_id': vessel.vessel_id,
                'vessel_name': vessel.vessel_name,
                'email': vessel.email
            }

            session.close()
            return vessel_data['id']

        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error adding/updating vessel: {e}")
            raise

    def add_sampling_point(
        self,
        vessel_id: int,
        code: str,
        name: str,
        system_type: Optional[str] = None,
        labcom_account_id: Optional[int] = None
    ) -> SamplingPoint:
        """
        Add a sampling point for a vessel

        Args:
            vessel_id: Database vessel ID
            code: Sampling point code (e.g., 'AB1')
            name: Sampling point name
            system_type: System type (e.g., 'Boiler Water')
            labcom_account_id: Labcom account ID for this sampling point

        Returns:
            SamplingPoint object
        """
        session = self.db.get_session()

        try:
            # Check if sampling point exists
            sp = session.query(SamplingPoint).filter_by(
                vessel_id=vessel_id, code=code
            ).first()

            if sp:
                # Update existing
                sp.name = name
                sp.system_type = system_type
                sp.labcom_account_id = labcom_account_id
            else:
                # Create new
                sp = SamplingPoint(
                    vessel_id=vessel_id,
                    code=code,
                    name=name,
                    system_type=system_type,
                    labcom_account_id=labcom_account_id
                )
                session.add(sp)

            session.commit()
            session.refresh(sp)
            sp_id = sp.id
            session.close()
            return sp_id

        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error adding sampling point: {e}")
            raise

    def add_or_update_parameter(self, param_data: Dict) -> Parameter:
        """
        Add or update a parameter

        Args:
            param_data: Dictionary with parameter data from Labcom

        Returns:
            Parameter object
        """
        session = self.db.get_session()

        try:
            labcom_id = param_data.get('id')

            # Check if parameter exists
            param = session.query(Parameter).filter_by(
                labcom_parameter_id=labcom_id
            ).first()

            if param:
                # Update existing
                param.name = param_data.get('name', '')
                param.symbol = param_data.get('symbol', '')
                param.unit = param_data.get('unit', '')
                param.min_value = param_data.get('minValue')
                param.max_value = param_data.get('maxValue')
            else:
                # Create new
                param = Parameter(
                    labcom_parameter_id=labcom_id,
                    name=param_data.get('name', ''),
                    symbol=param_data.get('symbol', ''),
                    unit=param_data.get('unit', ''),
                    min_value=param_data.get('minValue'),
                    max_value=param_data.get('maxValue'),
                    description=param_data.get('name_long', '')
                )
                session.add(param)

            session.commit()
            return param

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding parameter: {e}")
            raise
        finally:
            session.close()

    def store_measurements(
        self,
        vessel_id: int,
        measurements: List[Dict]
    ) -> Dict[str, int]:
        """
        Store measurements from Labcom with enhanced fields

        Args:
            vessel_id: Database vessel ID
            measurements: List of measurement dictionaries from Labcom

        Returns:
            Dictionary with statistics: {'new': count, 'duplicate': count, 'alerts': count}
        """
        session = self.db.get_session()
        stats = {'new': 0, 'duplicate': 0, 'alerts': 0}

        try:
            for meas_data in measurements:
                labcom_meas_id = meas_data.get('id')

                # TEMPORARILY DISABLED: Allow duplicates across vessels
                # Check if already exists for THIS vessel only
                existing = session.query(Measurement).filter_by(
                    labcom_measurement_id=labcom_meas_id,
                    vessel_id=vessel_id
                ).first()

                if existing:
                    stats['duplicate'] += 1
                    continue

                # Get parameter ID from Labcom
                param_labcom_id = meas_data.get('parameter_id')

                # Get or create parameter
                param = session.query(Parameter).filter_by(
                    labcom_parameter_id=param_labcom_id
                ).first()

                if not param:
                    # Create parameter on the fly
                    param = Parameter(
                        labcom_parameter_id=param_labcom_id,
                        name=meas_data.get('parameter', ''),
                        unit=meas_data.get('unit', '')
                    )
                    session.add(param)
                    session.flush()  # Get param.id

                # Try to find sampling point
                labcom_account_id = meas_data.get('account_id')

                sampling_point = session.query(SamplingPoint).filter_by(
                    vessel_id=vessel_id,
                    labcom_account_id=labcom_account_id
                ).first()

                # Parse numeric value
                value_str = str(meas_data.get('value', ''))
                value_numeric = None
                try:
                    value_numeric = float(value_str)
                except (ValueError, TypeError):
                    pass

                # Parse ideal low/high
                ideal_low = None
                ideal_high = None
                try:
                    ideal_low_str = meas_data.get('ideal_low', '')
                    if ideal_low_str:
                        ideal_low = float(ideal_low_str)
                except (ValueError, TypeError):
                    pass

                try:
                    ideal_high_str = meas_data.get('ideal_high', '')
                    if ideal_high_str:
                        ideal_high = float(ideal_high_str)
                except (ValueError, TypeError):
                    pass

                # Create measurement with enhanced fields
                measurement = Measurement(
                    labcom_measurement_id=labcom_meas_id,
                    vessel_id=vessel_id,
                    sampling_point_id=sampling_point.id if sampling_point else None,
                    parameter_id=param.id,
                    value=value_str,
                    value_numeric=value_numeric,
                    unit=meas_data.get('unit', ''),
                    ideal_low=ideal_low,
                    ideal_high=ideal_high,
                    ideal_status=meas_data.get('ideal_status', ''),
                    measurement_date=datetime.fromtimestamp(meas_data.get('timestamp')),
                    operator_name=meas_data.get('operator_name', ''),
                    device_serial=meas_data.get('device_serial', ''),
                    comment=meas_data.get('comment', ''),
                    is_valid=1,
                    sync_status='synced'
                )

                session.add(measurement)
                session.flush()  # Get measurement.id

                # Create alert if out of range
                ideal_status = meas_data.get('ideal_status', '')
                if ideal_status in ['TOO LOW', 'TOO HIGH', 'CRITICAL']:
                    alert = Alert(
                        measurement_id=measurement.id,
                        vessel_id=vessel_id,
                        sampling_point_id=sampling_point.id if sampling_point else None,
                        parameter_id=param.id,
                        alert_type='critical' if ideal_status == 'CRITICAL' else 'warning',
                        alert_reason=ideal_status.replace(' ', '_'),
                        measured_value=value_numeric,
                        expected_low=ideal_low,
                        expected_high=ideal_high,
                        alert_date=datetime.fromtimestamp(meas_data.get('timestamp'))
                    )
                    session.add(alert)
                    stats['alerts'] += 1

                stats['new'] += 1

            session.commit()
            logger.info(f"Stored {stats['new']} new measurements, {stats['duplicate']} duplicates, {stats['alerts']} alerts")
            return stats

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing measurements: {e}")
            raise
        finally:
            session.close()

    def create_fetch_log(
        self,
        vessel_id: int,
        status: str,
        measurements_fetched: int = 0,
        measurements_new: int = 0,
        measurements_duplicate: int = 0,
        date_range_from: Optional[datetime] = None,
        date_range_to: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> int:
        """
        Create a fetch log entry

        Args:
            vessel_id: Vessel database ID
            status: 'success', 'failed', or 'partial'
            measurements_fetched: Total number of measurements fetched
            measurements_new: Number of new measurements stored
            measurements_duplicate: Number of duplicates skipped
            date_range_from: Start of date range
            date_range_to: End of date range
            error_message: Optional error message

        Returns:
            FetchLog ID
        """
        session = self.db.get_session()

        try:
            log = FetchLog(
                vessel_id=vessel_id,
                fetch_start=datetime.utcnow(),
                fetch_end=datetime.utcnow(),
                status=status,
                measurements_fetched=measurements_fetched,
                measurements_new=measurements_new,
                measurements_duplicate=measurements_duplicate,
                date_range_from=date_range_from,
                date_range_to=date_range_to,
                error_message=error_message
            )

            session.add(log)
            session.commit()
            session.refresh(log)
            log_id = log.id
            session.close()
            return log_id

        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error creating fetch log: {e}")
            raise

    def get_vessel_by_id(self, vessel_id: str) -> Optional[int]:
        """Get vessel database ID by vessel_id"""
        session = self.db.get_session()
        try:
            vessel = session.query(Vessel).filter_by(vessel_id=vessel_id).first()
            if vessel:
                vessel_db_id = vessel.id
                session.close()
                return vessel_db_id
            session.close()
            return None
        except Exception as e:
            session.close()
            raise


if __name__ == "__main__":
    # Test data manager
    dm = DataManager()

    # Add a test vessel
    vessel_db_id = dm.add_or_update_vessel(
        vessel_id="test_vessel",
        vessel_name="Test Vessel",
        email="test@example.com",
        auth_token="test_token",
        labcom_account_id=12345
    )

    print(f"✓ Created/updated vessel with database ID: {vessel_db_id}")

    # Add a sampling point
    sp_id = dm.add_sampling_point(
        vessel_id=vessel_db_id,
        code="AB1",
        name="Auxiliary Boiler 1",
        system_type="Boiler Water",
        labcom_account_id=67890
    )

    print(f"✓ Created sampling point with ID: {sp_id}")
