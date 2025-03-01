from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, Date, ForeignKey, String, Float, LargeBinary, update
from sqlalchemy.orm import relationship, aliased, joinedload
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
import os
from datetime import datetime
from base64 import b64encode

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)
#-----------------------------------Tabelas--------------------------------------------------
class Patient(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(12), nullable=False)
    date_of_birth = db.Column(Date)
    gender = db.Column(String(10))
    weight = db.Column(Float)
    height = db.Column(Float)
    profile_picture = db.Column(LargeBinary)

class Doctor(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String, nullable=False)
    username = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    specialty = db.Column(db.String(30), nullable=False)
    crm = db.Column(db.String(6), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="")
    profile_picture = db.Column(LargeBinary)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)

    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')

class Rating(db.Model):
    tablename = 'rating'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(500), nullable=True, default="")

with app.app_context():
    new_appointment = Appointment(patient_id=1, doctor_id=2, appointment_datetime=datetime.today().replace(hour=19, minute=0, second=0))
    db.session.add(new_appointment)
    db.session.commit()
    db.create_all()
    #db.create_all() # Doctor.__table__.drop(db.engine)
#------------------------------------------------------------------------------ROTAS(URL)-----------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    if session.get('user_type') == 'patient':
        return Patient.query.get(int(user_id))
    elif session.get('user_type') == 'doctor':
        return Doctor.query.get(int(user_id))
    return None
@app.route('/') #Página Inicial
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        
        # Patient Registration
        if user_type == 'patient':
            username = request.form.get('username')
            name = request.form.get('name')
            password = request.form.get('password')

            if not username or not name or not password:
                flash("Todos os campos são obrigatórios.")
                return redirect(url_for('register'))

            existing_user = Patient.query.filter_by(username=username).first()
            if existing_user:
                flash('O nome de usuário já está em uso. Tente outro.')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password)
            new_user = Patient(username=username, name=name, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))

        # Doctor Registration
        elif user_type == 'doctor':
            username = request.form.get('username')
            name = request.form.get('name')
            password = request.form.get('password')
            specialty = request.form.get('specialty')
            crm = request.form.get('crm')
            estado = request.form.get('estado')

            if not username or not name or not password or not specialty or not crm or not estado:
                flash("Todos os campos de médico são obrigatórios.")
                return redirect(url_for('register'))

            existing_doctor = Doctor.query.filter_by(username=username).first()
            existing_doctor_crm = Doctor.query.filter_by(crm=crm, estado=estado).first()
            
            if existing_doctor or existing_doctor_crm:
                flash('O nome de usuário ou CRM já está em uso. Tente outro.')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password)
            new_doctor = Doctor(username=username, name=name, password=hashed_password, specialty=specialty, crm=crm, estado=estado)
            db.session.add(new_doctor)
            db.session.commit()
            flash('Cadastro de médico realizado com sucesso!')
            return redirect(url_for('login'))

    return render_template('register.html')
        
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        patient = Patient.query.filter_by(username=username).first()
        doctor = Doctor.query.filter_by(username=username).first()

        if patient and check_password_hash(patient.password, password):
            login_user(patient)
            session['user_type'] = 'patient'
            return redirect(url_for('menu'))
        elif doctor and check_password_hash(doctor.password, password):
            login_user(doctor)
            session['user_type'] = 'doctor'
            return redirect(url_for('dashboard_doctor'))
        else:
            flash("Username ou senha incorretos.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    session.pop('user_type', None)
    flash('Logout realizado com sucesso.')
    return redirect(url_for('login'))

@app.route('/menu')
@login_required
def menu():
    if session.get('user_type') != 'patient':
        abort(403)  # Restrict access if not a patient
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.appointment_datetime >= datetime.today()
    ).order_by(Appointment.appointment_datetime).all()
    return render_template('menu.html', upcoming_appointments=upcoming_appointments)

@app.route('/dashboard_doctor', endpoint='dashboard_doctor')
@login_required
def dashboard_doctor():
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_datetime >= datetime.today()
    ).order_by(Appointment.appointment_datetime).all()

    ratings = Rating.query.filter_by(doctor_id=current_user.id).all()
    average_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else None
    latest_reviews = Rating.query.filter_by(doctor_id=current_user.id).order_by(Rating.id.desc()).limit(5).all()

    if 'logout' in request.args:
        logout_user()
        flash('Logout realizado com sucesso.')
        return redirect(url_for('login'))

    return render_template(
        'dashboard_doctor.html',
        doctor=current_user,
        appointments=upcoming_appointments,
        average_rating=average_rating,
        reviews=latest_reviews,
        patient_names={a.patient_id: a.patient.name for a in upcoming_appointments}
    )

