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
        "six", "four", "century", "outfield", "infield", "strikeout",

        # Famous Football Players
        "messi", "ronaldo", "neymar", "mbappe", "haaland", "salah", "debruyne", "lewandowski", "modric", 
        "kane", "vinicius", "bellingham", "pedri", "gavi", "jude", "rodri", "bernardo", "bruno", "casemiro",
        "vini", "kylian", "erling", "mohamed", "kevin", "robert", "luka", "harry", "jude", "pedri", "gavi",
        "zidane", "beckham", "maradona", "pele", "cruyff", "ronaldinho", "kaka", "figo", "henry", "bergkamp",
        "zlatan", "suarez", "aguero", "tevez", "rooney", "gerrard", "lampard", "terry", "rio", "ashley",
        "cole", "scholes", "carrick", "giggs", "solskjaer", "cantona", "best", "charlton", "law", "bobby",
        "moore", "banks", "lines", "charlton", "hurst", "peters", "stiles", "cohen", "wilson", "ball",
        "ramsey", "greaves", "hurst", "charlton", "moore", "banks", "stiles", "cohen", "wilson", "ball",

        # Famous Basketball Players
        "jordan", "lebron", "kobe", "bryant", "curry", "durant", "james", "shaq", "o'neal", "duncan",
        "iverson", "bird", "magic", "johnson", "kareem", "abdul-jabbar", "wilt", "chamberlain", "russell",
        "bill", "hakeem", "olajuwon", "drexler", "barkley", "malone", "stockton", "ewing", "robinson",
        "david", "miller", "reggie", "allen", "ray", "pierce", "paul", "garnett", "kg", "nowitzki",
        "dirk", "nash", "steve", "kidd", "jason", "payton", "gary", "mutombo", "dikembe", "yao", "ming",
        "shaquille", "kobe", "michael", "stephen", "kevin", "anthony", "carmelo", "chris", "paul", "dwyane",
        "wade", "giannis", "antetokounmpo", "jokic", "nikola", "embiid", "joel", "tatum", "jason", "jalen",
        "brown", "jaylen", "mitchell", "donovan", "trae", "young", "luka", "doncic", "zion", "williamson",
        "ja", "morant", "lamelo", "ball", "la", "melo", "anthony", "davis", "anthony", "kawhi", "leonard",
        "kyrie", "irving", "harden", "james", "westbrook", "russell", "love", "kevin", "bosh", "chris",
        "wade", "dwyane", "bosh", "allen", "ray", "kg", "pierce", "rondo", "rajon", "derozan", "demar",
        "lowry", "kyle", "ibaka", "serge", "gasol", "pau", "marc", "noah", "joakim", "rose", "derrick",
        "wall", "john", "beal", "bradley", "lillard", "damian", "aldridge", "lamarcus", "love", "kevin",

        # Famous Cricket Players
        "tendulkar", "sachin", "kohli", "virat", "dhoni", "mahendra", "dhoni", "ms", "smith", "steve",
        "warner", "david", "kane", "williamson", "root", "joe", "cook", "alastair", "anderson", "james",
        "broad", "stuart", "swann", "graeme", "ponting", "ricky", "clarke", "michael", "waugh", "steve",
        "gilchrist", "adam", "hayden", "matthew", "martyn", "damien", "lee", "brett", "mcgrath", "glenn",
        "warne", "shane", "muralitharan", "muthiah", "lara", "brian", "sangakkara", "kumar", "jayawardene",
        "sehwag", "virender", "gambhir", "gautam", "yuvraj", "singh", "raina", "suresh", "dhawan", "shikhar",
        "rohit", "sharma", "rahul", "kl", "pandya", "hardik", "jadeja", "ravindra", "ashwin", "ravichandran",
        "bumrah", "jasprit", "shami", "mohammed", "ishant", "sharma", "umesh", "yadav", "kuldeep", "yadav",
        "chahal", "yuzvendra", "bhumrah", "jaspit", "kohali", "virat", "tendulkar", "sachin", "dravid",
        "rahul", "ganguly", "sourav", "laxman", "vvs", "sehwag", "virender", "yuvraj", "singh", "harbhajan",
        "singh", "zaheer", "khan", "sreesanth", "sreesanth", "pathan", "irfan", "nehra", "ashish", "agarkar",
        "ajit", "kumble", "anil", "srinath", "javagal", "prasad", "venkatesh", "mongia", "nayan", "karthik",
        "dinesh", "dhruv", "rathour", "vikram", "jadeja", "ajay", "kambli", "vinod", "manjrekar", "sanjay",
        "more", "kiran", "srikanth", "kris", "srikkanth", "sidhu", "navjot", "azharuddin", "mohammed",
        "kapil", "dev", "gavaskar", "sunil", "vengsarkar", "sandip", "shastri", "ravi", "binny", "roger",
        "madan", "lal", "amarnath", "mohan", "surinder", "bedi", "bishan", "chandra", "sp", "prasanna",
        "venkat", "srinivasan", "ekanath", "solanke", "subhash", "gupte", "ghulam", "ahmed", "vinoo",
        "mankad", "polly", "umrigar", "vijay", "manjrekar", "hazarare", "salim", "durani", "salim",
        "abid", "ali", "mushtaq", "ali", "hanif", "mohammad", "saeed", "anwar", "inzamam", "ul-haq",
        "wasim", "akram", "waqar", "younis", "shoaib", "akhtar", "saqlain", "mushtaq", "abdul", "qadir",
        "imran", "khan", "javed", "miandad", "zaheer", "abbas", "majid", "khan", "asif", "iqbal", "sarfraz",
        "ahmed", "moin", "khan", "rashid", "latif", "misbah", "ul-haq", "younis", "khan", "shahid",
        "afridi", "umar", "gul", "saeed", "ajmal", "hafeez", "mohammed", "younis", "khan", "shahid",
        "afridi", "umar", "akmal", "kamran", "akmal", "umar", "malik", "shoaib", "tanvir", "sohail",
        "tanvir", "abdul", "razzaq", "azhar", "mahmood", "yasir", "arafat", "yasir", "shah", "mohammad",
        "sammy", "sammy", "gayle", "chris", "sarwan", "ramnaresh", "chanderpaul", "shivnarine", "lara",
        "brian", "hooper", "carl", "walsh", "courtney", "ambrose", "curtly", "marshall", "malcolm",
        "holding", "michael", "garner", "joel", "richards", "viv", "lloyd", "clive", "rowe", "lawrence",
        "khan", "collis", "king", "jimmy", "adams", "jimmy", "gayle", "chris", "bravo", "dwayne",
        "pollard", "kieron", "narine", "sunil", "samuels", "marlon", "taylor", "jerome", "rampaul",
        "ravi", "bennett", "samuel", "fidel", "edwards", "jerome", "powell", "ramnaresh", "sarwan",
        "shivnarine", "chanderpaul", "ramdin", "denesh", "smith", "devon", "sammy", "darren", "fletcher",
        "andre", "russell", "andre", "shai", "hope", "shai", "nicholas", "pooran", "nicholas", "pooran",

        # Famous Tennis Players
        "federer", "roger", "nadal", "rafael", "djokovic", "novak", "murray", "andy", "sampras", "pete",
        "agassi", "andre", "lendl", "ivan", "mcenroe", "john", "borg", "bjorn", "connors", "jimmy",
        "wilander", "mats", "edberg", "stefan", "becker", "boris", "stich", "michael", "chang", "michael",
        " Courier", "jim", "roddick", "andy", "hewitt", "lleyton", "safin", "marat", "kuerten", "gustavo",
        "ferrero", "juan", "carlos", "moya", "carlos", "coria", "guillermo", "gaudio", "gaston", "costa",
        "albert", "johansson", "thomas", "philippoussis", "mark", "rusedski", "greg", "henman", "tim",
        "kafelnikov", "yevgeny", "krajicek", "richard", "rafter", "patrick", "ivanisevic", "goran",
        "stich", "michael", "edberg", "stefan", "becker", "boris", "wilander", "mats", "lendl", "ivan",
        "mcenroe", "john", "borg", "bjorn", "connors", "jimmy", "ashe", "arthur", "newcombe", "john",
        "roche", "tony", "emerson", "roy", "laver", "rod", "rosewall", "ken", "hoad", "lew", "sedgman",
        "frank", "mcgregor", "john", "david", "fraser", "neale", "rose", "allan", "hoad", "lewis",
        "sedgman", "frank", "mcgregor", "john", "david", "fraser", "neale", "rose", "allan", "hoad",
        "lewis", "sedgman", "frank", "mcgregor", "john", "david", "fraser", "neale", "rose", "allan",
        "serena", "williams", "venus", "williams", "graf", "steffi", "navratilova", "martina", "evert",
        "chris", "seles", "monica", "hingis", "martina", "davenport", "lindsay", "capriati", "jennifer",
        "sharapova", "maria", "wozniacki", "caroline", "azarenka", "victoria", "kerber", "angelique",
        "halep", "simona", "pliskova", "karolina", "kvitova", "petra", "kuznetsova", "svetlana", "muguruza",
        "garbine", "ostapenko", "jelena", "sloane", "stephens", "sloane", "osaka", "naomi", "barty",
        "ashleigh", "andreescu", "bianca", "kenin", "sofia", "swiatek", "iga", "raducanu", "emma",
        "gauff", "coco", "sabalenka", "aryna", "rybakina", "elena", "jabeur", "ons", "fritz", "taylor",
        "tsitsipas", "stefanos", "medvedev", "daniil", "zverev", "alexander", "rublev", "andrey",
        "berrettini", "matteo", "sinner", "jannik", "alcaraz", "carlos", "ruud", "casper", "norrie",
        "cameron", "de", "minaur", "alex", "shapovalov", "denis", "auger-aliassime", "felix", "khachanov",
        "karen", "bublik", "alexander", "hurkacz", "hubert", "fucsovics", "marton", "paul", "tommy",

        # Famous Baseball Players
        "ruth", "babe", "aaron", "hank", "mays", "willie", "bonds", "barry", "cobb", "ty", "musial",
        "stan", "williams", "ted", "dimaggio", "joe", "mantle", "mickey", "robinson", "jackie", "clemente",
        "roberto", "ryan", "nolan", "johnson", "randy", "koufax", "sandy", "seaver", "tom", "maddux",
        "greg", "glavine", "tom", "smoltz", "john", "pedro", "martinez", "rivera", "mariano", "jeter",
        "derek", "piazza", "mike", "griffey", "ken", "thomas", "frank", "ortiz", "david", "rodriguez",
        "alex", "ramirez", "manny", "sosa", "sammy", "mcgwire", "mark", "palmeiro", "rafael", "biggio",
        "craig", "thomas", "jeff", "bagwell", "jeff", "pujols", "albert", "trout", "mike", "harper",
        "bryce", "kershaw", "clayton", "verlander", "justin", "schanzer", "max", "cole", "gerrit",
        "deGrom", "jacob", "betts", "mookie", "judge", "aaron", "stanton", "giancarlo", "altuve", "jose",
        "bregman", "alex", "correa", "carlos", "springer", "george", "bauer", "trevor", "snell", "blake",
        "darvish", "yu", "tanaka", "masahiro", "ohtani", "shohei", "machado", "manny", "harper", "bryce",

        # Famous Hockey Players
        "gretzky", "wayne", "lemieux", "mario", "howe", "gordie", "orr", "bobby", "hull", "brett",
        "jagr", "jaromir", "messier", "mark", "forsberg", "peter", "lindros", "eric", "sakic", "joe",
        "yzerman", "steve", "bourque", "ray", "robitaille", "luc", "francis", "ron", "hull", "brett",
        "oates", "adam", "jagr", "jaromir", "lemieux", "mario", "jagr", "jaromir", "gretzky", "wayne",
        "howe", "gordie", "orr", "bobby", "hull", "brett", "messier", "mark", "forsberg", "peter",
        "lindros", "eric", "sakic", "joe", "yzerman", "steve", "bourque", "ray", "robitaille", "luc",
        "francis", "ron", "crosby", "sidney", "ovechkin", "alex", "malkin", "evgeni", "stamkos", "steven",
        "tavares", "john", "mcDavid", "connor", "matthews", "auston", "mackinnon", "nathan", "macKinnon",
        "kane", "patrick", "toews", "jonathan", "keith", "duncan", "seabrook", "brent", "hossa", "marian",
        "sharp", "patrick", "campbell", "colin", "keith", "duncan", "seabrook", "brent", "hossa", "marian",

        # Famous Golf Players
        "woods", "tiger", "nicklaus", "jack", "palmer", "arnold", "player", "gary", "hogan", "ben",
        "snead", "sam", "watson", "tom", "mickelson", "phil", "norman", "greg", "els", "ernie",
        "singh", "vijay", "faldo", "nick", "scott", "adam", "mcilroy", "rory", "spieth", "jordan",
        "thomas", "justin", "johnson", "dustin", "rahm", "jon", "koepka", "brooks", "dechambeau",
        "bryson", "scheffler", "scottie", "cantlay", "patrick", "morikawa", "collin", "zalatoris",
        "will", "hatton", "tyrell", "fleetwood", "tommy", "rahm", "jon", "thomas", "justin", "johnson",
        "dustin", "koepka", "brooks", "dechambeau", "bryson", "mcilroy", "rory", "spieth", "jordan",
        "thomas", "justin", "cantlay", "patrick", "scheffler", "scottie", "morikawa", "collin", "zalatoris",
        "will", "hatton", "tyrell", "fleetwood", "tommy", "rahm", "jon", "thomas", "justin", "johnson",
        "dustin", "koepka", "brooks", "dechambeau", "bryson", "mcilroy", "rory", "spieth", "jordan",

        # Famous Boxers
        "ali", "muhammad", "tyson", "mike", "foreman", "george", "frazier", "joe", "leonard", "sugar",
        "ray", "durán", "roberto", "hagler", "marvelous", "hearns", "thomas", "hear", "sugar", "ray",
        "robinson", "sugar", "ray", "armstrong", "henry", "dempsey", "jack", "marciano", "rocky",
        "louis", "joe", "pacquiao", "manny", "mayweather", "floyd", "cotto", "miguel", "marquez",
        "juan", "manuel", "barrera", "marco", "pacquiao", "manny", "mayweather", "floyd", "cotto",
        "miguel", "marquez", "juan", "manuel", "barrera", "marco", "pacquiao", "manny", "mayweather",
        "floyd", "cotto", "miguel", "marquez", "juan", "manuel", "barrera", "marco", "pacquiao", "manny",
        "mayweather", "floyd", "cotto", "miguel", "marquez", "juan", "manuel", "barrera", "marco",

        # Famous MMA Fighters
        "silva", "anderson", "jones", "jon", "st-pierre", "georges", "lesnar", "brock", "cormier",
        "daniel", "miocic", "stipe", "nogueira", "minotauro", "fedor", "emelianenko", "couture",
        "randy", "liddell", "chuck", "ortiz", "tito", "griffin", "forrest", "rampage", "quinton",
        "jackson", "shogun", "rua", "machida", "lyoto", "evans", "rashad", "henderson", "dan",
        "bisping", "michael", "rockhold", "luke", "weidman", "chris", "silva", "vitor", "belfort",
        "vitor", "wanderlei", "silva", "rampage", "jackson", "shogun", "rua", "machida", "lyoto",
        "evans", "rashad", "henderson", "dan", "bisping", "michael", "rockhold", "luke", "weidman",
        "chris", "silva", "vitor", "belfort", "vitor", "wanderlei", "silva", "rampage", "jackson",
        "shogun", "rua", "machida", "lyoto", "evans", "rashad", "henderson", "dan", "bisping",
        "michael", "rockhold", "luke", "weidman", "chris", "silva", "vitor", "belfort", "vitor",

        # Famous F1 Drivers
        "hamilton", "lewis", "schumacher", "michael", "verstappen", "max", "vettel", "sebastian",
        "alonso", "fernando", "raikkonen", "kimi", "button", "jenson", "webber", "mark", "ricciardo",
        "daniel", "bottas", "valtteri", "norris", "lando", "sainz", "carlos", "leclerc", "charles",
        "gasly", "pierre", "ocon", "esteban", "grosjean", "romain", "kvyat", "daniil", "magnussen",
        "kevin", "hulkenberg", "nico", "perez", "sergio", "stroll", "lance", "tsunoda", "yuki",
        "zhou", "guanyu", "albon", "alexander", "latifi", "nicholas", "mazepin", "nikita", "schumacher",
        "mick", "russell", "george", "hamilton", "lewis", "verstappen", "max", "vettel", "sebastian",
        "alonso", "fernando", "raikkonen", "kimi", "button", "jenson", "webber", "mark", "ricciardo",
        "daniel", "bottas", "valtteri", "norris", "lando", "sainz", "carlos", "leclerc", "charles",

        # Famous Athletes (Various Sports)
        "bolt", "usain", "phelps", "michael", "biles", "simone", "radcliffe", "paula", "farah",
        "mo", "rudisha", "david", "bekele", "kenenisa", "gebrselassie", "haile", "kipchoge", "eluid",
        "el", "guerrouj", "hicham", "warholm", "karsten", "duplantis", "mondo", "richardson", "sha'carri",
        "thompson", "katarina", "johnson", "katarina", "wlodarczyk", "anita", "adams", "valerie",
        "barshim", "mutaz", "doha", "makhinin", "ivan", "lasitskene", "mariya", "stefanidi", "ekaterini",
        "rogers", "felix", "allyson", "fraser-pryce", "shelly-ann", "thompson", "elaine", "jackson",
        "shericka", "ahmed", "faith", "chepng'etich", "kipyegon", "faith", "gidey", "letesenbet", "obiri",
        "hellen", "muir", "laura", "houlihan", "sifan", "hasan", "sifan", "dibaba", "genzebe",
        "ayana", "almaz", "cheruiyot", "vivian", "jepchirchir", "peres", "kosgei", "brigid", "kipruto",
        "conseslus", "keter", "timothy", "cheruiyot", "timothy", "manangoi", "amos", "emanuel", "kinyamal",
        "michael", "cheruiyot", "timothy", "manangoi", "amos", "emanuel", "kinyamal", "michael", "wanyonyi",
        "emmanuel", "korir", "ferguson", "reuben", "kipsang", "wilson", "kipchoge", "eluid", "bekele",
        "kenenisa", "gebrselassie", "haile", "farah", "mo", "radcliffe", "paula", "kipsang", "wilson",
        "kimetto", "dennis", "kipsiro", "moses", "cherono", "lawrence", "tanui", "abraham", "rotich",
        "wilson", "kipsang", "wilson", "kimetto", "dennis", "kipsiro", "moses", "cherono", "lawrence",
        "tanui", "abraham", "rotich", "wilson", "kipsang", "wilson", "kimetto", "dennis", "kipsiro",
        "moses", "cherono", "lawrence", "tanui", "abraham", "rotich", "wilson", "kipsang", "wilson",

        # Sports Teams
        "barcelona", "real", "madrid", "manchester", "united", "city", "liverpool", "chelsea", "arsenal",
        "tottenham", "juventus", "inter", "milan", "ac", "milan", "bayern", "munich", "dortmund", "psg",
        "paris", "saint-germain", "ajax", "benfica", "porto", "sporting", "galatasaray", "fenerbahce",
        "besiktas", "olympiakos", "panathinaikos", "paok", "celtic", "rangers", "shakhtar", "dynamo",
        "kyiv", "red", "star", "partizan", "steaua", "crvena", "zvezda", "salzburg", "basel", "zurich",
        "young", "boys", "brugge", "club", "brugge", "leverkusen", "wolfsburg", "frankfurt", "eintracht",
        "leipzig", "rb", "monchengladbach", "borussia", "hamburg", "werder", "bremen", "stuttgart", "hertha",
        "berlin", "hannover", "koln", "fc", "mainz", "freiburg", "hoffenheim", "augsburg", "paderborn",
        "union", "berlin", "schalke", "dortmund", "borussia", "bayer", "leverkusen", "bayern", "munich",
        "rb", "leipzig", "wolfsburg", "frankfurt", "eintracht", "monchengladbach", "borussia", "hamburg",
        "werder", "bremen", "stuttgart", "hertha", "berlin", "hannover", "koln", "fc", "mainz", "freiburg",
        "hoffenheim", "augsburg", "paderborn", "union", "berlin", "schalke", "dortmund", "borussia",
        "lakers", "celtics", "warriors", "bulls", "heat", "spurs", "mavericks", "rockets", "clippers",
        "knicks", "nets", "76ers", "raptors", "bucks", "pistons", "pacers", "cavaliers", "timberwolves",
        "grizzlies", "pelicans", "thunder", "blazers", "kings", "suns", "hawks", "hornets", "magic",
        "wizards", "yankees", "red", "sox", "dodgers", "giants", "cubs", "cardinals", "braves", "astros",
        "mets", "phillies", "angels", "mariners", "rangers", "orioles", "blue", "jays", "rays", "athletics",
        "tigers", "white", "sox", "royals", "twins", "indians", "guardians", "pirates", "reds", "diamondbacks",
        "rockies", "brewers", "nationals", "padres", "marlins", "penguins", "blackhawks", "rangers", "bruins",
        "canadiens", "maple", "leafs", "capitals", "lightning", "golden", "knights", "avalanche", "stars",
        "oilers", "flames", "canucks", "jets", "senators", "sabres", "panthers", "hurricanes", "wild",
        "predators", "devils", "flyers", "islanders", "ducks", "kings", "sharks", "coyotes",

        # Sports Equipment and Gear
        "ball", "balls", "bat", "bats", "racket", "rackets", "club", "clubs", "stick", "sticks", "puck",
        "gloves", "helmet", "helmets", "pad", "pads", "shin", "guards", "cleats", "spikes", "jersey",
        "kit", "uniform", "shorts", "socks", "shoes", "boots", "sneakers", "net", "nets", "hoop", "hoops",
        "rim", "rims", "backboard", "goalpost", "crossbar", "post", "posts", "flag", "flags", "whistle",
        "referee", "umpire", "linesman", "judge", "scorer", "timer", "clock", "scoreboard", "video",
        "replay", "challenge", "review", "var", "technology", "system", "camera", "cameras", "drone",
        "drones", "tracker", "tracking", "gps", "sensor", "sensors", "wearable", "fitness", "watch",
        "band", "strap", "heart", "rate", "monitor", "smartwatch", "tracker", "activity", "step",
        "counter", "calorie", "burn", "sleep", "tracker", "hydration", "monitor", "nutrition", "diet",
        "supplement", "protein", "carb", "carbohydrate", "fat", "vitamin", "mineral", "water", "bottle",
        "bottles", "hydration", "pack", "belt", "fanny", "pack", "backpack", "bag", "bags", "duffel",
        "locker", "room", "shower", "towel", "soap", "shampoo", "conditioner", "deodorant", "antiperspirant",
        "tape", "athletic", "wrap", "brace", "support", "compression", "socks", "sleeves", "shirt",
        "base", "layer", "mid", "layer", "outer", "layer", "jacket", "windbreaker", "rain", "gear",
        "cold", "weather", "hot", "weather", "sun", "protection", "sunglasses", "hat", "cap", "visor",

        # Sports Venues and Locations
        "stadium", "stadiums", "arena", "arenas", "field", "fields", "court", "courts", "pitch", "pitches",
        "track", "tracks", "pool", "pools", "gym", "gymnasium", "fitness", "center", "centre", "club",
        "complex", "facility", "facilities", "venue", "venues", "location", "locations", "city", "cities",
        "country", "countries", "nation", "nations", "region", "regions", "state", "states", "province",
        "provinces", "territory", "territories", "continent", "continents", "world", "global", "international",
        "domestic", "local", "regional", "national", "amateur", "professional", "semi", "pro", "elite",
        "youth", "junior", "senior", "veteran", "rookie", "debut", "retirement", "legend", "hall", "fame",
        "museum", "exhibition", "showcase", "demonstration", "clinic", "camp", "training", "academy",
        "school", "university", "college", "high", "school", "elementary", "primary", "secondary",
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
            
            # Enhance query with sports context for better results
            enhanced_query = query
            if "messi" in query.lower() or "ronaldo" in query.lower() or "neymar" in query.lower():
                enhanced_query = f"{query} football soccer player"
            elif "jordan" in query.lower() or "lebron" in query.lower() or "kobe" in query.lower():
                enhanced_query = f"{query} basketball nba player"
            elif "tendulkar" in query.lower() or "kohli" in query.lower():
                enhanced_query = f"{query} cricket player"
            elif "federer" in query.lower() or "nadal" in query.lower() or "djokovic" in query.lower():
                enhanced_query = f"{query} tennis player"
            
            web_results = search_web(enhanced_query)
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
