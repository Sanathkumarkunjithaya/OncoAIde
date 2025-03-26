import json
import pymongo
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = pymongo.MongoClient(MONGO_URI)
db = client["onco_db"]
collection = db["patients"]

# Load JSON Data
with open("data/patient.json", "r") as file:
    data = json.load(file)

# Insert JSON into MongoDB
collection.insert_one(data)

print("Patient data successfully inserted into MongoDB!")
