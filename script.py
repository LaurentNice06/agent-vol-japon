import os
import sqlite3
from datetime import datetime, timedelta
from amadeus import Client, ResponseError
import smtplib
from email.mime.text import MIMEText

# ----------------------------
# Configuration
# ----------------------------

AMADEUS_CLIENT_ID = os.environ.get("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.environ.get("AMADEUS_CLIENT_SECRET")

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

ORIGIN = "NCE"

DESTINATIONS = ["NRT", "HND", "KIX"]

BUDGET_MIN = 800
BUDGET_MAX = 1300

# périodes de départ possibles
PERIODS = [
    ("2026-10-01", "2026-12-10"),   # automne / début hiver
    ("2027-03-20", "2027-04-10")    # sakura
]

MIN_DAYS = 14
MAX_DAYS = 21

DB_FILE = "flights.db"


# ----------------------------
# Initialisation
# ----------------------------

amadeus = Client(
    client_id=AMADEUS_CLIENT_ID,
    client_secret=AMADEUS_CLIENT_SECRET
)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS flights (
    id TEXT PRIMARY KEY,
    price REAL,
    destination TEXT,
    depart_at TEXT,
    return_at TEXT,
    checked_at TEXT
)
""")
conn.commit()


# ----------------------------
# Email
# ----------------------------

def send_email(subject, body):
    msg = MIMEText(body)
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Subject"] = subject

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)


# ----------------------------
# Scan
# ----------------------------

def daterange(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def scan():
    for destination in DESTINATIONS:
        for start_str, end_str in PERIODS:

            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()

            for depart_date in daterange(start_date, end_date):

                for stay in [MIN_DAYS, MAX_DAYS]:

                    return_date = depart_date + timedelta(days=stay)

                    try:
                        response = amadeus.shopping.flight_offers_search.get(
                            originLocationCode=ORIGIN,
                            destinationLocationCode=destination,
                            departureDate=depart_date.isoformat(),
                            returnDate=return_date.isoformat(),
                            adults=1,
                            max=5
                        )

                        for offer in response.data:

                            price = float(offer["price"]["total"])

                            if not (BUDGET_MIN <= price <= BUDGET_MAX):
                                continue

                            # maximum 1 escale
                            outbound_segments = offer["itineraries"][0]["segments"]
                            inbound_segments = offer["itineraries"][1]["segments"]

                            if len(outbound_segments) > 2 or len(inbound_segments) > 2:
                                continue

                            flight_id = offer["id"]
                            depart_at = outbound_segments[0]["departure"]["at"]
                            return_at = inbound_segments[-1]["arrival"]["at"]

                            cur.execute("SELECT 1 FROM flights WHERE id = ?", (flight_id,))
                            if cur.fetchone():
                                continue

                            cur.execute(
                                "INSERT INTO flights VALUES (?,?,?,?,?,?)",
                                (
                                    flight_id,
                                    price,
                                    destination,
                                    depart_at,
                                    return_at,
                                    datetime.utcnow().isoformat()
                                )
                            )
                            conn.commit()

                            subject = f"✈️ Vol Japon trouvé – {price} €"

                            body = f"""
NICE → {destination}

Départ : {depart_at}
Retour : {return_at}

Durée : {stay} jours
Prix : {price} €

Critères respectés :
- 1 escale maximum
- budget 800–1300 €
- période souhaitée
"""

                            send_email(subject, body)

                    except ResponseError as e:
                        print("Erreur API:", e)


if __name__ == "__main__":
    scan()
