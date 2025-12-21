import smtplib
import secrets
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Configuration
SMTP_SERVER = "smtp.zoho.in"
SMTP_PORT = 587
SMTP_EMAIL = "info@accuport.cloud"
SMTP_PASSWORD = "N7SJ0kDGwyxq"

def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def send_password_reset_email(to_email, username, new_password):
    """Send password reset email with new auto-generated password"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "AccuPort - Password Reset"
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email

        # Plain text version
        text = f"""
AccuPort Password Reset

Hello {username},

Your password has been reset. Here are your new login credentials:

Username: {username}
New Password: {new_password}

Please login and change your password immediately for security.

Login at: https://accuport.quantumautomata.in/login

If you did not request this reset, please contact your administrator immediately.

Best regards,
AccuPort Team
"""

        # HTML version
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0071e3; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f5f5f7; padding: 30px; border-radius: 0 0 8px 8px; }}
        .credentials {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .label {{ color: #86868b; font-size: 12px; text-transform: uppercase; }}
        .value {{ font-size: 18px; font-weight: 600; color: #1d1d1f; }}
        .warning {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin-top: 20px; }}
        .button {{ display: inline-block; background: #0071e3; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 8px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">AccuPort</h1>
            <p style="margin: 5px 0 0 0;">Password Reset</p>
        </div>
        <div class="content">
            <p>Hello <strong>{username}</strong>,</p>
            <p>Your password has been reset. Here are your new login credentials:</p>
            
            <div class="credentials">
                <div style="margin-bottom: 15px;">
                    <div class="label">Username</div>
                    <div class="value">{username}</div>
                </div>
                <div>
                    <div class="label">New Password</div>
                    <div class="value">{new_password}</div>
                </div>
            </div>
            
            <a href="https://accuport.quantumautomata.in/login" class="button">Login to AccuPort</a>
            
            <div class="warning">
                <strong>Security Notice:</strong> Please change your password after logging in. 
                If you did not request this reset, contact your administrator immediately.
            </div>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True, "Password reset email sent successfully"
    
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


def send_welcome_email(to_email, username, password):
    """Send welcome email to new user with their credentials"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Welcome to AccuPort - Your Login Credentials"
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0071e3; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f5f5f7; padding: 30px; border-radius: 0 0 8px 8px; }}
        .credentials {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .label {{ color: #86868b; font-size: 12px; text-transform: uppercase; }}
        .value {{ font-size: 18px; font-weight: 600; color: #1d1d1f; }}
        .button {{ display: inline-block; background: #0071e3; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 8px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Welcome to AccuPort</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{username}</strong>,</p>
            <p>Your AccuPort account has been created. Here are your login credentials:</p>
            
            <div class="credentials">
                <div style="margin-bottom: 15px;">
                    <div class="label">Username</div>
                    <div class="value">{username}</div>
                </div>
                <div>
                    <div class="label">Password</div>
                    <div class="value">{password}</div>
                </div>
            </div>
            
            <a href="https://accuport.quantumautomata.in/login" class="button">Login to AccuPort</a>
            
            <p style="margin-top: 20px; color: #86868b; font-size: 14px;">
                Please change your password after your first login for security.
            </p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True, "Welcome email sent successfully"
    
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
