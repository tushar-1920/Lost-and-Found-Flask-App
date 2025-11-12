from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secretkey'

# Uploads & Database Config
UPLOAD_FOLDER = 'uploaded'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lost_and_found.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MODELS
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(128), nullable=False)

    sent_messages = db.relationship('Message', back_populates='sender', foreign_keys='Message.sender_id', lazy='dynamic')
    received_messages = db.relationship('Message', back_populates='receiver', foreign_keys='Message.receiver_id', lazy='dynamic')
    comments = db.relationship('Comment', backref='user', lazy='dynamic')
    lost_items = db.relationship('LostItem', backref='user', lazy='dynamic')
    found_items = db.relationship('FoundItem', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_type = db.Column(db.String(10))  # lost/found
    item_id = db.Column(db.Integer)

    sender = db.relationship('User', back_populates='sent_messages', foreign_keys=[sender_id])
    receiver = db.relationship('User', back_populates='received_messages', foreign_keys=[receiver_id])

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('lost_item.id'))
    found_item_id = db.Column(db.Integer, db.ForeignKey('found_item.id'))

class LostItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    location = db.Column(db.String(200))
    image = db.Column(db.String(120), nullable=False)
    date_lost = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='lost_item', lazy='dynamic')

class FoundItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(120), nullable=False)
    date_found = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='found_item', lazy='dynamic')


class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')



@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ROUTES
@app.route('/')
def get_started():
    return render_template("get_started.html")

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')




@app.route('/home')
def home():
    lost_items = LostItem.query.order_by(LostItem.date_lost.desc()).all()
    found_items = FoundItem.query.order_by(FoundItem.date_found.desc()).all()
    comments = Comment.query.order_by(Comment.timestamp.desc()).all()
    return render_template('index.html', lost=lost_items, found=found_items, comments=comments)


# For viewing all shared stories
@app.route('/stories')
def stories():
    all_stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('stories.html', stories=all_stories)

# For submitting a story (only for logged-in users)
@app.route('/share_story', methods=['GET', 'POST'])
@login_required
def share_story():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_story = Story(title=title, content=content, user_id=current_user.id)
        db.session.add(new_story)
        db.session.commit()
        flash('Your story has been shared!')
        return redirect(url_for('stories'))
    return render_template('share_story.html')


@app.route('/stories_wall')
def stories_wall():
    stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('stories_wall.html', stories=stories)

@app.route('/submit_story', methods=['GET', 'POST'])
@login_required
def submit_story():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = current_user.id

        new_story = Story(title=title, content=content, user_id=user_id)
        db.session.add(new_story)
        db.session.commit()

        # 👇 Redirect to the stories wall after successful submission
        return redirect(url_for('stories_wall'))

    return render_template('submit_story.html')


@app.route('/chatbot', methods=['POST'])
def chatbot():
    user_message = request.json.get('message', '').lower()
    if "lost" in user_message:
        reply = "To report a lost item, go to 'Post Lost Item' and fill in the form."
    elif "found" in user_message:
        reply = "To report a found item, click on 'Post Found Item' and provide details."
    elif "search" in user_message:
        reply = "To search items, use the 'Search Lost' or 'Search Found' section."
    elif "delete item" in user_message:
        reply = "To delete your post, go to your dashboard and click the delete icon."
    elif "edit" in user_message:
        reply = "To edit your item, click the edit button on your post in the dashboard."
    elif "help" in user_message:
        reply = "I can help you report, search, or view items. Try typing 'lost', 'found', or 'search'."
    else:
        reply = "I'm not sure how to help with that. Try typing 'lost', 'found', or 'search'."
    return jsonify({'reply': reply})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/post_lost', methods=['GET', 'POST'])
@login_required
def post_lost():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['location']
        image = request.files['image']
        if image.filename == '':
            flash('No image selected!')
            return redirect(request.url)
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        lost_item = LostItem(title=title, description=description, category=category,
                             location=location, image=filename, user_id=current_user.id)
        db.session.add(lost_item)
        db.session.commit()
        flash('Lost item posted successfully!')
        return redirect(url_for('home'))
    return render_template('post_lost.html')

@app.route('/post_found', methods=['GET', 'POST'])
@login_required
def post_found():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        image = request.files['image']
        if image.filename == '':
            flash('No image selected!')
            return redirect(request.url)
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        found_item = FoundItem(title=title, description=description,
                               image=filename, user_id=current_user.id)
        db.session.add(found_item)
        db.session.commit()
        flash('Found item posted successfully!')
        return redirect(url_for('home'))
    return render_template('post_found.html')

@app.route('/add_comment/<item_type>/<int:item_id>', methods=['POST'])
@login_required
def add_comment(item_type, item_id):
    content = request.form['content']
    if not content:
        flash("Comment cannot be empty.")
        return redirect(url_for('home'))

    comment = Comment(content=content, user_id=current_user.id)
    if item_type == 'lost':
        comment.lost_item_id = item_id
    elif item_type == 'found':
        comment.found_item_id = item_id

    db.session.add(comment)
    db.session.commit()
    flash("Comment added!")
    return redirect(url_for('home'))

@app.route('/contact_owner/<item_type>/<int:item_id>')
@login_required
def contact_owner(item_type, item_id):
    return render_template("contact_owner.html", item_type=item_type, item_id=item_id)

@app.route('/send_message/<item_type>/<int:item_id>', methods=['POST'])
@login_required
def send_message(item_type, item_id):
    content = request.form['content']
    if item_type == 'lost':
        item = LostItem.query.get_or_404(item_id)
    else:
        item = FoundItem.query.get_or_404(item_id)

    receiver = item.user
    msg = Message(content=content, sender_id=current_user.id, receiver_id=receiver.id,
                  item_type=item_type, item_id=item_id)
    db.session.add(msg)
    db.session.commit()
    flash('Your message has been sent!')
    return redirect(url_for('home'))

@app.route('/inbox')
@login_required
def inbox():
    messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.timestamp.desc()).all()
    return render_template('inbox.html', messages=messages)

@app.route('/messages')
@login_required
def messages():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('messages.html', users=users)

@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        content = request.form['content']
        msg = Message(sender_id=current_user.id, receiver_id=user.id, content=content)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('chat', user_id=user.id))

    sent = Message.query.filter_by(sender_id=current_user.id, receiver_id=user.id)
    received = Message.query.filter_by(sender_id=user.id, receiver_id=current_user.id)
    all_messages = sent.union(received).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', user=user, messages=all_messages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        phone = request.form.get('phone')
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('register'))
        user = User(email=email, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5000)

