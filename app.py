from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Appointment, DoctorSchedule, MedicalRecord, Notification
from models import get_available_time_slots, create_appointment, get_doctor_appointments, DoctorAvailabilitySlot
from models import get_patient_appointments, cancel_appointment, get_user_notifications, mark_notification_read
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Added to fix the warning
db.init_app(app)


with app.app_context():
    db.create_all()


# Custom decorator for role-based access control
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or 'role' not in session:
                flash('Please log in to access this page', 'error')
                return redirect(url_for('login'))
            
            if session['role'] not in allowed_roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('homepage'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def homepage():
    return render_template('index.html')

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role'].lower()
        phone = request.form.get('phone', '')
        
        if not re.match(EMAIL_REGEX, email):
            error = "Invalid email format"
        elif len(password) < 5:
            error = "Password must be at least 5 characters"
        elif User.query.filter_by(email=email).first():
            error = "This email is already registered. Please log in instead."

        if error:
            return render_template('signup.html', error=error)
            
        hashed_password = generate_password_hash(password)
        
        # Additional fields based on role
        specialty = request.form.get('specialty', '') if role == 'doctor' else None
        department = request.form.get('department', '') if role == 'nurse' else None
        shift = request.form.get('shift', '') if role == 'nurse' else None
        supervising_doctor_id = request.form.get('supervising_doctor_id') if role == 'nurse' else None
        
        user = User(
            name=name, 
            email=email, 
            password=hashed_password, 
            role=role,
            phone=phone,
            specialty=specialty,
            department=department,
            shift=shift,
            supervising_doctor_id=supervising_doctor_id
        )
        
        db.session.add(user)
        db.session.commit()
        
        # If the user is a doctor, create initial schedule slots
        if role == 'doctor':
            create_default_schedule(user.id)
            
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('signup.html')

def create_default_schedule(doctor_id):
    """Create default work schedule for new doctors"""
    # Create schedule for the next 30 days
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=30)
    current_date = start_date
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() < 5:  # Monday to Friday
            schedule = DoctorSchedule(
                doctor_id=doctor_id,
                date=current_date,
                start_time='09:00',
                end_time='17:00',
                is_available=True
            )
            db.session.add(schedule)
        current_date += timedelta(days=1)
    
    db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if not user:
            error = "Email not found. Please sign up first."
        elif not check_password_hash(user.password, password):
            error = "Incorrect password. Try again."
        else:
            # Login successful
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name

            # Redirect based on role
            if user.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            elif user.role == 'nurse':
                return redirect(url_for('nurse_dashboard'))
            elif user.role == 'patient':
                return redirect(url_for('patient_dashboard'))
            else:
                # If role is unknown (fallback)
                return "Unknown user role", 400

        if error:
            flash(error, 'error')

    return render_template('login.html')

def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('homepage'))

# Notifications handling
@app.route('/notifications')
@role_required(['doctor', 'nurse', 'patient'])
def view_notifications():
    user_id = session['user_id']
    notifications = get_user_notifications(user_id)
    role = session.get('role')

    # Mark ALL as read
    for notif in notifications:
        if not notif.is_read:
         notif.is_read = True

    db.session.commit()

    return render_template('notifications.html', notifications=notifications, role=role)


@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@role_required(['doctor', 'nurse', 'patient'])
def mark_notification_as_read(notification_id):
    success = mark_notification_read(notification_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=success)
    return redirect(url_for('view_notifications'))

