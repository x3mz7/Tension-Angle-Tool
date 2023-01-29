import os  # Core python module
from deta import Deta  # pip install deta
from dotenv import load_dotenv  # pip install python-dotenv

# Load the environment variables
load_dotenv("TA.env")
DETA_KEY = os.getenv("DETA_KEY")

# Initialise with a project key
deta = Deta(DETA_KEY)

# This is how to create/connect a database
db = deta.Base("tension_angle_data")

def insert_session(sessionData, projName, projVersion, projClient, date_saved, time_saved, projComment, t_a_Pack):
    """Returns the report on a successful creation, otherwise raises an error"""
    return db.put({"key": sessionData, "projName": projName, "projVersion": projVersion, "projClient": projClient, "date_saved": date_saved, "time_saved": time_saved, "projComment": projComment, "t_a_Pack": t_a_Pack})

def fetch_all_sessions():
    """Returns a dict of all sessionData"""
    res = db.fetch()
    return res.items

def get_session(sessionData):
    """If not found, the function will return None"""
    return db.get(sessionData)
