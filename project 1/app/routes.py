from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import Post, Comment, Like, Message, Friendship, Notification, User, Report
from app import db
import os
from werkzeug.utils import secure_filename
import ffmpeg
import bleach
from werkzeug.security import generate_password_hash

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4', 'mov'}

MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB
MAX_VIDEO_SIZE = 8 * 1024 * 1024  # 8 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_video_duration(filepath):
    try:
        probe = ffmpeg.probe(filepath)
        duration = float(probe['format']['duration'])
        return duration <= 1200  # 20 minutes
    except:
        return False

def create_notification(user_id, content):
    content = bleach.clean(content)
    notification = Notification(user_id=user_id, content=content)
    db.session.add(notification)
    db.session.commit()

@main.route('/')
def index():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('index.html', posts=posts)

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'Admin':
        posts = Post.query.all()
    else:
        posts = Post.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', posts=posts)

@main.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if current_user.role not in ['Author', 'Admin', 'User']:
        flash('Unauthorized', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        title = bleach.clean(request.form['title'])
        content = bleach.clean(request.form['content'])
        image = request.files.get('image')
        video = request.files.get('video')
        image_filename = video_filename = None

        if image and allowed_file(image.filename):
            if image.content_length and image.content_length > MAX_IMAGE_SIZE:
                flash('Image must be 8MB or less.', 'danger')
                return redirect(url_for('main.new_post'))
            image_filename = secure_filename(image.filename)
            image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename))

        if video and allowed_file(video.filename):
            if video.content_length and video.content_length > MAX_VIDEO_SIZE:
                flash('Video must be 8MB or less.', 'danger')
                return redirect(url_for('main.new_post'))
            video_filename = secure_filename(video.filename)
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], video_filename)
            video.save(temp_path)
            if not validate_video_duration(temp_path):
                flash('Video must be 60 seconds or less', 'danger')
                return redirect(url_for('main.new_post'))
        
        post = Post(title=title, content=content, image=image_filename, video=video_filename, author=current_user)
        db.session.add(post)
        db.session.commit()
        
        followers = Friendship.query.filter_by(followed_id=current_user.id).all()
        for follower in followers:
            create_notification(follower.follower_id, f"{current_user.username} posted a new blog: {title}")
        
        flash('Post created!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('create_post.html')

@main.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST' and current_user.is_authenticated:
        content = bleach.clean(request.form['content'])
        comment = Comment(content=content, post=post, author=current_user)
        db.session.add(comment)
        db.session.commit()
        if post.author.id != current_user.id:
            create_notification(post.author.id, f"{current_user.username} commented on your post: {post.title}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'author_id': current_user.id,
                'author_username': current_user.username,
                'author_profile_picture': url_for('static', filename='uploads/' + current_user.profile_picture),
                'content': comment.content,
                'date_posted': comment.date_posted.strftime('%b %d, %Y %H:%M')
            })
        flash('Comment added!', 'success')
        return redirect(url_for('main.post', post_id=post_id))
    return render_template('post.html', post=post)

@main.route('/like/<int:post_id>/<action>')
@login_required
def like_action(post_id, action):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if action == 'like' and not like:
        db.session.add(Like(user_id=current_user.id, post_id=post_id, is_like=True))
        if post.author.id != current_user.id:
            create_notification(post.author.id, f"{current_user.username} liked your post: {post.title}")
    elif action == 'dislike' and not like:
        db.session.add(Like(user_id=current_user.id, post_id=post_id, is_like=False))
        if post.author.id != current_user.id:
            create_notification(post.author.id, f"{current_user.username} disliked your post: {post.title}")
    elif like:
        db.session.delete(like)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        likes = len([l for l in post.likes if l.is_like])
        dislikes = len([l for l in post.likes if not l.is_like])
        return jsonify({'likes': likes, 'dislikes': dislikes})

    return redirect(request.referrer or url_for('main.index'))

@main.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = bleach.clean(request.form['query'])
        posts = Post.query.filter(Post.title.ilike(f'%{query}%') | Post.content.ilike(f'%{query}%')).all()
        users = User.query.filter(User.username.ilike(f'%{query}%')).all()
        return render_template('search.html', posts=posts, users=users, query=query)
    return render_template('search.html', posts=[], users=[], query='')

