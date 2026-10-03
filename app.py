from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from functools import wraps

app = Flask(__name__)

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'student_assignment_system')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'student-assignment-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'zip', 'jpg', 'png', 'jpeg'}
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), nullable=True)
    year_of_study = db.Column(db.String(20), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FacultyApproval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    approval_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    student = db.relationship('User', foreign_keys=[student_id], backref='faculty_approvals_received')


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(120), nullable=False, default='General')
    description = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(80), nullable=False, default='General')
    year = db.Column(db.String(20), nullable=False, default='All')
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='submitted')
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)


class Seminar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(120), nullable=False, default='General')
    description = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(80), nullable=False, default='General')
    year = db.Column(db.String(20), nullable=False, default='All')
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    time = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(200), nullable=False, default='Main Hall')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentSeminar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seminar_id = db.Column(db.Integer, db.ForeignKey('seminar.id'), nullable=False)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)
    attendance = db.Column(db.Boolean, default=False)
    grade = db.Column(db.Float)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'faculty':
            return redirect(url_for('home'))
        if not current_user.is_approved:
            return redirect(url_for('pending_approval'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            return redirect(url_for('home'))
        if not current_user.is_approved:
            return redirect(url_for('pending_approval'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        if current_user.role == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        if current_user.role == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('home'))


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    selected_role = request.args.get('role', 'student')

    if request.method == 'POST':
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            username = payload.get('username')
            password = payload.get('password')
            role = payload.get('role', selected_role)
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', selected_role)

        if not username or not password:
            if request.is_json:
                return jsonify({'error': 'Username and password are required'}), 400
            flash('Username and password are required.', 'error')
            return render_template('login.html', role=role)

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if user.role != role:
                if request.is_json:
                    return jsonify({'error': 'Role mismatch. Please select the correct login type.'}), 401
                flash('Role mismatch. Please select the correct login type.', 'error')
                return render_template('login.html', role=role)

            if user.role in ['student', 'faculty'] and not user.is_approved:
                if request.is_json:
                    return jsonify({'error': 'Your account is still pending approval.'}), 401
                flash('Your account is still pending approval.', 'error')
                return redirect(url_for('pending_approval'))

            login_user(user)
            if request.is_json:
                return jsonify({'message': 'Login successful'}), 200

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            if user.role == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            return redirect(url_for('student_dashboard'))

        if request.is_json:
            return jsonify({'error': 'Invalid username or password'}), 401
        flash('Invalid username or password.', 'error')
        return render_template('login.html', role=role)

    return render_template('login.html', role=selected_role)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            username = payload.get('username')
            email = payload.get('email')
            password = payload.get('password')
            full_name = payload.get('full_name')
            role = payload.get('role', 'student')
            department = payload.get('department')
            year_of_study = payload.get('year_of_study')
        else:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            role = request.form.get('role', 'student')
            department = request.form.get('department')
            year_of_study = request.form.get('year_of_study')

        if not all([username, email, password, full_name]):
            if request.is_json:
                return jsonify({'error': 'Please fill in all required fields'}), 400
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html', role=role)

        if User.query.filter_by(username=username).first():
            if request.is_json:
                return jsonify({'error': 'Username already exists'}), 400
            flash('Username already exists.', 'error')
            return render_template('register.html', role=role)

        if User.query.filter_by(email=email).first():
            if request.is_json:
                return jsonify({'error': 'Email already exists'}), 400
            flash('Email already exists.', 'error')
            return render_template('register.html', role=role)

        user = User(
            username=username.strip(),
            email=email.strip(),
            password=generate_password_hash(password),
            full_name=full_name.strip(),
            role=role,
            department=department or None,
            year_of_study=year_of_study or None,
            is_approved=(role == 'admin')
        )
        db.session.add(user)
        db.session.commit()

        if request.is_json:
            return jsonify({'message': 'Registration successful! Please login.'}), 201
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login', role=role))

    return render_template('register.html', role='student')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/pending-approval')
@login_required
def pending_approval():
    return render_template('pending_approval.html', user=current_user)


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    faculty_count = User.query.filter_by(role='faculty', is_approved=True).count()
    student_count = User.query.filter_by(role='student', is_approved=True).count()
    pending_faculty = User.query.filter_by(role='faculty', is_approved=False).count()
    total_assignments = Assignment.query.count()
    total_seminars = Seminar.query.count()
    return render_template(
        'admin/dashboard.html',
        faculty_count=faculty_count,
        student_count=student_count,
        pending_faculty=pending_faculty,
        total_assignments=total_assignments,
        total_seminars=total_seminars,
    )


@app.route('/admin/faculty-approvals')
@admin_required
def admin_faculty_approvals():
    pending = User.query.filter_by(role='faculty', is_approved=False).all()
    return render_template('admin/faculty_approvals.html', faculty=pending)


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


@app.route('/admin/view-assignments')
@admin_required
def admin_view_assignments():
    assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()
    return render_template('admin/view_assignments.html', assignments=assignments)


@app.route('/admin/view-seminars')
@admin_required
def admin_view_seminars():
    seminars = Seminar.query.order_by(Seminar.date.asc()).all()
    return render_template('admin/view_seminars.html', seminars=seminars)


@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard():
    assignments = Assignment.query.filter_by(faculty_id=current_user.id).all()
    seminars = Seminar.query.filter_by(faculty_id=current_user.id).all()
    pending_approvals = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='pending').all()
    return render_template(
        'faculty/dashboard.html',
        assignments=assignments,
        seminars=seminars,
        pending_approvals=pending_approvals,
        assignment_count=len(assignments),
        seminar_count=len(seminars),
        pending_count=len(pending_approvals),
    )


@app.route('/faculty/student-approvals')
@faculty_required
def faculty_student_approvals():
    pending = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='pending').all()
    approved = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='approved').all()
    rejected = FacultyApproval.query.filter_by(faculty_id=current_user.id, status='rejected').all()
    return render_template('faculty/student_approvals.html', pending=pending, approved=approved, rejected=rejected)


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
        data = request.get_json(silent=True) or {}
        title = data.get('title')
        subject = data.get('subject') or 'General'
        description = data.get('description')
        department = data.get('department') or 'General'
        year = data.get('year') or 'All'
        due_date = parse_date(data.get('due_date'))

        if not all([title, description, due_date]):
            return jsonify({'error': 'Title, description, and due date are required'}), 400

        assignment = Assignment(
            title=title,
            subject=subject,
            description=description,
            department=department,
            year=year,
            faculty_id=current_user.id,
            due_date=due_date,
        )
        db.session.add(assignment)
        db.session.commit()
        return jsonify({'message': 'Assignment created successfully', 'id': assignment.id}), 201

    assignments = Assignment.query.filter_by(faculty_id=current_user.id).order_by(Assignment.due_date.asc()).all()
    return render_template('faculty/assignments.html', assignments=assignments)


