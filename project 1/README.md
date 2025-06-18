# Flask Blog Project

## Overview
This is a Flask-based blog application with user authentication, post creation, comments, likes, messaging, friendships, notifications, and theming support.

## Features
- User registration and login with role-based access control
- Create, edit, and view posts with images and videos
- Comment and like posts
- User messaging and friendships
- Notifications for user activities
- Theme support with light, dark, and blue themes
- File uploads with size and type validation

## Setup Instructions

1. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python run.py
   ```

4. Access the app at `http://127.0.0.1:5000/`

## Notes
- Ensure `email_validator` is installed for email validation support.
- Static files are located in `app/static/`.
- Templates are located in `app/templates/`.
- Database is SQLite by default (`instance/site.db`).

## License
MIT License
