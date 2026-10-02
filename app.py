from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_change_this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///assignment_management.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'zip', 'jpg', 'png', 'jpeg'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ===================== DATABASE MODELS =====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, faculty, student
    full_name = db.Column(db.String(120), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    faculty_approvals = db.relationship('FacultyApproval', backref='faculty', lazy=True, foreign_keys='FacultyApproval.faculty_id')
    student_seminars = db.relationship('StudentSeminar', backref='student', lazy=True, foreign_keys='StudentSeminar.student_id')
    assignments = db.relationship('Assignment', backref='faculty', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)

class FacultyApproval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approval_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    student = db.relationship('User', foreign_keys=[student_id], backref='faculty_approvals_received')

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade='all, delete-orphan')

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='submitted')  # submitted, graded
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)

class Seminar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    faculty_assigned = db.relationship('User', backref='seminars_created')
    student_seminars = db.relationship('StudentSeminar', backref='seminar', lazy=True, cascade='all, delete-orphan')

class StudentSeminar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seminar_id = db.Column(db.Integer, db.ForeignKey('seminar.id'), nullable=False)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)
    attendance = db.Column(db.Boolean, default=False)
    grade = db.Column(db.Float)

# ===================== LOGIN MANAGER =====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'faculty':
            return redirect(url_for('login'))
        if not current_user.is_approved:
            return redirect(url_for('pending_approval'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            return redirect(url_for('login'))
        if not current_user.is_approved:
            return redirect(url_for('pending_approval'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===================== AUTHENTICATION ROUTES =====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        full_name = data.get('full_name')
        role = data.get('role', 'student')
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            full_name=full_name,
            role=role,
            is_approved=(role == 'admin')  # Admin users are auto-approved
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'Registration successful! Please login.'}), 201
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return jsonify({'message': 'Login successful'}), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/pending-approval')
@login_required
def pending_approval():
    return render_template('pending_approval.html', user=current_user)

# ===================== ADMIN ROUTES =====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    faculty_count = User.query.filter_by(role='faculty').count()
    student_count = User.query.filter_by(role='student').count()
    pending_faculty = User.query.filter_by(role='faculty', is_approved=False).count()
    
    return render_template('admin/dashboard.html', 
                         faculty_count=faculty_count,
                         student_count=student_count,
                         pending_faculty=pending_faculty)

@app.route('/admin/faculty-approvals')
@admin_required
def admin_faculty_approvals():
    pending_faculty = User.query.filter_by(role='faculty', is_approved=False).all()
    return render_template('admin/faculty_approvals.html', faculty=pending_faculty)

@app.route('/admin/approve-faculty/<int:faculty_id>', methods=['POST'])
@admin_required
def approve_faculty(faculty_id):
    faculty = User.query.get(faculty_id)
    if faculty and faculty.role == 'faculty':
        faculty.is_approved = True
        db.session.commit()
        return jsonify({'message': 'Faculty approved successfully'}), 200
    return jsonify({'error': 'Faculty not found'}), 404

@app.route('/admin/reject-faculty/<int:faculty_id>', methods=['POST'])
@admin_required
def reject_faculty(faculty_id):
    faculty = User.query.get(faculty_id)
    if faculty and faculty.role == 'faculty':
        db.session.delete(faculty)
        db.session.commit()
        return jsonify({'message': 'Faculty rejected'}), 200
    return jsonify({'error': 'Faculty not found'}), 404

@app.route('/admin/all-users')
@admin_required
def admin_all_users():
    faculty = User.query.filter_by(role='faculty').all()
    students = User.query.filter_by(role='student').all()
    return render_template('admin/all_users.html', faculty=faculty, students=students)

# ===================== FACULTY ROUTES =====================

@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard():
    assignments = Assignment.query.filter_by(faculty_id=current_user.id).all()
    seminars = Seminar.query.filter_by(faculty_id=current_user.id).all()
    pending_students = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='pending').all()
    
    return render_template('faculty/dashboard.html',
                         assignments=assignments,
                         seminars=seminars,
                         pending_students=pending_students)

@app.route('/faculty/student-approvals')
@faculty_required
def faculty_student_approvals():
    pending_approvals = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='pending').all()
    approved = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='approved').all()
    return render_template('faculty/student_approvals.html', 
                         pending=pending_approvals,
                         approved=approved)

@app.route('/faculty/approve-student/<int:approval_id>', methods=['POST'])
@faculty_required
def approve_student(approval_id):
    approval = FacultyApproval.query.get(approval_id)
    if approval and approval.faculty_id == current_user.id:
        approval.status = 'approved'
        approval.approval_date = datetime.utcnow()
        
        student = User.query.get(approval.student_id)
        if student:
            student.is_approved = True
        
        db.session.commit()
        return jsonify({'message': 'Student approved successfully'}), 200
    return jsonify({'error': 'Approval not found'}), 404

