from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Unified User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'doctor', 'nurse', 'patient'
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Common doctor fields
    specialty = db.Column(db.String(100))
    
    # Common nurse fields
    department = db.Column(db.String(100))
    shift = db.Column(db.String(50))
    supervising_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    # Self-referential relationship for nurse-doctor supervision
    nurses = db.relationship('User', 
                            foreign_keys=[supervising_doctor_id],
                            backref=db.backref('supervising_doctor', remote_side=[id]),
                            lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.id}: {self.name} ({self.role})>'

# Medical Record for patients
class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diagnosis = db.Column(db.Text)
    treatment = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationships
    patient = db.relationship('User', foreign_keys=[patient_id], backref='medical_records')
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='records_created')
    
    def __repr__(self):
        return f'<MedicalRecord {self.id}: Patient {self.patient_id}, Doctor {self.doctor_id}>'

class DoctorAvailabilitySlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship('User', backref='availability_slots')

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    duration = db.Column(db.Integer, default=30)  # Duration in minutes
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_in = db.Column(db.Boolean, default=False)
    checked_in_time = db.Column(db.DateTime, nullable=True)
    
    # Define relationships
    patient = db.relationship('User', foreign_keys=[patient_id], backref='patient_appointments')
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_appointments')
    nurse = db.relationship('User', foreign_keys=[nurse_id], backref='nurse_appointments')
    
    def __repr__(self):
        return f'<Appointment {self.id}: {self.patient_id} with Dr. {self.doctor_id} on {self.date} at {self.time}>'

class DoctorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Define relationship
    doctor = db.relationship('User', backref='schedules')
    
    def __repr__(self):
        return f'<Schedule: Dr. {self.doctor_id} on {self.date} from {self.start_time} to {self.end_time}>'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Define relationships
    user = db.relationship('User', backref='notifications')
    appointment = db.relationship('Appointment', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'

# Helper functions for common operations
def get_available_time_slots(doctor_id, date):
    slots = DoctorAvailabilitySlot.query.filter_by(
        doctor_id=doctor_id,
        date=date,
        is_available=True
    ).all()
    return [slot.time for slot in slots]


def create_appointment(patient_id, doctor_id, date, time, reason=None, nurse_id=None):
    """
    Create a new appointment
    """
    # Check if time slot is available
    available_slots = get_available_time_slots(doctor_id, date)
    if time not in available_slots:
        return None, "This time slot is not available"
    
    # Create the appointment
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        nurse_id=nurse_id,
        date=date,
        time=time,
        reason=reason,
        status='scheduled'
    )
    
    db.session.add(appointment)
    db.session.commit()
    slot = DoctorAvailabilitySlot.query.filter_by(
        doctor_id=doctor_id,
        date=date,
        time=time
    ).first()

    if slot:
        slot.is_available = False
        db.session.commit()
    # Create notifications
    create_appointment_notifications(appointment)
    
    return appointment, "Appointment scheduled successfully"

def create_appointment_notifications(appointment):
    """
    Create notifications for a new appointment
    """
    # Notification for the doctor
    doctor_notification = Notification(
        user_id=appointment.doctor_id,
        appointment_id=appointment.id,
        message=f"New appointment with {appointment.patient.name} on {appointment.date} at {appointment.time}"
    )
    db.session.add(doctor_notification)
    
    # Notification for the patient
    patient_notification = Notification(
        user_id=appointment.patient_id,
        appointment_id=appointment.id,
        message=f"Appointment confirmed with Dr. {appointment.doctor.name} on {appointment.date} at {appointment.time}"
    )
    db.session.add(patient_notification)
    
    # Notification for the nurse if assigned
    if appointment.nurse_id:
        nurse_notification = Notification(
            user_id=appointment.nurse_id,
            appointment_id=appointment.id,
            message=f"You've been assigned to assist with {appointment.patient.name}'s appointment with Dr. {appointment.doctor.name} on {appointment.date} at {appointment.time}"
        )
        db.session.add(nurse_notification)
    
    db.session.commit()

def get_user_notifications(user_id, limit=10):
    """
    Get recent notifications for a user
    """
    return Notification.query.filter_by(
        user_id=user_id
    ).order_by(Notification.created_at.desc()).limit(limit).all()

def mark_notification_read(notification_id):
    """
    Mark a notification as read
    """
    notification = Notification.query.get(notification_id)
    if notification:
        notification.is_read = True
        db.session.commit()
        return True
    return False

def get_doctor_appointments(doctor_id, date=None):
    """
    Get appointments for a doctor, optionally filtered by date
    """
    query = Appointment.query.filter_by(doctor_id=doctor_id)
    
    if date:
        query = query.filter_by(date=date)
    
    return query.order_by(Appointment.date, Appointment.time).all()

def get_patient_appointments(patient_id, include_past=False):
    """
    Get appointments for a patient
    """
    query = Appointment.query.filter_by(patient_id=patient_id)
    
    if not include_past:
        # Only include appointments today or in the future
        query = query.filter(Appointment.date >= datetime.now().date())
    
    return query.order_by(Appointment.date, Appointment.time).all()

def cancel_appointment(appointment_id):
    """
    Cancel an appointment
    """
    appointment = Appointment.query.get(appointment_id)
    if appointment:
        appointment.status = 'cancelled'
        db.session.commit()
        
        # Notify the doctor
        doctor_notification = Notification(
            user_id=appointment.doctor_id,
            appointment_id=appointment.id,
            message=f"Appointment with {appointment.patient.name} on {appointment.date} at {appointment.time} has been cancelled"
        )
        db.session.add(doctor_notification)
        
        # Notify the patient
        patient_notification = Notification(
            user_id=appointment.patient_id,
            appointment_id=appointment.id,
            message=f"Your appointment with Dr. {appointment.doctor.name} on {appointment.date} at {appointment.time} has been cancelled"
        )
        db.session.add(patient_notification)
        
        # Notify the nurse if assigned
        if appointment.nurse_id:
            nurse_notification = Notification(
                user_id=appointment.nurse_id,
                appointment_id=appointment.id,
                message=f"The appointment with {appointment.patient.name} and Dr. {appointment.doctor.name} on {appointment.date} at {appointment.time} has been cancelled"
            )
            db.session.add(nurse_notification)
        
        db.session.commit()
        return True
    return False