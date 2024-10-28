from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'
db = SQLAlchemy(app) # Inicializando a base de dados
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Rota onde será redirecionado se o login for necessário



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

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False, unique=True)

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
            flash('Login realizado com sucesso!')
            return redirect(url_for('menu'))  # Redireciona para o painel após o login

        # Se não for paciente, verifica se é médico
        doctor = Doctor.query.filter_by(username=username).first()
        if doctor and check_password_hash(doctor.password, password):
            login_user(doctor)
            flash('Login realizado com sucesso!')
            return redirect(url_for('menu'))  # Redireciona para o painel após o login

        flash('Usuário ou senha incorretos. Tente novamente.')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form.get('user_type')  # Verifica se é paciente ou médico

        if user_type == 'patient':
            name = request.form.get('name')
            username = request.form.get('username')
            password = generate_password_hash(request.form.get('password'))
            
            # Verifica se o username já existe na tabela User
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Usuário já existe. Tente outro nome de usuário.', 'error')
                return redirect(url_for('register'))

            # Cria um novo paciente (User)
            new_user = User(name=name, username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro de paciente realizado com sucesso!', 'success')
            return redirect(url_for('login'))

        elif user_type == 'doctor':
            username = request.form.get('username')
            name = request.form.get('name')
            password = generate_password_hash(request.form.get('password'))  # Gerar a senha corretamente
            specialty = request.form.get('specialty')
            crm = request.form.get('crm')

            existing_user = Doctor.query.filter_by(username=username).first()
            if existing_user:
                flash('Usuário já existe. Tente outro nome.')
                return redirect(url_for('register'))

            # Verifica se o CRM já está cadastrado
            existing_doctor = Doctor.query.filter_by(crm=crm).first()
            if existing_doctor:
                flash('Médico já cadastrado. Fazer login?')
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

# Rota para agendar com o médico selecionado
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
        return redirect(url_for('select_doctor'))  # Redireciona após o agendamento

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

@app.route('/rate-doctor/<int:doctor_id>', methods=['GET', 'POST'])
def rate_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)

    if request.method == 'POST':
        rating = int(request.form['rating'])
        review = request.form.get('review', '')

        # Armazenar a avaliação no banco de dados
        new_rating = DoctorRating(doctor_id=doctor_id, rating=rating, review=review)
        db.session.add(new_rating)
        db.session.commit()

        flash('Avaliação enviada com sucesso!', 'success')
        return redirect(url_for('rate_doctor', doctor_id=doctor_id))

    return render_template('rate_doctor.html', doctor_id=doctor_id, doctor=doctor)

@app.route('/list_data')
def list_data():
    # Consultando todos os dados das tabelas
    users = User.query.all()
    doctors = Doctor.query.all()
    appointments = Appointment.query.all()
    ratings = DoctorRating.query.all()

    # Iniciando a string HTML para exibição dos dados
    result = """
    <html>
        <head>
            <title>Lista de Dados</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                h1, h2 { color: #333; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
                th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #f4f4f4; }
                tr:nth-child(even) { background-color: #f9f9f9; }
            </style>
        </head>
        <body>
            <h1>Lista de Dados</h1>
            
            <h2>Usuários</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Usuário</th>
                </tr>
    """

    # Adicionando os dados de Usuários
    for user in users:
        result += f"""
            <tr>
                <td>{user.id}</td>
                <td>{user.username}</td>
            </tr>
        """

    result += """
            </table>
            
            <h2>Médicos</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nome</th>
                    <th>Especialidade</th>
                    <th>CRM</th>
                </tr>
    """

    # Adicionando os dados de Médicos
    for doctor in doctors:
        result += f"""
            <tr>
                <td>{doctor.id}</td>
                <td>{doctor.name}</td>
                <td>{doctor.specialty}</td>
                <td>{doctor.crm}</td>
            </tr>
        """

    result += """
            </table>
            
            <h2>Consultas Agendadas</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Paciente (ID)</th>
                    <th>Médico (ID)</th>
                    <th>Data da Consulta</th>
                </tr>
    """

    # Adicionando os dados de Consultas Agendadas
    for appointment in appointments:
        result += f"""
            <tr>
                <td>{appointment.id}</td>
                <td>{appointment.user_id}</td>
                <td>{appointment.doctor_id}</td>
                <td>{appointment.appointment_date}</td>
            </tr>
        """

    result += """
            </table>
            
            <h2>Avaliações de Médicos</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Médico (ID)</th>
                    <th>Paciente (ID)</th>
                    <th>Nota</th>
                    <th>Comentário</th>
                </tr>
    """

    # Adicionando os dados de Avaliações de Médicos
    for rating in ratings:
        result += f"""
            <tr>
                <td>{rating.id}</td>
                <td>{rating.doctor_id}</td>
                <td>{rating.user_id}</td>
                <td>{rating.rating}</td>
                <td>{rating.review or 'Sem comentário'}</td>
            </tr>
        """

    result += """
            </table>
        </body>
    </html>
    """

    return result

# Função que carrega o usuário baseado no ID
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) or Doctor.query.get(int(user_id))

if __name__ == '__main__':
    app.run(debug=True)