@app.route('/select-doctor', methods=['GET', 'POST'])
def select_doctor():
    # Busca especialidades distintas para o formulário
    specialties = [specialty[0] for specialty in Doctor.query.with_entities(Doctor.specialty).distinct().all()]

    if request.method == 'POST':
        specialty = request.form.get('specialty')
        
        # Filtra médicos com a especialidade selecionada
        selected_doctors = Doctor.query.filter_by(specialty=specialty).all()
        if not selected_doctors:
            flash('Nenhum médico disponível para esta especialidade.', 'error')
        
        # Renderiza a página com médicos filtrados ou uma mensagem
        return render_template('select_doctor.html', specialties=specialties, selected_doctors=selected_doctors)
    
    # Renderiza a página de seleção de especialidades sem médicos selecionados inicialmente
    return render_template('select_doctor.html', specialties=specialties)

@app.route('/schedule_appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def schedule_appointment(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)  # Busca o médico pelo ID
    
    if request.method == 'POST':
        appointment_date_str = request.form.get('appointment_date') 
        appointment_time_str = request.form.get('appointment_time')
        appointment_datetime_str = f'{appointment_date_str} {appointment_time_str}' # Pega e valida a data do formulário de agendamento
        
        appointment_datetime_str = appointment_datetime_str.replace('None ', '')  # Tira o 'None' do come o da string
        try:
            appointment_datetime = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Formato de data ou hora inválido. Use o formato aaaa-mm-dd HH:MM.', 'error')
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))

        if appointment_datetime < datetime.now():
            flash('A data e hora selecionadas são no passado. Escolha uma data futura.', 'error')
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))

        # Verifica se j  existe um agendamento para esse m dico na data e hora selecionados
        booked_time_slots = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            db.func.date(Appointment.appointment_datetime) == appointment_datetime.date()
        ).all()
        for appointment in booked_time_slots:
            if appointment.appointment_datetime == appointment_datetime:
                flash('Esse médico já tem uma consulta agendada nessa data e hora. Escolha outra data ou hora.', 'error')
                return redirect(url_for('schedule_appointment', doctor_id=doctor_id))
        
        # Cria uma nova consulta
        new_appointment = Appointment(
            patient_id=current_user.id,  # Paciente logado
            doctor_id=doctor_id,
            appointment_datetime=appointment_datetime
        )
        db.session.add(new_appointment)
        db.session.commit()
        
        flash(f'Consulta agendada com o Dr. {doctor.name} para o dia e hora {appointment_datetime}.', 'success')
        return redirect(url_for('menu'))  # Redireciona após o agendamento

    available_times = [f"{hour}:00" for hour in range(8, 19)]  # Horários disponíveis das 8 às 18
    return render_template('schedule_appointment.html', doctor=doctor, available_times=available_times)

@app.route('/select-doctor-for-rating', methods=['GET'])
@login_required
def select_doctor_for_rating():
    patient_id = current_user.id

    # Retrieve appointments for the logged-in patient that are eligible for rating
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_datetime < datetime.now()
    ).all()

    return render_template('select-doctor-for-rating.html', appointments=appointments)

@app.route('/rate-doctor/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def rate_doctor(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.patient_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        rating_value = request.form.get('rating')
        review = request.form.get('review', '')

        # Criar nova avaliação
        new_rating = Rating(
            doctor_id=appointment.doctor_id,
            patient_id=current_user.id,
            rating=int(rating_value),
            review=review
        )
        db.session.add(new_rating)
        db.session.commit()

        flash("Avaliação enviada com sucesso!", "success")
        return redirect(url_for('select_doctor_for_rating'))

    doctor = Doctor.query.get(appointment.doctor_id)
    return render_template('rate_doctor.html', doctor=doctor, appointment=appointment)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update fields
        try:
            current_user.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
        except ValueError:
            flash('Data de nascimento em formato inválido', 'danger')
            return redirect(url_for('profile'))
        current_user.gender = request.form.get('gender')

        # Only request weight and height if user is not a doctor
        if not hasattr(current_user, 'crm'):
            try:
                current_user.weight = float(request.form.get('weight'))
            except ValueError:
                current_user.weight = None
            try:
                current_user.height = float(request.form.get('height'))
            except ValueError:
                current_user.height = None

        # Handle profile picture upload
        profile_pic = request.files.get('profile_picture')
        if profile_pic:
            filename = secure_filename(profile_pic.filename)
            current_user.profile_picture = profile_pic.read()
        
        # Save to database
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.template_filter('b64encode')
def b64encode_filter(data):
    return b64encode(data).decode('utf-8') if data else ''

@app.route('/check-data')
def check_data():
    users = Patient.query.all()
    doctors = Doctor.query.all()
    appointments = Appointment.query.all()
    ratings = Rating.query.all()
    return render_template('check_data.html', users=users, doctors=doctors, appointments=appointments, ratings=ratings)

if __name__ == '__main__':
    app.run(debug=True)