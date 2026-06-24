from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import bcrypt
import secrets
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from config import APP_PORT, GOOGLE_CLIENT_ID, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
from local_store import LocalStore
from gemini_client import GeminiError, generate_agent_answer, search_web, status as gemini_status, generate_local_sports_answer


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
LOCAL = LocalStore()

# Session management
SESSIONS = {}
SESSION_TIMEOUT = 30 * 60  # 30 minutes

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_hex(32)

def create_session(user_data: dict) -> str:
    """Create a new session for a user."""
    token = generate_token()
    SESSIONS[token] = {
        "user": user_data,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    }
    return token

def validate_session(token: str) -> dict:
    """Validate a session token and return user data if valid."""
    if token not in SESSIONS:
        return None
    
    session = SESSIONS[token]
    if datetime.now() > session["expires_at"]:
        del SESSIONS[token]
        return None
    
    # Extend session timeout
    session["expires_at"] = datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    return session["user"]

def invalidate_session(token: str):
    """Invalidate a session token."""
    if token in SESSIONS:
        del SESSIONS[token]

def send_reset_email(email: str, reset_link: str) -> bool:
    """Send password reset email."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP credentials not configured, skipping email send")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = 'Password Reset - Sportly'
        
        body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>You requested a password reset for your Sportly account.</p>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_link}">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def is_sports_query_local(query: str) -> bool:
    # A simple word list check for offline/fallback mode.
    q = query.lower().strip("?!. ")
    # Simple greetings are allowed
    if q in ("hello", "hi", "hey", "sup", "greetings", "good morning", "good afternoon", "good evening"):
        return True
        
    sports_keywords = {
        # General & Actions
        "sport", "sports", "game", "games", "match", "matches", "player", "players", "team", "teams",
        "win", "wins", "won", "lose", "loses", "lost", "score", "scores", "play", "playing", "cup", "cups",
        "tournament", "tournaments", "league", "leagues", "championship", "championships", "stadium", "stadiums",
        "arena", "coach", "coaches", "referee", "ref", "refs", "umpire", "umpires", "athlete", "athletes", 
        "predict", "prediction", "predictions", "vs", "versus", "training", "workout", "fitness", "draft",

        # Wrestling & WWE specifically
        "wwe", "raw", "smackdown", "wrestlemania", "wrestler", "wrestlers", "wrestling", "ring", "mat", 
        "knockout", "ko", "tko", "submission", "belt", "champion", "sumo", "lucha", "royal rumble",

        # Common Sports Names
        "football", "soccer", "basketball", "cricket", "tennis", "baseball", "hockey", "rugby", "golf", 
        "badminton", "volleyball", "swimming", "boxing", "mma", "ufc", "f1", "racing", "formula1", "motogp",
        "athletics", "gymnastics", "cycling", "chess", "billiards", "snooker", "pool", "darts", "bowling", 
        "squash", "lacrosse", "handball", "waterpolo", "polo", "kabaddi", "archery", "shooting", "fencing", 
        "rowing", "sailing", "canoeing", "kayaking", "surfing", "skateboarding", "snowboarding", "skiing", 
        "icehockey", "curling", "biathlon", "triathlon", "decathlon", "marathon", "sprint", "hurdles", 
        "highjump", "longjump", "polevault", "shotput", "discus", "javelin", "weightlifting", "powerlifting", 
        "bodybuilding", "karate", "judo", "taekwondo", "kungfu", "kickboxing", "muaythai", "jiujitsu", "bjj",
        "softball", "netball", "dodgeball", "kickball", "pickleball", "croquet", "rounders", "hurling", "gaelic",

        # Major Leagues, Events & Cups
        "fifa", "nba", "nfl", "mlb", "nhl", "ipl", "epl", "laliga", "seriea", "bundesliga", "ligue1", "uefa", 
        "championsleague", "europaleague", "worldcup", "olympics", "paralympics", "wimbledon", "usopen", 
        "frenchopen", "ausopen", "australianopen", "t20", "odi", "testmatch", "ashes", "superbowl", 
        "tourdefrance", "indy500", "nascar", "onechampionship", "bellator",

        # Terminology & Positions
        "wicket", "wickets", "run", "runs", "goal", "goals", "touchdown", "touchdowns", "homerun", "homeruns", 
        "slam", "slams", "point", "points", "court", "pitch", "field", "jersey", "striker", "strikers", 
        "goalkeeper", "keeper", "batsman", "batsmen", "bowler", "bowlers", "midfielder", "defender", 
        "quarterback", "batter", "pitcher", "tackle", "dribble", "pass", "shoot", "dunk", "serve", 
        "volley", "offside", "penalty", "freekick", "corner", "innings", "over", "overs", "boundary", 
        "six", "four", "century", "outfield", "infield", "strikeout"
    }
    
    import re
    words = set(re.findall(r"\b\w+\b", q))
    return bool(words & sports_keywords)


class SportlyBotHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_POST(self):
        try:
            if self.path == "/api/ask":
                self.handle_ask()
                return
            if self.path == "/api/auth/login":
                self.handle_login()
                return
            if self.path == "/api/auth/register":
                self.handle_register()
                return
            if self.path == "/api/auth/logout":
                self.handle_logout()
                return
            if self.path == "/api/auth/validate":
                self.handle_validate()
                return
            if self.path == "/api/auth/forgot-password":
                self.handle_forgot_password()
                return
            if self.path == "/api/auth/google-login":
                self.handle_google_login()
                return

            self.send_error(404, "Not found")
        except json.JSONDecodeError:
            self.respond_json({"error": "Invalid JSON body."}, status=400)
        except Exception as exc:
            self.respond_json({"error": str(exc)}, status=500)

    def do_GET(self):
        try:
            if self.path == "/api/health":
                self.respond_json(
                    {
                        "ok": True,
                        "database": {"enabled": False},
                        "gemini": gemini_status(),
                        "local_store": {"enabled": True},
                        "google_client_id": GOOGLE_CLIENT_ID,
                    }
                )
                return

            super().do_GET()
        except Exception as exc:
            self.respond_json({"error": str(exc)}, status=500)

    def handle_ask(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        query = payload.get("query", "")
        conversation_history = payload.get("conversation_history", [])

        if not query.strip():
            self.respond_json({"error": "Query is required."}, status=400)
            return

        # Use sports intent for sports prediction assistant
        intent = "sports"
        
        # Local validation check if Gemini is offline
        from gemini_client import gemini_enabled
        if not gemini_enabled():
            # Always do web search when Gemini is disabled
            print(f"Performing web search for query: {query}")
            web_results = search_web(query)
            print(f"Web results: {web_results}")
            local_ans = generate_local_sports_answer(query, web_results)
            result = {
                "answer": local_ans,
                "generated_by": "local_search",
                "intent": intent,
                "agent": "Sportly",
                "web_results": web_results,
            }
            LOCAL.insert_chat(
                {
                    "user_query": query,
                    "intent": intent,
                    "agent": "Sportly",
                    "answer": result["answer"],
                }
            )
            self.respond_json(result)
            return

        # Always perform web search for real-time sports data
        web_results = search_web(query)

        # Generate AI response with web search context
        ai_answer = None
        try:
            ai_answer = generate_agent_answer(
                query=query,
                intent=intent,
                agent="Sportly",
                retrieved_context=None,
                conversation_history=conversation_history,
                web_results=web_results,
            )
        except (GeminiError, json.JSONDecodeError) as exc:
            # Fall back to local search if Gemini API fails
            print(f"Gemini API error, falling back to local search: {exc}")
            local_ans = generate_local_sports_answer(query, web_results)
            result = {
                "answer": local_ans,
                "generated_by": "local_search_fallback",
                "intent": intent,
                "agent": "Sportly",
                "web_results": web_results,
            }
            LOCAL.insert_chat(
                {
                    "user_query": query,
                    "intent": intent,
                    "agent": "Sportly",
                    "answer": result["answer"],
                }
            )
            self.respond_json(result)
            return

        if ai_answer:
            if not ai_answer.get("is_sports_related", True):
                result = {
                    "answer": {
                        "direct_answer": ai_answer.get("direct_answer", "I am Sportly, a specialized sports prediction and analysis assistant. I can only assist you with sports-related queries."),
                        "explanation": "",
                        "action_steps": [],
                        "sources": [],
                    },
                    "generated_by": "gemini",
                    "intent": "sports",
                    "agent": "Sportly",
                    "web_results": [],
                }
            else:
                result = {
                    "answer": ai_answer,
                    "generated_by": "gemini",
                    "intent": intent,
                    "agent": "Sportly",
                    "web_results": web_results,
                }
        else:
            result = {
                "answer": {
                    "direct_answer": "I am Sportly, your sports assistant. The AI service is currently offline. Please check back later.",
                    "explanation": "",
                    "action_steps": [],
                    "sources": [],
                },
                "generated_by": "local",
                "intent": intent,
                "agent": "Sportly",
                "web_results": [],
            }

        # Save to local storage
        LOCAL.insert_chat(
            {
                "user_query": query,
                "intent": intent,
                "agent": "Sportly",
                "answer": result["answer"],
            }
        )
        self.respond_json(result)

    def handle_login(self):
        """Handle user login."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
        remember_me = payload.get("remember_me", False)
        
        if not username or not password:
            self.respond_json({"error": "Username and password are required."}, status=400)
            return
        
        # Get users from local storage
        users_data = LOCAL.list_rows("users", limit=1000)
        users = {user["username"]: user for user in users_data}
        
        if username not in users:
            self.respond_json({"error": "Invalid username or password."}, status=401)
            return
        
        user = users[username]
        if not verify_password(password, user["password_hash"]):
            self.respond_json({"error": "Invalid username or password."}, status=401)
            return
        
        # Create session with extended timeout if remember me is checked
        user_data = {
            "username": user["username"],
            "email": user.get("email", ""),
            "created_at": user["created_at"]
        }
        
        # Adjust session timeout based on remember_me
        if remember_me:
            session_timeout = 7 * 24 * 60 * 60  # 7 days
        else:
            session_timeout = SESSION_TIMEOUT
        
        token = generate_token()
        SESSIONS[token] = {
            "user": user_data,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=session_timeout),
            "remember_me": remember_me
        }
        
        self.respond_json({
            "token": token,
            "user": user_data,
            "expires_in": session_timeout
        })

    def handle_register(self):
        """Handle user registration."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        
        username = payload.get("username", "").strip()
        email = payload.get("email", "").strip()
        password = payload.get("password", "")
        
        if not username or not email or not password:
            self.respond_json({"error": "Username, email, and password are required."}, status=400)
            return
        
        if len(password) < 6:
            self.respond_json({"error": "Password must be at least 6 characters."}, status=400)
            return
        
        # Check if user already exists
        users_data = LOCAL.list_rows("users", limit=1000)
        users = {user["username"]: user for user in users_data}
        
        if username in users:
            self.respond_json({"error": "Username already exists."}, status=409)
            return
        
        # Create new user
        user = LOCAL.insert_row("users", {
            "username": username,
            "email": email,
            "password_hash": hash_password(password)
        })
        
        self.respond_json({
            "message": "User created successfully",
            "user": {
                "username": user["username"],
                "email": user["email"],
                "created_at": user["created_at"]
            }
        })

    def handle_logout(self):
        """Handle user logout."""
        token = self.headers.get("Authorization", "").replace("Bearer ", "")
        
        if token:
            invalidate_session(token)
        
        self.respond_json({"message": "Logged out successfully"})

    def handle_validate(self):
        """Validate session token."""
        token = self.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            self.respond_json({"valid": False}, status=401)
            return
        
        user_data = validate_session(token)
        
        if user_data:
            self.respond_json({
                "valid": True,
                "user": user_data,
                "expires_in": SESSION_TIMEOUT
            })
        else:
            self.respond_json({"valid": False}, status=401)

    def handle_forgot_password(self):
        """Handle forgot password request."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        
        email = payload.get("email", "").strip()
        
        if not email:
            self.respond_json({"error": "Email is required."}, status=400)
            return
        
        # Check if user exists with this email
        users_data = LOCAL.list_rows("users", limit=1000)
        users = {user["email"]: user for user in users_data}
        
        if email not in users:
            # Don't reveal if email exists or not for security
            self.respond_json({"message": "If an account exists with this email, a reset link will be sent."})
            return
        
        # Generate a reset token (valid for 1 hour)
        reset_token = generate_token()
        user = users[email]
        
        # Store reset token in user data
        user["reset_token"] = reset_token
        user["reset_token_expires"] = (datetime.now() + timedelta(hours=1)).isoformat()
        
        # For demo purposes, return the reset link directly
        reset_link = f"http://localhost:8000/reset-password.html?token={reset_token}"
        
        # Try to send email if configured
        email_sent = send_reset_email(email, reset_link)
        
        if email_sent:
            self.respond_json({
                "message": "Password reset link sent to your email",
                "email_sent": True
            })
        else:
            # Fallback to showing link if email not configured
            self.respond_json({
                "message": "Password reset link generated (email not configured)",
                "reset_link": reset_link,
                "reset_token": reset_token,
                "email_sent": False
            })

    def handle_google_login(self):
        """Handle Google Sign-In login."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        
        token = payload.get("token", "")
        email = payload.get("email", "")
        name = payload.get("name", "")
        picture = payload.get("picture", "")
        
        if not token or not email:
            self.respond_json({"error": "Google token and email are required."}, status=400)
            return
        
        # Check if user exists with this email
        users_data = LOCAL.list_rows("users", limit=1000)
        users = {user["email"]: user for user in users_data}
        
        if email in users:
            # User exists, create session
            user = users[email]
            user_data = {
                "username": user["username"],
                "email": user["email"],
                "name": name,
                "picture": picture,
                "created_at": user["created_at"]
            }
        else:
            # Create new user from Google account
            username = email.split("@")[0]
            # Ensure username is unique
            base_username = username
            counter = 1
            while username in [u["username"] for u in users_data]:
                username = f"{base_username}{counter}"
                counter += 1
            
            user = LOCAL.insert_row("users", {
                "username": username,
                "email": email,
                "password_hash": "",  # No password for Google users
                "google_id": token[:20]  # Store partial Google ID
            })
            
            user_data = {
                "username": user["username"],
                "email": user["email"],
                "name": name,
                "picture": picture,
                "created_at": user["created_at"]
            }
        
        # Create session with extended timeout (7 days for Google login)
        session_timeout = 7 * 24 * 60 * 60
        token = generate_token()
        SESSIONS[token] = {
            "user": user_data,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=session_timeout),
            "remember_me": True
        }
        
        self.respond_json({
            "token": token,
            "user": user_data,
            "expires_in": session_timeout
        })

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def respond_json(self, data, status=200):
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else APP_PORT
    server = ThreadingHTTPServer(("localhost", port), SportlyBotHandler)
    print(f"Sportly running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