@app.route('/faculty/reject-student/<int:approval_id>', methods=['POST'])
@faculty_required
def reject_student(approval_id):
    approval = FacultyApproval.query.get(approval_id)
    if approval and approval.faculty_id == current_user.id:
        approval.status = 'rejected'
        approval.approval_date = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'Student rejected'}), 200
    return jsonify({'error': 'Approval not found'}), 404

@app.route('/faculty/assignments', methods=['GET', 'POST'])
@faculty_required
def faculty_assignments():
    if request.method == 'POST':
        data = request.get_json()
        assignment = Assignment(
            title=data.get('title'),
            description=data.get('description'),
            faculty_id=current_user.id,
            due_date=datetime.fromisoformat(data.get('due_date'))
        )
        db.session.add(assignment)
        db.session.commit()
        return jsonify({'message': 'Assignment created successfully'}), 201
    
    assignments = Assignment.query.filter_by(faculty_id=current_user.id).all()
    return render_template('faculty/assignments.html', assignments=assignments)

@app.route('/faculty/assignment/<int:assignment_id>')
@faculty_required
def view_assignment_submissions(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment or assignment.faculty_id != current_user.id:
        return redirect(url_for('faculty_dashboard'))
    
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    return render_template('faculty/assignment_submissions.html', 
                         assignment=assignment,
                         submissions=submissions)

@app.route('/faculty/grade-submission/<int:submission_id>', methods=['POST'])
@faculty_required
def grade_submission(submission_id):
    submission = Submission.query.get(submission_id)
    data = request.get_json()
    
    if submission:
        assignment = Assignment.query.get(submission.assignment_id)
        if assignment.faculty_id == current_user.id:
            submission.grade = data.get('grade')
            submission.feedback = data.get('feedback')
            submission.status = 'graded'
            db.session.commit()
            return jsonify({'message': 'Grade submitted successfully'}), 200
    
    return jsonify({'error': 'Submission not found'}), 404

@app.route('/faculty/seminars', methods=['GET', 'POST'])
@faculty_required
def faculty_seminars():
    if request.method == 'POST':
        data = request.get_json()
        seminar = Seminar(
            title=data.get('title'),
            description=data.get('description'),
            faculty_id=current_user.id,
            date=datetime.fromisoformat(data.get('date')),
            location=data.get('location')
        )
        db.session.add(seminar)
        db.session.commit()
        return jsonify({'message': 'Seminar created successfully'}), 201
    
    seminars = Seminar.query.filter_by(faculty_id=current_user.id).all()
    return render_template('faculty/seminars.html', seminars=seminars)

@app.route('/faculty/assign-seminar/<int:seminar_id>')
@faculty_required
def assign_seminar(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if not seminar or seminar.faculty_id != current_user.id:
        return redirect(url_for('faculty_seminars'))
    
    approved_students = User.query.filter_by(role='student', is_approved=True).all()
    assigned_students = db.session.query(StudentSeminar.student_id).filter_by(seminar_id=seminar_id).all()
    assigned_ids = [s[0] for s in assigned_students]
    
    available_students = [s for s in approved_students if s.id not in assigned_ids]
    
    return render_template('faculty/assign_seminar.html', 
                         seminar=seminar,
                         students=available_students)

@app.route('/faculty/add-student-to-seminar/<int:seminar_id>/<int:student_id>', methods=['POST'])
@faculty_required
def add_student_to_seminar(seminar_id, student_id):
    seminar = Seminar.query.get(seminar_id)
    
    if seminar and seminar.faculty_id == current_user.id:
        existing = StudentSeminar.query.filter_by(student_id=student_id, seminar_id=seminar_id).first()
        if not existing:
            student_seminar = StudentSeminar(student_id=student_id, seminar_id=seminar_id)
            db.session.add(student_seminar)
            db.session.commit()
            return jsonify({'message': 'Student assigned to seminar successfully'}), 201
        return jsonify({'error': 'Student already assigned'}), 400
    
    return jsonify({'error': 'Seminar not found'}), 404

@app.route('/faculty/seminar/<int:seminar_id>')
@faculty_required
def view_seminar_students(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if not seminar or seminar.faculty_id != current_user.id:
        return redirect(url_for('faculty_seminars'))
    
    students = db.session.query(User, StudentSeminar).join(StudentSeminar).filter(
        StudentSeminar.seminar_id == seminar_id
    ).all()
    
    return render_template('faculty/seminar_students.html', seminar=seminar, students=students)

@app.route('/faculty/mark-attendance/<int:student_seminar_id>', methods=['POST'])
@faculty_required
def mark_attendance(student_seminar_id):
    student_seminar = StudentSeminar.query.get(student_seminar_id)
    if student_seminar:
        data = request.get_json()
        student_seminar.attendance = data.get('attendance', False)
        student_seminar.grade = data.get('grade')
        db.session.commit()
        return jsonify({'message': 'Attendance marked'}), 200
    return jsonify({'error': 'Record not found'}), 404

# ===================== STUDENT ROUTES =====================

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    approvals = FacultyApproval.query.filter_by(student_id=current_user.id).all()
    seminars = db.session.query(Seminar).join(StudentSeminar).filter(
        StudentSeminar.student_id == current_user.id
    ).all()
    
    return render_template('student/dashboard.html', 
                         approvals=approvals,
                         seminars=seminars)

@app.route('/student/find-faculty')
@student_required
def find_faculty():
    approved_faculty = User.query.filter_by(role='faculty', is_approved=True).all()
    my_approvals = FacultyApproval.query.filter_by(student_id=current_user.id).all()
    applied_faculty_ids = [a.faculty_id for a in my_approvals]
    
    available_faculty = [f for f in approved_faculty if f.id not in applied_faculty_ids]
    
    return render_template('student/find_faculty.html', faculty=available_faculty)

@app.route('/student/apply-to-faculty/<int:faculty_id>', methods=['POST'])
@student_required
def apply_to_faculty(faculty_id):
    faculty = User.query.get(faculty_id)
    if faculty and faculty.role == 'faculty':
        existing = FacultyApproval.query.filter_by(student_id=current_user.id, faculty_id=faculty_id).first()
        if not existing:
            approval = FacultyApproval(
                faculty_id=faculty_id,
                student_id=current_user.id,
                status='pending'
            )
            db.session.add(approval)
            db.session.commit()
            return jsonify({'message': 'Application sent successfully'}), 201
        return jsonify({'error': 'Already applied to this faculty'}), 400
    return jsonify({'error': 'Faculty not found'}), 404

@app.route('/student/assignments')
@student_required
def student_assignments():
    # Get assignments from faculty members who approved this student
    approved_faculties = db.session.query(FacultyApproval.faculty_id).filter(
        FacultyApproval.student_id == current_user.id,
        FacultyApproval.status == 'approved'
    ).all()
    
    faculty_ids = [f[0] for f in approved_faculties]
    assignments = Assignment.query.filter(Assignment.faculty_id.in_(faculty_ids)).all() if faculty_ids else []
    
    return render_template('student/assignments.html', assignments=assignments)

@app.route('/student/assignment/<int:assignment_id>')
@student_required
def view_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    
    return render_template('student/assignment_detail.html', 
                         assignment=assignment,
                         submission=submission)

@app.route('/student/submit-assignment/<int:assignment_id>', methods=['POST'])
@student_required
def submit_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    filename = secure_filename(f"{current_user.id}_{assignment_id}_{datetime.utcnow().timestamp()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Remove old submission if exists
    old_submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    if old_submission:
        if os.path.exists(old_submission.file_path):
            os.remove(old_submission.file_path)
        db.session.delete(old_submission)
    
    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        file_path=filepath
    )
    db.session.add(submission)
    db.session.commit()
    
    return jsonify({'message': 'Assignment submitted successfully'}), 201

@app.route('/student/seminars')
@student_required
def student_seminars():
    seminars = db.session.query(Seminar).join(StudentSeminar).filter(
        StudentSeminar.student_id == current_user.id
    ).all()
    
    return render_template('student/seminars.html', seminars=seminars)

@app.route('/student/seminar/<int:seminar_id>')
@student_required
def view_seminar(seminar_id):
    student_seminar = StudentSeminar.query.filter_by(student_id=current_user.id, seminar_id=seminar_id).first()
    if not student_seminar:
        return redirect(url_for('student_seminars'))
    
    seminar = Seminar.query.get(seminar_id)
    return render_template('student/seminar_detail.html', 
                         seminar=seminar,
                         student_seminar=student_seminar)

# ===================== ERROR HANDLING =====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', error='Server error'), 500

# ===================== DATABASE INITIALIZATION =====================

def init_db():
    with app.app_context():
        db.create_all()
        
        # Create admin user if doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                password=generate_password_hash('admin123'),
                full_name='System Administrator',
                role='admin',
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: username=admin, password=admin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
