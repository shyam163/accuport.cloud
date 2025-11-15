"""
SQLite Database Schema for Accuport
Stores marine onboard chemical test data from Labcom
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class Vessel(Base):
    """Vessel/Ship information"""
    __tablename__ = 'vessels'

    id = Column(Integer, primary_key=True)
    vessel_id = Column(String(50), unique=True, nullable=False)  # e.g., 'mv_racer'
    vessel_name = Column(String(100), nullable=False)  # e.g., 'M.V Racer'
    email = Column(String(100))
    labcom_account_id = Column(Integer)  # Account ID from Labcom
    auth_token = Column(String(255))  # Encrypted or securely stored
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sampling_points = relationship('SamplingPoint', back_populates='vessel')
    measurements = relationship('Measurement', back_populates='vessel')


class SamplingPoint(Base):
    """Sampling points for each vessel"""
    __tablename__ = 'sampling_points'

    id = Column(Integer, primary_key=True)
    vessel_id = Column(Integer, ForeignKey('vessels.id'), nullable=False)
    code = Column(String(10), nullable=False)  # e.g., 'AB1', 'ME', 'PW1'
    name = Column(String(100), nullable=False)  # e.g., 'Auxiliary boiler 1'
    system_type = Column(String(50))  # e.g., 'Boiler Water', 'Main Engine'
    description = Column(Text)
    labcom_account_id = Column(Integer, index=True)  # Link to Labcom account (not unique - shared across vessels)
    is_active = Column(Integer, default=1)  # 1=active, 0=inactive
    location_description = Column(Text)  # Physical location details
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vessel = relationship('Vessel', back_populates='sampling_points')
    measurements = relationship('Measurement', back_populates='sampling_point')
    parameter_limits = relationship('ParameterLimit', back_populates='sampling_point')

    __table_args__ = (
        UniqueConstraint('vessel_id', 'code', name='unique_vessel_sampling_point'),
        UniqueConstraint('vessel_id', 'labcom_account_id', name='unique_vessel_labcom_account'),
    )


class Parameter(Base):
    """Chemical test parameters"""
    __tablename__ = 'parameters'

    id = Column(Integer, primary_key=True)
    labcom_parameter_id = Column(Integer, unique=True, index=True)  # ID from Labcom
    name = Column(String(100), nullable=False)  # e.g., 'pH', 'Chloride'
    symbol = Column(String(20))  # e.g., 'pH', 'Cl'
    unit = Column(String(50))  # Default unit e.g., 'ppm', 'mg/L'
    ideal_low = Column(Float)  # Default ideal low value
    ideal_high = Column(Float)  # Default ideal high value
    category = Column(String(50))  # 'chemical', 'physical', 'biological'
    criticality = Column(String(20))  # 'high', 'medium', 'low'
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    measurements = relationship('Measurement', back_populates='parameter')
    parameter_limits = relationship('ParameterLimit', back_populates='parameter')


class Measurement(Base):
    """Test measurement data"""
    __tablename__ = 'measurements'

    id = Column(Integer, primary_key=True)
    labcom_measurement_id = Column(Integer, index=True)  # ID from Labcom - TEMPORARILY REMOVED unique=True to allow duplicates across vessels
    vessel_id = Column(Integer, ForeignKey('vessels.id'), nullable=False, index=True)
    sampling_point_id = Column(Integer, ForeignKey('sampling_points.id'), index=True)
    parameter_id = Column(Integer, ForeignKey('parameters.id'), nullable=False, index=True)

    # Value fields
    value = Column(String(50), nullable=False)  # Raw value from Labcom (string)
    value_numeric = Column(Float)  # Parsed numeric value for calculations
    unit = Column(String(50))  # Unit for this specific measurement

    # Quality control fields
    ideal_low = Column(Float)  # Ideal low for THIS measurement
    ideal_high = Column(Float)  # Ideal high for THIS measurement
    ideal_status = Column(String(20))  # 'OKAY', 'TOO LOW', 'TOO HIGH', 'CRITICAL'

    # Metadata
    measurement_date = Column(DateTime, nullable=False, index=True)  # When test was performed
    operator_name = Column(String(100))  # Who performed the test
    device_serial = Column(String(100))  # Device used ('Manual' or serial number)
    comment = Column(Text)  # Comments/notes

    # Data quality
    is_valid = Column(Integer, default=1)  # 1=valid, 0=invalid
    sync_status = Column(String(20), default='synced')  # 'synced', 'pending', 'failed'

    # Timestamps
    fetched_at = Column(DateTime, default=datetime.utcnow)  # When we fetched from Labcom
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vessel = relationship('Vessel', back_populates='measurements')
    sampling_point = relationship('SamplingPoint', back_populates='measurements')
    parameter = relationship('Parameter', back_populates='measurements')
    alerts = relationship('Alert', back_populates='measurement')

    # TEMPORARILY DISABLED: Allow duplicate labcom_measurement_id for multiple vessels
    # This allows the same measurement to be stored for different vessels
    # __table_args__ = (
    #     UniqueConstraint('labcom_measurement_id', name='unique_labcom_measurement'),
    # )


class ParameterLimit(Base):
    """Custom parameter limits per sampling point"""
    __tablename__ = 'parameter_limits'

    id = Column(Integer, primary_key=True)
    sampling_point_id = Column(Integer, ForeignKey('sampling_points.id'), nullable=False)
    parameter_id = Column(Integer, ForeignKey('parameters.id'), nullable=False)

    # Limits
    ideal_low = Column(Float)
    ideal_high = Column(Float)
    warning_low = Column(Float)  # Warning threshold
    warning_high = Column(Float)  # Warning threshold
    critical_low = Column(Float)  # Critical threshold
    critical_high = Column(Float)  # Critical threshold

    # Time-based limits
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime)  # NULL means currently active

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sampling_point = relationship('SamplingPoint', back_populates='parameter_limits')
    parameter = relationship('Parameter', back_populates='parameter_limits')

    __table_args__ = (
        UniqueConstraint('sampling_point_id', 'parameter_id', 'effective_from',
                        name='unique_limit_per_period'),
    )


class Alert(Base):
    """Alerts for out-of-range measurements"""
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True)
    measurement_id = Column(Integer, ForeignKey('measurements.id'), nullable=False, index=True)
    vessel_id = Column(Integer, ForeignKey('vessels.id'), nullable=False, index=True)
    sampling_point_id = Column(Integer, ForeignKey('sampling_points.id'), index=True)
    parameter_id = Column(Integer, ForeignKey('parameters.id'), nullable=False, index=True)

    # Alert details
    alert_type = Column(String(20), nullable=False)  # 'warning', 'critical'
    alert_reason = Column(String(50))  # 'TOO_LOW', 'TOO_HIGH', 'OUT_OF_RANGE'
    measured_value = Column(Float)
    expected_low = Column(Float)
    expected_high = Column(Float)

    # Alert management
    alert_date = Column(DateTime, nullable=False, index=True)
    acknowledged_by = Column(String(100))
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime, index=True)
    resolution_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    measurement = relationship('Measurement', back_populates='alerts')


class FetchLog(Base):
    """Log of data fetch operations"""
    __tablename__ = 'fetch_logs'

    id = Column(Integer, primary_key=True)
    vessel_id = Column(Integer, ForeignKey('vessels.id'), index=True)
    fetch_start = Column(DateTime, nullable=False)
    fetch_end = Column(DateTime)
    status = Column(String(20))  # 'success', 'failed', 'partial'
    measurements_fetched = Column(Integer, default=0)
    measurements_new = Column(Integer, default=0)  # How many were new
    measurements_duplicate = Column(Integer, default=0)  # How many were skipped
    date_range_from = Column(DateTime)  # Date range fetched
    date_range_to = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """Manager for database operations"""

    def __init__(self, db_path: str = 'data/accubase.sqlite'):
        """Initialize database connection"""
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        print(f"Database tables created at {self.db_path}")

    def get_session(self):
        """Get a new database session"""
        return self.Session()


if __name__ == "__main__":
    # Test database creation
    import os
    os.makedirs('../data', exist_ok=True)

    db = DatabaseManager('../data/accubase.sqlite')
    db.create_tables()

    print("\n✓ Enhanced database schema created successfully!")
    print("\nTables created:")
    print("  - vessels")
    print("  - sampling_points (enhanced with is_active, location)")
    print("  - parameters (enhanced with ideal ranges, category)")
    print("  - measurements (enhanced with quality control fields)")
    print("  - parameter_limits (NEW - custom limits per sampling point)")
    print("  - alerts (NEW - out-of-range measurement tracking)")
    print("  - fetch_logs (enhanced with detailed statistics)")
    print("\nPhase 1 enhancements implemented:")