@app.route('/faculty/assignment/<int:assignment_id>')
@faculty_required
def view_assignment_submissions(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment or assignment.faculty_id != current_user.id:
        return redirect(url_for('faculty_dashboard'))
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    return render_template('faculty/assignment_submissions.html', assignment=assignment, submissions=submissions)


@app.route('/faculty/grade-submission/<int:submission_id>', methods=['POST'])
@faculty_required
def grade_submission(submission_id):
    submission = Submission.query.get(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    assignment = Assignment.query.get(submission.assignment_id)
    if not assignment or assignment.faculty_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    submission.grade = data.get('grade')
    submission.feedback = data.get('feedback', '')
    submission.status = 'graded'
    db.session.commit()
    return jsonify({'message': 'Grade submitted successfully'}), 200


@app.route('/faculty/seminars', methods=['GET', 'POST'])
@faculty_required
def faculty_seminars():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = data.get('title')
        subject = data.get('subject') or 'General'
        description = data.get('description')
        department = data.get('department') or 'General'
        year = data.get('year') or 'All'
        seminar_date = parse_date(data.get('date'))
        seminar_time = data.get('time')
        location = data.get('location') or 'Main Hall'

        if not all([title, description, seminar_date]):
            return jsonify({'error': 'Title, description, and date are required'}), 400

        seminar = Seminar(
            title=title,
            subject=subject,
            description=description,
            department=department,
            year=year,
            faculty_id=current_user.id,
            date=seminar_date,
            time=seminar_time,
            location=location,
        )
        db.session.add(seminar)
        db.session.commit()
        return jsonify({'message': 'Seminar created successfully', 'id': seminar.id}), 201

    seminars = Seminar.query.filter_by(faculty_id=current_user.id).order_by(Seminar.date.asc()).all()
    return render_template('faculty/seminars.html', seminars=seminars)


@app.route('/faculty/assign-seminar/<int:seminar_id>')
@faculty_required
def assign_seminar(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if not seminar or seminar.faculty_id != current_user.id:
        return redirect(url_for('faculty_seminars'))

    approved_students = User.query.filter_by(role='student', is_approved=True).all()
    assigned_students = StudentSeminar.query.filter_by(seminar_id=seminar_id).all()
    assigned_ids = {row.student_id for row in assigned_students}
    available_students = [student for student in approved_students if student.id not in assigned_ids]
    return render_template('faculty/assign_seminar.html', seminar=seminar, students=available_students)


@app.route('/faculty/add-student-to-seminar/<int:seminar_id>/<int:student_id>', methods=['POST'])
@faculty_required
def add_student_to_seminar(seminar_id, student_id):
    seminar = Seminar.query.get(seminar_id)
    if not seminar or seminar.faculty_id != current_user.id:
        return jsonify({'error': 'Seminar not found'}), 404

    existing = StudentSeminar.query.filter_by(student_id=student_id, seminar_id=seminar_id).first()
    if existing:
        return jsonify({'error': 'Student already assigned'}), 400

    record = StudentSeminar(student_id=student_id, seminar_id=seminar_id)
    db.session.add(record)
    db.session.commit()
    return jsonify({'message': 'Student assigned to seminar successfully'}), 201


@app.route('/faculty/seminar/<int:seminar_id>')
@faculty_required
def view_seminar_students(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if not seminar or seminar.faculty_id != current_user.id:
        return redirect(url_for('faculty_seminars'))
    rows = db.session.query(User, StudentSeminar).join(StudentSeminar, StudentSeminar.student_id == User.id).filter(
        StudentSeminar.seminar_id == seminar_id
    ).all()
    return render_template('faculty/seminar_students.html', seminar=seminar, rows=rows)


@app.route('/faculty/mark-attendance/<int:student_seminar_id>', methods=['POST'])
@faculty_required
def mark_attendance(student_seminar_id):
    record = StudentSeminar.query.get(student_seminar_id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404
    data = request.get_json(silent=True) or {}
    record.attendance = bool(data.get('attendance', False))
    record.grade = data.get('grade')
    db.session.commit()
    return jsonify({'message': 'Attendance updated'}), 200


@app.route('/faculty/delete-assignment/<int:assignment_id>', methods=['POST'])
@faculty_required
def delete_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if assignment and assignment.faculty_id == current_user.id:
        db.session.delete(assignment)
        db.session.commit()
        return jsonify({'message': 'Assignment deleted'}), 200
    return jsonify({'error': 'Assignment not found'}), 404


@app.route('/faculty/delete-seminar/<int:seminar_id>', methods=['POST'])
@faculty_required
def delete_seminar(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if seminar and seminar.faculty_id == current_user.id:
        db.session.delete(seminar)
        db.session.commit()
        return jsonify({'message': 'Seminar deleted'}), 200
    return jsonify({'error': 'Seminar not found'}), 404


@app.route('/student/dashboard')
@student_required
def student_dashboard():
    approvals = FacultyApproval.query.filter_by(student_id=current_user.id).all()
    assigned_seminars = db.session.query(Seminar).join(StudentSeminar, StudentSeminar.seminar_id == Seminar.id).filter(
        StudentSeminar.student_id == current_user.id
    ).all()
    approved_faculty_ids = [item.faculty_id for item in FacultyApproval.query.filter_by(student_id=current_user.id, status='approved').all()]
    assignments = Assignment.query.filter(Assignment.faculty_id.in_(approved_faculty_ids)).all() if approved_faculty_ids else []
    return render_template(
        'student/dashboard.html',
        approvals=approvals,
        seminars=assigned_seminars,
        assignments=assignments,
        approval_count=len(approvals),
        seminar_count=len(assigned_seminars),
        assignment_count=len(assignments),
    )


@app.route('/student/find-faculty')
@student_required
def find_faculty():
    approved_faculty = User.query.filter_by(role='faculty', is_approved=True).all()
    my_approvals = FacultyApproval.query.filter_by(student_id=current_user.id).all()
    applied_ids = {item.faculty_id for item in my_approvals}
    available_faculty = [faculty for faculty in approved_faculty if faculty.id not in applied_ids]
    return render_template('student/find_faculty.html', faculty=available_faculty)


@app.route('/student/apply-to-faculty/<int:faculty_id>', methods=['POST'])
@student_required
def apply_to_faculty(faculty_id):
    faculty = User.query.get(faculty_id)
    if not faculty or faculty.role != 'faculty':
        return jsonify({'error': 'Faculty not found'}), 404

    existing = FacultyApproval.query.filter_by(student_id=current_user.id, faculty_id=faculty_id).first()
    if existing:
        return jsonify({'error': 'Already applied to this faculty'}), 400

    approval = FacultyApproval(faculty_id=faculty_id, student_id=current_user.id, status='pending')
    db.session.add(approval)
    db.session.commit()
    return jsonify({'message': 'Application sent successfully'}), 201


@app.route('/student/assignments')
@student_required
def student_assignments():
    approved_faculty_ids = [item.faculty_id for item in FacultyApproval.query.filter_by(student_id=current_user.id, status='approved').all()]
    assignments = Assignment.query.filter(Assignment.faculty_id.in_(approved_faculty_ids)).order_by(Assignment.due_date.asc()).all() if approved_faculty_ids else []
    return render_template('student/assignments.html', assignments=assignments)


@app.route('/student/assignment/<int:assignment_id>')
@student_required
def view_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return redirect(url_for('student_assignments'))
    submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    return render_template('student/assignment_detail.html', assignment=assignment, submission=submission)


@app.route('/student/submit-assignment/<int:assignment_id>', methods=['POST'])
@student_required
def submit_assignment(assignment_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    filename = secure_filename(f"{current_user.id}_{assignment_id}_{datetime.utcnow().timestamp()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    existing_submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    if existing_submission:
        if os.path.exists(existing_submission.file_path):
            os.remove(existing_submission.file_path)
        db.session.delete(existing_submission)

    submission = Submission(assignment_id=assignment_id, student_id=current_user.id, file_path=filepath)
    db.session.add(submission)
    db.session.commit()
    return jsonify({'message': 'Assignment submitted successfully'}), 201


@app.route('/student/seminars')
@student_required
def student_seminars():
    seminars = db.session.query(Seminar).join(StudentSeminar, StudentSeminar.seminar_id == Seminar.id).filter(
        StudentSeminar.student_id == current_user.id
    ).all()
    return render_template('student/seminars.html', seminars=seminars)


@app.route('/student/seminar/<int:seminar_id>')
@student_required
def view_seminar(seminar_id):
    record = StudentSeminar.query.filter_by(student_id=current_user.id, seminar_id=seminar_id).first()
    if not record:
        return redirect(url_for('student_seminars'))
    seminar = Seminar.query.get(seminar_id)
    return render_template('student/seminar_detail.html', seminar=seminar, student_seminar=record)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error.html', error='Internal server error'), 500


def ensure_admin_user():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username=ADMIN_USERNAME).first():
            admin = User(
                username=ADMIN_USERNAME,
                email='admin@example.com',
                password=generate_password_hash(ADMIN_PASSWORD),
                full_name='System Administrator',
                role='admin',
                is_approved=True,
            )
            db.session.add(admin)
            db.session.commit()
            print(f'Created admin user: {ADMIN_USERNAME} / {ADMIN_PASSWORD}')


if __name__ == '__main__':
    ensure_admin_user()
    app.run(debug=True, host='0.0.0.0', port=5000)