# Doctor Routes
@app.route('/doctor')
@role_required(['doctor'])
def doctor_dashboard():
    doctor_id = session['user_id']
    
    # Get today's appointments
    today = datetime.now().date()
    todays_appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        date=today
    ).order_by(Appointment.time).all()
    
    # Get upcoming appointments (future dates)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date > today
    ).order_by(Appointment.date, Appointment.time).all()
    
    # Get unread notifications
    notifications = Notification.query.filter_by(
        user_id=doctor_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('doctorhomepage.html', 
                          todays_appointments=todays_appointments,
                          upcoming_appointments=upcoming_appointments,
                          notifications=notifications)

@app.route('/doctor/availability')
@role_required(['doctor'])
def doctor_availability():
    doctor_id = session['user_id']
    today = datetime.today().date()
    end_date = today + timedelta(days=13)

    slots = DoctorAvailabilitySlot.query.filter(
        DoctorAvailabilitySlot.doctor_id == doctor_id,
        DoctorAvailabilitySlot.date >= today,
        DoctorAvailabilitySlot.date <= end_date
    ).all()

    slot_map = {}
    for slot in slots:
        slot_map[f"{slot.date}|{slot.time}"] = slot.is_available

    return render_template('doctor/availability.html', slot_map=slot_map, today=today)

@app.route('/doctor/schedule', methods=['GET', 'POST'])
@role_required(['doctor'])
def doctor_schedule():
    doctor_id = session['user_id']
    
    if request.method == 'POST':
        # Update or add new schedule slot
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        is_available = 'is_available' in request.form
        
        schedule_id = request.form.get('schedule_id')
        
        if schedule_id:  # Update existing
            schedule = DoctorSchedule.query.get(schedule_id)
            if schedule and schedule.doctor_id == doctor_id:
                schedule.start_time = start_time
                schedule.end_time = end_time
                schedule.is_available = is_available
                db.session.commit()
                flash('Schedule updated successfully', 'success')
        else:  # Create new
            # Check if a schedule already exists for this date
            existing_schedule = DoctorSchedule.query.filter_by(
                doctor_id=doctor_id,
                date=date
            ).first()
            
            if existing_schedule:
                existing_schedule.start_time = start_time
                existing_schedule.end_time = end_time
                existing_schedule.is_available = is_available
                db.session.commit()
                flash('Schedule updated successfully', 'success')
            else:
                new_schedule = DoctorSchedule(
                    doctor_id=doctor_id,
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=is_available
                )
                db.session.add(new_schedule)
                db.session.commit()
                flash('Schedule added successfully', 'success')
        
        return redirect(url_for('doctor_schedule'))
    
    # Get the doctor's schedule for the next 30 days
    today = datetime.now().date()
    end_date = today + timedelta(days=30)
    schedules = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.date >= today,
        DoctorSchedule.date <= end_date
    ).order_by(DoctorSchedule.date).all()
    
    return render_template('doctor/schedule.html', schedules=schedules)

@app.route('/doctor/appointment/<appointment_id>', methods=['GET', 'POST'])
@role_required(['doctor'])
def doctor_appointment_detail(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Ensure the doctor only accesses their own appointments
    if appointment.doctor_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('doctor_dashboard'))
    
    if request.method == 'POST':
        # Update appointment details or add notes
        appointment.notes = request.form['notes']
        appointment.status = request.form['status']
        db.session.commit()
        flash('Appointment updated successfully', 'success')
        return redirect(url_for('doctor_appointment_detail', appointment_id=appointment_id))
    
    # Get patient's medical records
    medical_records = MedicalRecord.query.filter_by(patient_id=appointment.patient_id).order_by(MedicalRecord.created_at.desc()).all()
    
    return render_template('doctor/appointment_details.html', 
                          appointment=appointment, 
                          patient=appointment.patient,
                          medical_records=medical_records)

@app.route('/doctor/add_medical_record/<patient_id>', methods=['GET', 'POST'])
@role_required(['doctor'])
def add_medical_record(patient_id):
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()
    
    if request.method == 'POST':
        diagnosis = request.form['diagnosis']
        treatment = request.form['treatment']
        notes = request.form['notes']
        
        new_record = MedicalRecord(
            patient_id=patient_id,
            doctor_id=session['user_id'],
            diagnosis=diagnosis,
            treatment=treatment,
            notes=notes
        )
        db.session.add(new_record)
        db.session.commit()
        
        # Create notification for patient
        notification = Notification(
            user_id=patient_id,
            message=f"Dr. {session['name']} has updated your medical records with a new diagnosis.",
            created_at=datetime.now()
        )
        db.session.add(notification)
        db.session.commit()
        
        flash('Medical record added successfully', 'success')
        return redirect(url_for('doctor_dashboard'))
    
    return render_template('doctor/add_medical_record.html', patient=patient)

