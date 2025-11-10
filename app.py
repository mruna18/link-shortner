from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
import secrets
import string
import hashlib
import uuid
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# ============================================================================
# FLASK APP SETUP
# ============================================================================
app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-in-production'  # Change this!
app.config['SESSION_TYPE'] = 'filesystem'

# ============================================================================
# FLASK-LOGIN SETUP
# ============================================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page!'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(id=user_data[0], username=user_data[1], email=user_data[2])
    return None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def init_database():
    """Initialize database with users table"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shortened_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            custom_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INTEGER DEFAULT 0,
            user_id INTEGER,
            is_public BOOLEAN DEFAULT 1,
            is_guest BOOLEAN DEFAULT 0,
            guest_token TEXT,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_short_code(length=6):
    """Generate random short code"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_guest_token():
    """Generate unique token for guest URLs"""
    return str(uuid.uuid4())[:8]

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill all fields!', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'error')
            return render_template('register.html')
        
        # Hash password and save user
        password_hash = hash_password(password)
        
        conn = sqlite3.connect('urls.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (username, email, password_hash))
            
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                flash('Username already exists!', 'error')
            elif 'email' in str(e):
                flash('Email already exists!', 'error')
            else:
                flash('Registration failed!', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please fill all fields!', 'error')
            return render_template('login.html')
        
        conn = sqlite3.connect('urls.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, password_hash FROM users 
            WHERE username = ? OR email = ?
        ''', (username, username))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and user_data[3] == hash_password(password):
            user = User(id=user_data[0], username=user_data[1], email=user_data[2])
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username/email or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('index'))

# ============================================================================
# GUEST URL SHORTENING ROUTES
# ============================================================================
@app.route('/shorten-guest', methods=['POST'])
def shorten_guest():
    """Shorten URL for guest users (no registration required)"""
    long_url = request.form.get('long_url')
    custom_name = request.form.get('custom_name')
    
    if not long_url:
        flash('Please enter a URL!', 'error')
        return redirect(url_for('index'))
    
    short_code = custom_name if custom_name else generate_short_code()
    guest_token = generate_guest_token()
    
    # Guest URLs expire in 30 days
    expires_at = datetime.now() + timedelta(days=30)
    
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO shortened_urls (long_url, short_code, custom_name, is_guest, guest_token, expires_at, is_public)
            VALUES (?, ?, ?, 1, ?, ?, 1)
        ''', (long_url, short_code, custom_name, guest_token, expires_at))
        
        conn.commit()
        short_url = f"{request.host_url}{short_code}"
        
        # Store guest token in session so they can manage their URLs
        if 'guest_tokens' not in session:
            session['guest_tokens'] = []
        session['guest_tokens'].append(guest_token)
        session.modified = True
        
        return render_template('guest_result.html', 
                             short_url=short_url, 
                             long_url=long_url,
                             guest_token=guest_token)
        
    except sqlite3.IntegrityError:
        flash('That custom name is already taken! Please choose another.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/guest-urls')
def guest_urls():
    """Show guest user their shortened URLs"""
    guest_tokens = session.get('guest_tokens', [])
    
    if not guest_tokens:
        return render_template('guest_urls.html', urls=[])
    
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    placeholders = ','.join('?' for _ in guest_tokens)
    cursor.execute(f'''
        SELECT short_code, long_url, custom_name, created_at, click_count, guest_token, expires_at
        FROM shortened_urls 
        WHERE guest_token IN ({placeholders}) AND expires_at > datetime('now')
        ORDER BY created_at DESC
    ''', guest_tokens)
    
    guest_urls = cursor.fetchall()
    conn.close()
    
    return render_template('guest_urls.html', urls=guest_urls)

# ============================================================================
# MAIN APPLICATION ROUTES
# ============================================================================
@app.route('/')
def index():
    """Homepage - shows public URLs and allows shortening for both guest and logged-in users"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # Get recent public URLs (both user and guest URLs that are public)
    cursor.execute('''
        SELECT short_code, long_url, custom_name, created_at, click_count, is_guest
        FROM shortened_urls 
        WHERE is_public = 1 AND (expires_at > datetime('now') OR expires_at IS NULL)
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    public_urls = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', public_urls=public_urls)

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with personal statistics"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # Get user's URLs
    cursor.execute('''
        SELECT short_code, long_url, custom_name, created_at, click_count, is_public
        FROM shortened_urls 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (current_user.id,))
    
    user_urls = cursor.fetchall()
    
    # Get user statistics
    cursor.execute('''
        SELECT 
            COUNT(*) as total_urls,
            SUM(click_count) as total_clicks,
            AVG(click_count) as avg_clicks
        FROM shortened_urls 
        WHERE user_id = ?
    ''', (current_user.id,))
    
    stats = cursor.fetchone()
    conn.close()
    
    return render_template('dashboard.html', 
                         urls=user_urls,
                         total_urls=stats[0] if stats else 0,
                         total_clicks=stats[1] if stats and stats[1] else 0,
                         avg_clicks=round(stats[2], 1) if stats and stats[2] else 0)

@app.route('/shorten', methods=['POST'])
@login_required
def shorten_url():
    """Shorten URL for logged-in users"""
    long_url = request.form.get('long_url')
    custom_name = request.form.get('custom_name')
    is_public = request.form.get('is_public') == 'on'
    
    if not long_url:
        flash('Please enter a URL!', 'error')
        return redirect(url_for('dashboard'))
    
    short_code = custom_name if custom_name else generate_short_code()
    
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO shortened_urls (long_url, short_code, custom_name, user_id, is_public)
            VALUES (?, ?, ?, ?, ?)
        ''', (long_url, short_code, custom_name, current_user.id, is_public))
        
        conn.commit()
        short_url = f"{request.host_url}{short_code}"
        
        flash(f'URL shortened successfully! Your short URL: {short_url}', 'success')
        return redirect(url_for('dashboard'))
        
    except sqlite3.IntegrityError:
        flash('That custom name is already taken! Please choose another.', 'error')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/<short_code>')
def redirect_to_original(short_code):
    """Redirect short URLs (works for public URLs and user's own URLs)"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # Find URL - allow access to public URLs or user's own URLs
    if current_user.is_authenticated:
        cursor.execute('''
            SELECT long_url FROM shortened_urls 
            WHERE short_code = ? AND (is_public = 1 OR user_id = ? OR (is_guest = 1 AND expires_at > datetime('now')))
        ''', (short_code, current_user.id))
    else:
        cursor.execute('''
            SELECT long_url FROM shortened_urls 
            WHERE short_code = ? AND (is_public = 1 OR (is_guest = 1 AND expires_at > datetime('now')))
        ''', (short_code,))
    
    result = cursor.fetchone()
    
    if result:
        # Update click count
        cursor.execute('''
            UPDATE shortened_urls 
            SET click_count = click_count + 1 
            WHERE short_code = ?
        ''', (short_code,))
        conn.commit()
        conn.close()
        return redirect(result[0])
    else:
        conn.close()
        flash('Short URL not found or not accessible!', 'error')
        return redirect(url_for('index'))

@app.route('/stats')
@login_required
def stats_page():
    """User's personal statistics"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT short_code, long_url, custom_name, created_at, click_count, is_public
        FROM shortened_urls 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (current_user.id,))
    
    user_urls = cursor.fetchall()
    conn.close()
    
    return render_template('stats.html', urls=user_urls)

@app.route('/my-links')
@login_required
def my_links():
    """Page showing all short links for easy copying"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT short_code, long_url, custom_name, created_at, click_count, is_public
        FROM shortened_urls 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (current_user.id,))
    
    user_urls = cursor.fetchall()
    conn.close()
    
    return render_template('my_links.html', urls=user_urls)

@app.route('/visualize')
@login_required
def visualize_data():
    """User's data visualization"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    # Get user's URLs
    cursor.execute('''
        SELECT id, short_code, custom_name, click_count, created_at, is_public, long_url
        FROM shortened_urls 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (current_user.id,))
    
    user_urls = cursor.fetchall()
    
    # Get user statistics
    cursor.execute('''
        SELECT COUNT(*), SUM(click_count) 
        FROM shortened_urls WHERE user_id = ?
    ''', (current_user.id,))
    
    stats = cursor.fetchone()
    total_urls = stats[0] if stats else 0
    total_clicks = stats[1] if stats and stats[1] else 0
    
    conn.close()
    
    return render_template('visualize.html', 
                         urls=user_urls,
                         total_urls=total_urls,
                         total_clicks=total_clicks)

@app.route('/cleanup-expired-urls')
def cleanup_expired_urls():
    """Clean up expired guest URLs (can be run periodically)"""
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM shortened_urls 
        WHERE is_guest = 1 AND expires_at < datetime('now')
    ''')
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return f"Cleaned up {deleted_count} expired guest URLs"

# ============================================================================
# RUN APPLICATION
# ============================================================================
if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)