@main.route('/inbox', methods=['GET', 'POST'])
@login_required
def inbox():
    if request.method == 'POST':
        recipient_id = request.form['recipient_id']
        content = bleach.clean(request.form['content'])
        recipient = User.query.get_or_404(recipient_id)
        message = Message(content=content, sender_id=current_user.id, recipient_id=recipient_id)
        db.session.add(message)
        db.session.commit()
        create_notification(recipient_id, f"{current_user.username} sent you a message")
        flash('Message sent!', 'success')
        return redirect(url_for('main.inbox'))
    
    messages = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
    ).order_by(Message.date_sent.desc()).all()
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('inbox.html', messages=messages, users=users)

@main.route('/conversation/<int:user_id>')
@login_required
def conversation(user_id):
    other_user = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.date_sent.asc()).all()
    
    for message in messages:
        if message.recipient_id == current_user.id and not message.read:
            message.read = True
    db.session.commit()
    
    return render_template('conversation.html', messages=messages, other_user=other_user)

@main.route('/friends')
@login_required
def friends():
    following = Friendship.query.filter_by(follower_id=current_user.id).all()
    followers = Friendship.query.filter_by(followed_id=current_user.id).all()
    all_users = User.query.filter(User.id != current_user.id).all()
    return render_template('friends.html', following=following, followers=followers, all_users=all_users)

