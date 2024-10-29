from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, String
from flask_migrate import Migrate

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
    
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False, unique=True)

    user = db.relationship('User', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')

class DoctorRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(500), nullable=True)

with app.app_context():
    db.create_all()
#------------------------------------------------------------------------------ROTAS(URL)-----------------------------------------------------------------------
@app.route('/') #Página Inicial
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first() # Verifica se o usuário é paciente
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('menu'))

        # Se não for paciente, verifica se é médico
        doctor = Doctor.query.filter_by(username=username).first()
        if doctor and check_password_hash(doctor.password, password):
            login_user(doctor)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('menu'))

        # Mensagem de erro para usuário ou senha incorretos
        flash('Usuário ou senha incorretos. Tente novamente.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form.get('user_type')  # Verifica se é paciente ou médico

        if user_type == 'patient':
            username = request.form.get('username')
            name = request.form.get('name')
            password = generate_password_hash(request.form.get('password'))
            existing_user = User.query.filter_by(username=username).first()
            if not name:
                return "O campo nome é obrigatório.", 400
            if existing_user:
                flash('Usuário já existe. Tente outro nome de usuário.')
                return redirect(url_for('register'))

            new_user = User(username=username, name=name, password=password)  # Criando um novo paciente
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro de paciente realizado com sucesso!')
            return redirect(url_for('login'))

        elif user_type == 'doctor':
            username = request.form.get('username')
            name = request.form.get('name')
            password = generate_password_hash(request.form.get('password'))
            specialty = request.form.get('specialty')
            crm = request.form.get('crm')
            estado = request.form.get('estado')  # Novo campo para o estado do CRM

            # Verifica se existe um médico com o mesmo CRM e Estado
            existing_doctor_crm = Doctor.query.filter_by(crm=crm, estado=estado).first()
            if existing_doctor_crm:
                flash('Já existe um médico com este CRM e estado. Faça login ou tente novamente.')
                return redirect(url_for('login'))

            # Cria um novo médico (Doctor)
            new_doctor = Doctor(username=username, password=password, name=name, specialty=specialty, crm=crm)
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
def menu():
    return render_template('menu.html')

@app.route('/schedule_appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required  # O paciente precisa estar logado
def schedule_appointment(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)  # Busca o médico pelo ID
    
    if request.method == 'POST':
        # Pega a data do formulário de agendamento
        appointment_date = request.form.get('appointment_date')
        
        # Verifica se a data é válida
        try:
            appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Data inválida. Tente novamente.', 'error')
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

# Rota para a página de seleção de médicos
@app.route('/select-doctor', methods=['GET', 'POST'])
def select_doctor():
    specialties = Doctor.query.with_entities(Doctor.specialty).distinct().all()  # Pega todas as especialidades distintas dos médicos
    if request.method == 'POST':
        specialty = request.form['specialty']
        selected_doctors = Doctor.query.filter_by(specialty=specialty).all() # Filtra todos os médicos com a especialidade selecionada
        if selected_doctors:
            return render_template('select_doctor.html', specialties=specialties, selected_doctors=selected_doctors)
        else:
            flash('Nenhum médico disponível para esta especialidade.', 'error')
    
    return render_template('select_doctor.html', specialties=specialties)

@app.route('/select-doctor-for-rating')
@login_required
def select_doctor_for_rating():
    appointments = (Appointment.query
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .filter(Appointment.user_id == current_user.id, Appointment.appointment_date <= date.today())
                    .all())

    return render_template('select_doctor_for_rating.html', appointments=appointments)

@app.route('/rate-doctor', methods=['GET', 'POST'])
def rate_doctor():
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        rating = request.form['rating']
        review = request.form.get('review')

        # Verificar se o paciente tem uma consulta agendada com o médico
        user_id = session['user_id']  # Assumindo que o ID do usuário está na sessão
        appointment = Appointment.query.filter(
            Appointment.user_id == user_id,
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date <= datetime.now().date()
        ).first()

        if appointment:
            # Criar a avaliação
            new_rating = DoctorRating(doctor_id=doctor_id, user_id=user_id, rating=rating, review=review)
            db.session.add(new_rating)
            db.session.commit()
            flash('Avaliação submetida com sucesso!', 'success')
            return redirect(url_for('menu'))  # Redirecionar para a página do menu
        else:
            flash('Você não pode avaliar este médico.', 'danger')

    doctors = Doctor.query.all()  # Lista de médicos para o dropdown
    return render_template('rate_doctor.html', doctors=doctors)


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

# Função que carrega o usuário baseado no ID
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) or Doctor.query.get(int(user_id))

if __name__ == '__main__':
    app.run(debug=True)

