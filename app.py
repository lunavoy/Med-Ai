from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
import os
import datetime

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
    username = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(12), nullable=False)

class Doctor(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String, nullable=False)
    username = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(50), nullable=False)
    specialty = db.Column(db.String(30), nullable=False)
    crm = db.Column(db.String(6), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="")

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)

    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')

    __table_args__ = (db.UniqueConstraint('doctor_id', 'appointment_datetime', name='_appointment_datetime_doctor_id_uc'),)

class DoctorRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(500), nullable=True)
    
with app.app_context():
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
            flash('Cadastro de paciente realizado com sucesso!')
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
            flash("Login realizado com sucesso.")
            return redirect(url_for('menu'))
        elif doctor and check_password_hash(doctor.password, password):
            login_user(doctor)
            session['user_type'] = 'doctor'
            flash("Login realizado com sucesso.")
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
        Appointment.appointment_datetime >= datetime.date.today()
    ).order_by(Appointment.appointment_datetime).all()
    return render_template('menu.html', upcoming_appointments=upcoming_appointments)

@app.route('/dashboard_doctor', endpoint='dashboard_doctor')
@login_required
def dashboard_doctor():
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_datetime >= datetime.date.today()
    ).order_by(Appointment.appointment_datetime).all()

    ratings = DoctorRating.query.filter_by(doctor_id=current_user.id).all()
    average_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else None
    latest_reviews = DoctorRating.query.filter_by(doctor_id=current_user.id).order_by(DoctorRating.id.desc()).limit(5).all()

    if 'logout' in request.args:
        logout_user()
        flash('Logout realizado com sucesso.')
        return redirect(url_for('login'))

    return render_template(
        'dashboard_doctor.html',
        doctor=current_user,
        appointments=upcoming_appointments,
        average_rating=average_rating,
        reviews=latest_reviews
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
@login_required  # O paciente precisa estar logado
def schedule_appointment(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)  # Busca o médico pelo ID
    
    if request.method == 'POST':
        appointment_date_str = request.form.get('appointment_date') 
        appointment_time_str = request.form.get('appointment_time')
        appointment_datetime_str = f'{appointment_date_str} {appointment_time_str}' # Pega e valida a data do formulário de agendamento
        
        appointment_datetime_str = appointment_datetime_str.replace('None ', '')  # Tira o 'None' do come o da string
        try:
            appointment_datetime = datetime.datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Formato de data ou hora inválido. Use o formato aaaa-mm-dd HH:MM.', 'error')
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))

        if appointment_datetime < datetime.datetime.now():  # data e hora no passado = error
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
@app.route('/select-doctor-for-rating')
@login_required
def select_doctor_for_rating():
    patient_id = current_user.id
    today = datetime.date.today()

    # Consultas anteriores ou na data atual, onde ainda não há avaliação
    appointments = (
        Appointment.query
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.appointment_datetime <= today
        )
        .outerjoin(DoctorRating, DoctorRating.doctor_id == Appointment.doctor_id)
        .filter(DoctorRating.id.is_(None))  # Exclui consultas já avaliadas
        .all()
    )

    return render_template('select_doctor_for_rating.html', appointments=appointments)
@app.route('/rate-doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def rate_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)  # Busca o médico pelo ID
    patient_id = current_user.id  # ID do paciente logado
    
    if request.method == 'POST':
        # Valida e converte a nota
        try:
            rating = int(request.form['rating'])
            if rating < 1 or rating > 5:
                flash('A nota deve ser entre 1 e 5.', 'danger')
                return redirect(url_for('rate_doctor', doctor_id=doctor_id))
        except ValueError:
            flash('A nota deve ser um número entre 1 e 5.', 'danger')
            return redirect(url_for('rate_doctor', doctor_id=doctor_id))

        review = request.form.get('review')
        
        # Verifica se existe uma consulta passada ou atual sem avaliação
        appointment = Appointment.query.filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_datetime <= datetime.date.today()
        ).first()

        existing_rating = DoctorRating.query.filter_by(
            doctor_id=doctor_id, 
            patient_id=patient_id
        ).first() if appointment else None

        if appointment and not existing_rating:
            # Cria a avaliação
            new_rating = DoctorRating(
                doctor_id=doctor_id,
                patient_id=patient_id,
                rating=rating,
                review=review
            )
            db.session.add(new_rating)
            db.session.commit()
            flash('Avaliação submetida com sucesso!', 'success')
            return redirect(url_for('menu'))
        else:
            flash('Você não pode avaliar este médico ou a consulta já foi avaliada.', 'danger')

    return render_template('rate_doctor.html', doctor=doctor)

@app.route('/check-data', methods=['GET'])
def check_data():
    data = []
    for table in db.metadata.sorted_tables:
        table_data = []
        for row in db.session.query(table).all():
            row_data = {c.name: getattr(row, c.name) for c in table.columns}
            table_data.append(row_data)
        data.append({table.name: table_data})
    return jsonify(data)



if __name__ == '__main__':
    app.run(debug=True)