@main.route('/manage_users')
@login_required
def manage_users():
    if current_user.role not in ['Manager', 'Admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@main.route('/moderate_posts')
@login_required
def moderate_posts():
    if current_user.role not in ['Manager', 'Admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('moderate_posts.html', posts=posts)

@main.route('/report/post/<int:post_id>', methods=['POST'])
@login_required
def report_post(post_id):
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Please provide a reason for reporting.', 'danger')
        return redirect(url_for('main.post', post_id=post_id))
    post = Post.query.get_or_404(post_id)
    report = Report(
        reported_user_id=post.user_id,
        reporter_user_id=current_user.id,
        post_id=post.id,
        reason=reason,
        status='Pending'
    )
    db.session.add(report)
    db.session.commit()
    flash('Post reported successfully.', 'success')
    return redirect(url_for('main.post', post_id=post_id))

@main.route('/report/user/<int:user_id>', methods=['POST'])
@login_required
def report_user(user_id):
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Please provide a reason for reporting.', 'danger')
        return redirect(url_for('main.profile', user_id=user_id))
    user = User.query.get_or_404(user_id)
    report = Report(
        reported_user_id=user.id,
        reporter_user_id=current_user.id,
        post_id=None,
        reason=reason,
        status='Pending'
    )
    db.session.add(report)
    db.session.commit()
    flash('User reported successfully.', 'success')
    return redirect(url_for('main.profile', user_id=user_id))

from sqlalchemy.orm import aliased

@main.route('/view_reports')
@login_required
def view_reports():
    if current_user.role not in ['Manager', 'Admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    User2 = aliased(User)
    reports = db.session.query(
        Report,
        User.username.label('reported_username'),
        User2.username.label('reporter_username')
    ).join(User, Report.reported_user_id == User.id).join(User2, Report.reporter_user_id == User2.id).all()
    return render_template('view_reports.html', reports=reports)

@main.route('/follow/<int:user_id>')
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot follow yourself', 'danger')
        return redirect(url_for('main.friends'))
    friendship = Friendship.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()
    if not friendship:
        friendship = Friendship(follower_id=current_user.id, followed_id=user_id)
        db.session.add(friendship)
        db.session.commit()
        create_notification(user_id, f"{current_user.username} started following you")
        flash(f'You are now following {user.username}', 'success')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success'})
    return redirect(url_for('main.friends'))

import logging
import os

logger = logging.getLogger(__name__)

@main.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if current_user.role == 'Manager':
        if user_to_delete.role != 'Manager':
            # Delete profile picture file if not default
            if user_to_delete.profile_picture and user_to_delete.profile_picture != 'default.jpg':
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], user_to_delete.profile_picture))
                except Exception as e:
                    logger.error(f"Error deleting profile picture: {e}")
            db.session.delete(user_to_delete)
            db.session.commit()
            logger.info(f"User {user_to_delete.username} deleted by {current_user.username}")
            flash(f'User {user_to_delete.username} deleted.', 'success')
        else:
            flash('Managers cannot delete other Managers.', 'danger')
    elif current_user.role == 'Admin':
        if user_to_delete.role == 'User':
            if user_to_delete.profile_picture and user_to_delete.profile_picture != 'default.jpg':
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], user_to_delete.profile_picture))
                except Exception as e:
                    logger.error(f"Error deleting profile picture: {e}")
            db.session.delete(user_to_delete)
            db.session.commit()
            logger.info(f"User {user_to_delete.username} deleted by {current_user.username}")
            flash(f'User {user_to_delete.username} deleted.', 'success')
        else:
            flash('Admins can only delete Users.', 'danger')
    else:
        flash('You do not have permission to delete users.', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user.role == 'Manager':
        # Delete associated files
        if post.image:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.image))
            except Exception as e:
                logger.error(f"Error deleting post image: {e}")
        if post.video:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.video))
            except Exception as e:
                logger.error(f"Error deleting post video: {e}")
        # Manager can delete any post
        db.session.delete(post)
        db.session.commit()
        logger.info(f"Post {post.id} deleted by Manager {current_user.username}")
        flash('Post deleted by Manager.', 'success')
    elif current_user.role == 'Admin':
        # Admin can delete posts by Users
        if post.author.role == 'User':
            if post.image:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.image))
                except Exception as e:
                    logger.error(f"Error deleting post image: {e}")
            if post.video:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.video))
                except Exception as e:
                    logger.error(f"Error deleting post video: {e}")
            db.session.delete(post)
            db.session.commit()
            logger.info(f"Post {post.id} deleted by Admin {current_user.username}")
            flash('Post deleted by Admin.', 'success')
        else:
            flash('Admins can only delete posts by Users.', 'danger')
    elif current_user.role == 'User' or current_user.role == 'Author':
        # User and Author can delete own posts
        if post.author.id == current_user.id:
            if post.image:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.image))
                except Exception as e:
                    logger.error(f"Error deleting post image: {e}")
            if post.video:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.video))
                except Exception as e:
                    logger.error(f"Error deleting post video: {e}")
            db.session.delete(post)
            db.session.commit()
            logger.info(f"Post {post.id} deleted by User {current_user.username}")
            flash('Your post has been deleted.', 'success')
        else:
            flash('Users and Authors can only delete their own posts.', 'danger')
    else:
        flash('You do not have permission to delete posts.', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/admin/create', methods=['GET', 'POST'])
@login_required
def create_admin():
    if current_user.role != 'Manager':
        flash('Only Managers can create Admins.', 'danger')
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('main.create_admin'))
        existing_user_email = User.query.filter_by(email=email).first()
        existing_user_username = User.query.filter_by(username=username).first()
        if existing_user_email:
            flash('Email already registered. Please use a different email.', 'danger')
            return redirect(url_for('main.create_admin'))
        if existing_user_username:
            flash('Username already taken. Please choose a different username.', 'danger')
            return redirect(url_for('main.create_admin'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_admin = User(username=username, email=email, password=hashed_password, role='Admin')
        db.session.add(new_admin)
        db.session.commit()
        flash('Admin account created successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('create_admin.html')

@main.route('/unfollow/<int:user_id>')
@login_required
def unfollow(user_id):
    friendship = Friendship.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        flash('Unfollowed user', 'success')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success'})
    return redirect(url_for('main.friends'))

@main.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.date_created.desc()).all()
    for notification in notifications:
        if not notification.read:
            notification.read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifications)

@main.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(user_id=user_id).order_by(Post.date_posted.desc()).all()
    followers_count = Friendship.query.filter_by(followed_id=user_id).count()
    following_count = Friendship.query.filter_by(follower_id=user_id).count()
    return render_template('profile.html', user=user, posts=posts, followers_count=followers_count, following_count=following_count)

@main.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        bio = bleach.clean(request.form.get('bio', '')[:200])
        theme = request.form.get('theme', 'light')
        profile_picture = request.files.get('profile_picture')

        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_picture = filename

        current_user.bio = bio
        current_user.theme = theme
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('main.profile', user_id=current_user.id))

    return render_template('edit_profile.html', user=current_user)
