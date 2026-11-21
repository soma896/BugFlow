"""
BugFlow Aroma - Email Notification Service
Sends real-time email notifications for sign-up, workspace access, and alerts.
Supports standard SMTP (Gmail, Outlook, SendGrid, Brevo, AWS SES, or custom SMTP).
"""
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@bugflow.io"))
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ["true", "1", "yes"]

ROLE_DISPLAY_NAMES = {
    "admin": "Admin (System Administrator)",
    "senior_dev": "Senior Developer",
    "developer": "Developer",
    "tester": "QA Tester",
    "user": "Standard User",
}


def send_signup_notification(
    to_email: str,
    user_name: str,
    user_role: str,
    site_url: str = "https://bugflow-web.onrender.com"
) -> dict:
    """
    Sends an email notification to the recipient when they sign up on BugFlow Aroma.
    Message: 'You signed up on BugFlow Aroma - Account Confirmation'
    """
    clean_email = to_email.strip().lower()
    clean_name = user_name.strip() or clean_email.split("@")[0]
    role_disp = ROLE_DISPLAY_NAMES.get(user_role.lower(), user_role.title())
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    subject = "🎉 Welcome to BugFlow Aroma - You signed up successfully!"

    # Plain text version
    text_content = f"""Hello {clean_name},

You have successfully signed up on BugFlow Aroma (Defect Intelligence & Sprint Ecosystem).

Your Account Details:
---------------------------------------------
- Full Name: {clean_name}
- Work Email: {clean_email}
- Assigned Role: {role_disp}
- Sign-up Time: {current_time}
- Workspace Portal: {site_url}/login-ui
---------------------------------------------

You can now sign in to your role-specific dashboard using your email and password.

If you did not sign up on BugFlow Aroma, please ignore this email or contact support.

Best regards,
The BugFlow Aroma Team
{site_url}
"""

    # Modern responsive HTML email template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #0f172a; }}
  .email-card {{ max-width: 560px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }}
  .header {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); padding: 32px 28px; text-align: center; color: #ffffff; }}
  .logo {{ display: inline-block; width: 44px; height: 44px; line-height: 44px; border-radius: 12px; background: rgba(255, 255, 255, 0.2); font-size: 22px; font-weight: 800; margin-bottom: 12px; }}
  .brand {{ font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }}
  .badge {{ font-size: 11px; font-weight: 700; background: rgba(255, 255, 255, 0.25); padding: 3px 8px; border-radius: 6px; text-transform: uppercase; margin-left: 6px; }}
  .body {{ padding: 32px 28px; line-height: 1.6; font-size: 14px; color: #334155; }}
  .greeting {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 14px; }}
  .details-box {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 20px; margin: 20px 0; }}
  .detail-row {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13.5px; border-bottom: 1px dashed #cbd5e1; }}
  .detail-row:last-child {{ border-bottom: none; }}
  .detail-label {{ color: #64748b; font-weight: 600; }}
  .detail-value {{ color: #0f172a; font-weight: 700; }}
  .btn-wrap {{ text-align: center; margin: 26px 0 10px; }}
  .btn {{ display: inline-block; background: #2563eb; color: #ffffff !important; padding: 12px 28px; font-size: 14px; font-weight: 700; text-decoration: none; border-radius: 10px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }}
  .footer {{ padding: 20px 28px; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
</style>
</head>
<body>
  <div class="email-card">
    <div class="header">
      <div class="logo">B</div>
      <div class="brand">BugFlow <span class="badge">AROMA</span></div>
      <p style="margin: 8px 0 0; font-size: 14px; opacity: 0.9;">Defect Intelligence &amp; Sprint Ecosystem</p>
    </div>
    <div class="body">
      <div class="greeting">Hello {clean_name},</div>
      <p>You have successfully signed up on <strong>BugFlow Aroma</strong>! Your workspace account is now active and ready for defect tracking, sprint planning, and team collaboration.</p>
      
      <div class="details-box">
        <div class="detail-row">
          <span class="detail-label">Full Name:</span>
          <span class="detail-value">{clean_name}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Work Email:</span>
          <span class="detail-value">{clean_email}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Assigned Role:</span>
          <span class="detail-value">{role_disp}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Sign-up Time:</span>
          <span class="detail-value">{current_time}</span>
        </div>
      </div>

      <div class="btn-wrap">
        <a href="{site_url}/login-ui" class="btn" target="_blank">Access Your Workspace Dashboard &rarr;</a>
      </div>
      
      <p style="margin-top: 24px; font-size: 12.5px; color: #64748b;">
        If you did not sign up for BugFlow Aroma, please ignore this email or notify your system administrator.
      </p>
    </div>
    <div class="footer">
      &copy; 2026 BugFlow Aroma Inc. All rights reserved.<br>
      Enterprise Defect Lifecycle &amp; Sprint Management
    </div>
  </div>
</body>
</html>
"""

    # If SMTP is configured, send the live email
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = clean_email
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                if SMTP_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

            print(f"[BugFlow Email] Notification email sent successfully to {clean_email}")
            return {
                "success": True,
                "delivered": True,
                "recipient": clean_email,
                "message": f"Signup notification email sent successfully to {clean_email}."
            }
        except Exception as e:
            print(f"[BugFlow Email Error] Failed to send email to {clean_email}: {e}")
            return {
                "success": False,
                "delivered": False,
                "recipient": clean_email,
                "error": str(e)
            }
    else:
        # SMTP credentials not configured in environment
        print(f"[BugFlow Email] SMTP credentials not set in environment (SMTP_USER/SMTP_PASS). Simulated notification for {clean_email}.")
        return {
            "success": True,
            "delivered": False,
            "recipient": clean_email,
            "message": f"Signup notification generated for {clean_email} (live SMTP credentials pending in environment variables)."
        }
