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
db = SQLAlchemy(app) # Inicializando a base de dados
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Rota onde será redirecionado se o login for necessário
migrate = Migrate(app, db)
#-----------------------------------Tabelas--------------------------------------------------
class User(db.Model, UserMixin):
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
    pfp = db.Column(db.String(100), nullable=True)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class Appointment(db.Model):
    __tablename__ = 'appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)

    user = db.relationship('User', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')

    __table_args__ = (db.UniqueConstraint('doctor_id', 'appointment_date', name='_appointment_date_doctor_id_uc'),)

class DoctorRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(500), nullable=True)

with app.app_context():
   db.create_all()
    #db.create_all() # Doctor.__table__.drop(db.engine)
#------------------------------------------------------------------------------ROTAS(URL)-----------------------------------------------------------------------
@app.route('/') #Página Inicial
def home():
    return render_template('home.html')
@login_manager.user_loader # Função que carrega o usuário baseado no ID
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user is not None:
        return user

    doctor = Doctor.query.get(int(user_id))
    if doctor is not None:
        return doctor  
    return None
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['user_type'] = 'patient'
            return redirect(url_for('menu'))
        
        doctor = Doctor.query.filter_by(username=username).first()
        if doctor and check_password_hash(doctor.password, password):
            login_user(doctor)
            session['user_type'] = 'doctor'
            return redirect(url_for('dashboard_doctor'))
        else:
            flash("Username ou senha incorretos.")

    if session.get('user_type') == 'patient':
        print("Logged-in user is a patient")
    elif session.get('user_type') == 'doctor':
        print("Logged-in user is a doctor")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        name = request.form.get('name')
        password = request.form.get('password')

        if not username or not name or not password:
            flash("Todos os campos são obrigatórios.")
            return redirect(url_for('register'))

        # Verificação de existência de username em ambas as tabelas
        existing_user = User.query.filter_by(username=username).first()
        existing_doctor = Doctor.query.filter_by(username=username).first()
        
        if existing_user or existing_doctor:
            flash('O nome de usuário já está em uso. Tente outro.')
            return redirect(url_for('register'))

        user_type = request.form.get('user_type')  # Verifica se é paciente ou médico

        if user_type == 'patient':
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, name=name, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro de paciente realizado com sucesso!')
            return redirect(url_for('login'))

        elif user_type == 'doctor':
            specialty = request.form.get('specialty')
            crm = request.form.get('crm')
            estado = request.form.get('estado')  # Novo campo para o estado do CRM

            if not specialty or not crm or not estado:
                flash("Todos os campos de médico são obrigatórios.")
                return redirect(url_for('register'))

            # Verifica se já existe um médico com o mesmo CRM e estado
            existing_doctor_crm = Doctor.query.filter_by(crm=crm, estado=estado).first()
            if existing_doctor_crm:
                flash('Já existe um médico com este CRM e estado. Faça login ou tente novamente.')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password)
            new_doctor = Doctor(username=username, name=name, password=hashed_password, specialty=specialty, crm=crm, estado=estado)
            db.session.add(new_doctor)
            db.session.commit()
            flash('Cadastro de médico realizado com sucesso!')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.')
    return redirect(url_for('login'))

@app.route('/menu')
@login_required
def menu():
    # Verifica se o usuário atual é um médico
    if isinstance(current_user, Doctor):
        flash("Acesso restrito a pacientes.")
        return redirect(url_for('dashboard_doctor'))
    
    # Caso seja um paciente, renderiza o menu
    return render_template('menu.html')
        
@app.route('/dashboard_doctor', endpoint='dashboard_doctor')
@login_required
def dashboard_doctor():
    if not isinstance(current_user, Doctor):
        abort(403)

    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date >= datetime.date.today()
    ).order_by(Appointment.appointment_date).all()

    ratings = DoctorRating.query.filter_by(doctor_id=current_user.id).all()
    average_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else None
    latest_reviews = DoctorRating.query.filter_by(doctor_id=current_user.id).order_by(DoctorRating.id.desc()).limit(5).all()

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
        # Pega e valida a data do formulário de agendamento
        appointment_date_str = request.form.get('appointment_date')
        try:
            appointment_date = datetime.datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
            
            # Verifica se a data não está no passado
            if appointment_date < datetime.date.today():
                flash('A data selecionada é no passado. Escolha uma data futura.', 'error')
                return redirect(url_for('schedule_appointment', doctor_id=doctor_id))
                
        except ValueError:
            flash('Data inválida. Por favor, use o formato AAAA-MM-DD.', 'error')
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))

        # Verifica se já existe um agendamento para esse médico na data selecionada
        existing_appointment = Appointment.query.filter_by(doctor_id=doctor_id, appointment_date=appointment_date).first()
        if existing_appointment:
            flash('Esse médico já tem uma consulta agendada nessa data. Escolha outra data.', 'error')
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))
        
        # Cria uma nova consulta
        new_appointment = Appointment(
            user_id=current_user.id,  # Paciente logado
            doctor_id=doctor_id,
            appointment_date=appointment_date
        )
        db.session.add(new_appointment)
        db.session.commit()
        
        flash(f'Consulta agendada com o Dr. {doctor.name} para o dia {appointment_date}.', 'success')
        return redirect(url_for('menu'))  # Redireciona após o agendamento

    return render_template('schedule_appointment.html', doctor=doctor)

@app.route('/select-doctor-for-rating')
@login_required
def select_doctor_for_rating():
    user_id = current_user.id
    today = datetime.date.today()

    # Consultas anteriores ou na data atual, onde ainda não há avaliação
    appointments = (
        Appointment.query
        .filter(
            Appointment.user_id == user_id,
            Appointment.appointment_date <= today
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
    user_id = current_user.id  # ID do usuário logado
    
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
            Appointment.user_id == user_id,
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date <= datetime.date.today()
        ).first()

        existing_rating = DoctorRating.query.filter_by(
            doctor_id=doctor_id, 
            user_id=user_id
        ).first() if appointment else None

        if appointment and not existing_rating:
            # Cria a avaliação
            new_rating = DoctorRating(
                doctor_id=doctor_id,
                user_id=user_id,
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
@app.route('/upload_profile_image', methods=['POST'])
@login_required
def upload_profile_image():
    if not isinstance(current_user, Doctor):
        return redirect(url_for('menu'))

    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join('static/profile_images', filename)
            file.save(filepath)
            current_user.profile_image = filename
            db.session.commit()
            flash("Imagem de perfil atualizada com sucesso.")
    
    return redirect(url_for('dashboard_doctor'))

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