# Nurse Routes
@app.route('/nurse')
@role_required(['nurse'])
def nurse_dashboard():
    # Get all upcoming appointments for any doctor for today
    today = datetime.now().date()
    todays_appointments = Appointment.query.filter_by(
        date=today
    ).order_by(Appointment.time).all()
    
    # Get unread notifications
    notifications = Notification.query.filter_by(
        user_id=session['user_id'],
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('nursehomepage.html', 
                          appointments=todays_appointments,
                          notifications=notifications)

@app.route('/nurse/check-in/<int:appointment_id>', methods=['POST'])
@role_required(['nurse'])
def check_in_patient(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.checked_in = True
    appointment.checked_in_time = datetime.now()
    db.session.commit()
    
    # Create notification for doctor
    notification = Notification(
        user_id=appointment.doctor_id,
        message=f"Patient {appointment.patient.name} has checked in for their appointment at {appointment.time}.",
        created_at=datetime.now()
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Patient checked in successfully', 'success')
    return redirect(url_for('nurse_dashboard'))

@app.route('/nurse/patient-list')
@role_required(['nurse'])
def patient_list():
    patients = User.query.filter_by(role='patient').all()
    doctors = User.query.filter_by(role='doctor').all()
    today = datetime.now().date()
    return render_template('nurse/patient_list.html', patients=patients, doctors=doctors, today=today)

@app.route('/nurse/patient/<int:patient_id>')
@role_required(['nurse'])
def patient_details(patient_id):
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.date.desc()).all()
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    today = datetime.now().date()
    
    return render_template(
        'nurse/patient_details.html',
        patient=patient,
        appointments=appointments,
        medical_records=medical_records,
        today=today
    )

@app.route('/nurse/view-doctor-schedule', methods=['GET', 'POST'])
@role_required(['nurse'])
def view_doctor_schedule():
    doctors = User.query.filter_by(role='doctor').all()
    selected_doctor_id = None
    schedules = []
    
    if request.method == 'POST':
        selected_doctor_id = int(request.form.get('doctor_id', 0))
        if selected_doctor_id:
            schedules = DoctorSchedule.query.filter_by(doctor_id=selected_doctor_id).order_by(DoctorSchedule.date).all()
    
    return render_template(
        'nurse/view_doctor_schedule.html', 
        doctors=doctors, 
        schedules=schedules,
        selected_doctor_id=selected_doctor_id
    )

@app.route('/get_doctors')
@role_required(['nurse'])
def get_doctors():
    doctors = User.query.filter_by(role='doctor').all()
    return jsonify([{'id': doctor.id, 'name': doctor.name} for doctor in doctors])

@app.route('/get_view_doctor_schedule/<int:doctor_id>')
@role_required(['nurse'])
def get_view_doctor_schedule(doctor_id):
    today = datetime.now().date()
    appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        date=today
    ).order_by(Appointment.time).all()
    
    if not appointments:
        return jsonify({"error": "No appointments scheduled for today"})
    
    appointment_data = []
    for appt in appointments:
        appointment_data.append({
            "time": appt.time,
            "patient": appt.patient.name
        })
    
    return jsonify(appointment_data)

@app.route('/nurse/send-notification', methods=['GET', 'POST'])
@role_required(['nurse'])
def send_notification():
    if request.method == 'POST':
        recipient_id = request.form['recipient_id']
        message = request.form['message']
        sender_name = session['name']  # Get the current user's name

        # Create the notification with the sender's name included
        notification = Notification(
            user_id=recipient_id,
            message=f"From {sender_name}: {message}",  # Add sender name to the message
            created_at=datetime.now()
        )
        db.session.add(notification)
        db.session.commit()

        flash('Notification sent successfully', 'success')
        return redirect(url_for('nurse_dashboard'))

    users = User.query.all()
    return render_template('nurse/send_notification.html', users=users)

@app.route('/get_doctor_weekly_availability/<int:doctor_id>')
@role_required(['nurse', 'doctor'])
def get_doctor_weekly_availability(doctor_id):
    """Get all availability slots for a doctor, used in the weekly schedule view"""
    today = datetime.now().date()
    end_date = today + timedelta(days=7)
    
    # Get available slots
    availability_slots = DoctorAvailabilitySlot.query.filter(
        DoctorAvailabilitySlot.doctor_id == doctor_id,
        DoctorAvailabilitySlot.date >= today,
        DoctorAvailabilitySlot.date <= end_date
    ).all()
    
    # Get booked appointments
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date >= today,
        Appointment.date <= end_date
    ).all()
    
    # Create a dictionary of booked time slots
    booked_slots = {}
    for appointment in appointments:
        key = f"{appointment.date}|{appointment.time}"
        booked_slots[key] = {
            "patient_name": appointment.patient.name,
            "id": appointment.id
        }
    
    # Create a list of all slots
    all_slots = []
    for slot in availability_slots:
        slot_key = f"{slot.date}|{slot.time}"
        all_slots.append({
            "date": str(slot.date),
            "time": slot.time,
            "is_available": slot.is_available,
            "is_booked": slot_key in booked_slots,
            "patient_name": booked_slots.get(slot_key, {}).get("patient_name") if slot_key in booked_slots else None
        })
    
    return jsonify(all_slots)

