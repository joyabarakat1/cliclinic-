from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, TelField, SelectField
from wtforms import DateField, TimeField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from datetime import datetime, timedelta, time

class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class PatientRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=100)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone Number', validators=[Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Register')

class DoctorRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=100)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone Number', validators=[Length(max=20)])
    specialty = StringField('Specialty', validators=[DataRequired(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Register')

class NurseRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=100)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone Number', validators=[Length(max=20)])
    department = StringField('Department', validators=[Length(max=100)])
    shift = SelectField('Shift', choices=[
        ('morning', 'Morning (6am-2pm)'),
        ('afternoon', 'Afternoon (2pm-10pm)'),
        ('night', 'Night (10pm-6am)'),
        ('variable', 'Variable')
    ])
    supervising_doctor = SelectField('Supervising Doctor', coerce=int, validators=[])  # Can be empty, will be populated dynamically
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Register')

class AppointmentBookingForm(FlaskForm):
    doctor = SelectField('Select Doctor', coerce=int, validators=[DataRequired()])
    nurse = SelectField('Assign Nurse (Optional)', coerce=int, choices=[(0, 'No Nurse Required')], validators=[])
    date = DateField('Appointment Date', format='%Y-%m-%d', validators=[DataRequired()])
    time_slot = SelectField('Time Slot', coerce=int, validators=[DataRequired()])
    reason = TextAreaField('Reason for Visit', validators=[Length(max=500)])
    submit = SubmitField('Book Appointment')
    
    def validate_date(self, date):
        # Ensure date is not in the past
        if date.data < datetime.now().date():
            raise ValidationError('Appointment date cannot be in the past.')
        
        # Ensure date is not more than 3 months in the future
        if date.data > (datetime.now() + timedelta(days=90)).date():
            raise ValidationError('Appointments can only be booked up to 3 months in advance.')

class AvailabilityForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[DataRequired()])
    end_time = TimeField('End Time', format='%H:%M', validators=[DataRequired()])
    slot_duration = SelectField('Slot Duration (minutes)', 
                               choices=[(15, '15'), (30, '30'), (45, '45'), (60, '60')],
                               coerce=int,
                               default=30)
    submit = SubmitField('Add Availability')
    
    def validate_end_time(self, end_time):
        if self.start_time.data and end_time.data:
            if end_time.data <= self.start_time.data:
                raise ValidationError('End time must be after start time.')
            
            # Calculate hours difference
            start_minutes = self.start_time.data.hour * 60 + self.start_time.data.minute
            end_minutes = end_time.data.hour * 60 + end_time.data.minute
            
            if (end_minutes - start_minutes) > 480:  # 8 hours max
                raise ValidationError('Availability period cannot exceed 8 hours.')

class ProfileUpdateForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=100)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone Number', validators=[Length(max=20)])
    # Additional fields specific to user type can be added later
    submit = SubmitField('Update Profile')

class AppointmentManagementForm(FlaskForm):
    status = SelectField('Status', 
                        choices=[('scheduled', 'Scheduled'), 
                                ('completed', 'Completed'), 
                                ('cancelled', 'Cancelled')],
                        validators=[DataRequired()])
    nurse = SelectField('Assign Nurse', coerce=int, choices=[(0, 'No Nurse Required')], validators=[])
    notes = TextAreaField('Notes', validators=[Length(max=500)])
    submit = SubmitField('Update Appointment')

class NotificationForm(FlaskForm):
    recipient_type = SelectField('Recipient Type', 
                               choices=[('patient', 'Patient'), 
                                       ('doctor', 'Doctor'), 
                                       ('nurse', 'Nurse')],
                               validators=[DataRequired()])
    recipient = SelectField('Recipient', coerce=int, validators=[DataRequired()])
    type = SelectField('Notification Type', 
                      choices=[('reminder', 'Appointment Reminder'), 
                              ('confirmation', 'Appointment Confirmation'), 
                              ('cancellation', 'Appointment Cancellation'),
                              ('rescheduled', 'Appointment Rescheduled'),
                              ('general', 'General Message')],
                      validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired(), Length(max=500)])
    scheduled_for = DateField('Send Date', format='%Y-%m-%d', validators=[DataRequired()])
    scheduled_time = TimeField('Send Time', format='%H:%M', validators=[DataRequired()])
    submit = SubmitField('Schedule Notification')