# Patient Routes
@app.route('/patient')
@role_required(['patient'])
def patient_dashboard():
    patient_id = session['user_id']
    
    # Get upcoming appointments
    today = datetime.now().date()
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.date >= today
    ).order_by(Appointment.date, Appointment.time).all()
    
    # Get past appointments
    past_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.date < today
    ).order_by(Appointment.date.desc(), Appointment.time).limit(5).all()
    
    # Get unread notifications
    notifications = Notification.query.filter_by(
        user_id=patient_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('patienthomepage.html',
                          upcoming_appointments=upcoming_appointments,
                          past_appointments=past_appointments,
                          notifications=notifications)

@app.route('/patient/book-appointment', methods=['GET', 'POST'])
@role_required(['patient'])
def book_appointment():
    reschedule_id = request.args.get('reschedule_id', type=int) if request.method == 'GET' else request.form.get('reschedule_id', type=int)

    if request.method == 'POST':
        
        doctor_id = request.form['doctor_id']
        date = request.form['date']
        time = request.form['time']
        reason = request.form['reason']
        
        # Convert string to date object if needed
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()

        # If rescheduling: free old slot
        if reschedule_id:
            old_appointment = Appointment.query.get(int(reschedule_id))
            if old_appointment and old_appointment.patient_id == session['user_id']:
                # Mark the old slot as available
                old_slot = DoctorAvailabilitySlot.query.filter_by(
                    doctor_id=old_appointment.doctor_id,
                    date=old_appointment.date,
                    time=old_appointment.time
                ).first()
                if old_slot:
                    old_slot.is_available = True

                db.session.delete(old_appointment)
                db.session.commit()

        # Create new appointment
        appointment, message = create_appointment(
            patient_id=session['user_id'],
            doctor_id=doctor_id,
            date=date,
            time=time,
            reason=reason
        )

        if appointment:
            flash('Appointment booked successfully', 'success')
            return redirect(url_for('patient_dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('book_appointment'))

    doctors = User.query.filter_by(role='doctor').all()
    appointment = Appointment.query.get(reschedule_id) if reschedule_id else None
    return render_template('patient/book_appointment.html', doctors=doctors, appointment=appointment)


@app.route('/patient/get-doctor-availability/<int:doctor_id>/<date>')
@role_required(['patient'])
def get_doctor_availability(doctor_id, date):
    """AJAX endpoint to get available time slots for a doctor on a given date"""
    try:
        # Convert string date to datetime.date
        booking_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get available time slots
        time_slots = get_available_time_slots(doctor_id, booking_date)
        
        return jsonify({"available": len(time_slots) > 0, "time_slots": time_slots})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/patient/view-medical-records')
@role_required(['patient'])
def view_medical_records():
    patient_id = session['user_id']
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    
    # Join with doctor information
    for record in medical_records:
        record.doctor_name = record.doctor.name
    
    return render_template('patient/medical_records.html', records=medical_records)

@app.route('/patient/cancel-appointment/<int:appointment_id>', methods=['POST'])
@role_required(['patient'])
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Ensure only the logged-in patient can cancel their own appointment
    if appointment.patient_id != session['user_id']:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('patient_dashboard'))
    slot = DoctorAvailabilitySlot.query.filter_by(
        doctor_id=appointment.doctor_id,
        date=appointment.date,
        time=appointment.time
    ).first()

    if slot:
        slot.is_available = True
    db.session.delete(appointment)
    appointment.status = 'cancelled'
    db.session.commit()
    flash("Appointment cancelled successfully.", "success")
    return redirect(url_for('patient_dashboard'))

@app.route('/doctor/toggle-slot', methods=['POST'])
@role_required(['doctor'])
def toggle_slot():
    data = request.get_json()
    doctor_id = session['user_id']
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    time = data['time']
    is_available = data['is_available']

    slot = DoctorAvailabilitySlot.query.filter_by(
        doctor_id=doctor_id,
        date=date,
        time=time
    ).first()

    if slot:
        slot.is_available = is_available
    else:
        db.session.add(DoctorAvailabilitySlot(
            doctor_id=doctor_id,
            date=date,
            time=time,
            is_available=is_available
        ))

    db.session.commit()
    return jsonify(success=True)

@app.route('/api/doctor/slots')
@role_required(['doctor'])
def get_doctor_slots():
    doctor_id = session['user_id']
    today = datetime.now().date()
    end_date = today + timedelta(days=13)

    slots = DoctorAvailabilitySlot.query.filter_by(doctor_id=doctor_id).filter(
        DoctorAvailabilitySlot.date >= today,
        DoctorAvailabilitySlot.date <= end_date
    ).all()

    return jsonify({
        "slots": [
            {"date": str(slot.date), "time": slot.time, "is_available": slot.is_available}
            for slot in slots
        ]
    })

if __name__ == '__main__':
 app.run(debug=True)