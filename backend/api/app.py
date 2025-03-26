from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import groq
import re
from markdown2 import markdown
import json

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 

# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client["onco_db"]
collection = db["patients"]

# Initialize FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq API Client
groq_client = groq.Groq(api_key=GROQ_API_KEY)

class Query(BaseModel):
    query: str

@app.get("/")
def home():
    return {"message": "OncoAide API is running!"}

@app.get("/patients")
def get_patients():
    data = list(collection.find({}, {"_id": 0}))
    if not data:
        raise HTTPException(status_code=404, detail="No patients found")
    return {"patients": data}

@app.get("/patients/{patient_id}")
def get_patient_by_id(patient_id: str):
    patient = collection.find_one({"patient_id": patient_id}, {"_id": 0})
    if patient:
        return patient
    raise HTTPException(status_code=404, detail="Patient not found")

def query_groq_llm(prompt: str):
    try:
        completion = groq_client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_completion_tokens=2048,
            top_p=0.95,
            stream=False,
        )
        response = completion.choices[0].message.content.strip()
        response = re.sub(r"<think>.*?</think>\n*", "", response, flags=re.DOTALL).strip()
        response_html = markdown(response, extras=["breaks", "nofollow", "tables", "fenced-code-blocks"])
        response_html = re.sub(r"(<br>\s*){2,}", "<br>", response_html)
        response_html = re.sub(r"(<p>\s*){2,}", "<p>", response_html)
        response_html = re.sub(r"\s*\n\s*", "\n", response_html)
        response_html = re.sub(r"<ul>", "<ul style='margin-left: 20px; padding-left: 20px;'>", response_html)
        response_html = re.sub(r"</li>\s*<li>", "</li>\n<li>", response_html)
        response_html = f"<div class='response-box' style='word-wrap: break-word; overflow-wrap: break-word; padding: 10px;'>{response_html}</div>"
        return response_html
    except Exception as e:
        print(f"Groq API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Groq API Error: {str(e)}")

@app.post("/query")
def chatbot_query(user_query: Query):
    query = user_query.query.lower()
    print(f"Received query: {query}")

    # List all patients
    if any(phrase in query for phrase in ["list of all patient", "name all the patient", "give all the patient", "all patients"]):
        patients = list(collection.find({}, {"_id": 0}))
        if not patients:
            return {"response": "No patients found in the database."}
        patient_list = "\n".join([f"- {p.get('patient', {}).get('name', p.get('name', 'Unknown'))} ({p.get('diagnosis', {}).get('condition', 'No diagnosis')})" for p in patients])
        print(f"Returning patient list: {patient_list}")
        return {"response": f"Patients in the database:\n{patient_list}"}

    # Fetch patient by ID
    if "get details of patient with id" in query:
        patient_id = query.split("id")[-1].strip()
        patient = collection.find_one({"patient_id": patient_id}, {"_id": 0})
        print(f"Patient by ID {patient_id}: {patient}")
        return {"response": patient if patient else "Patient not found"}

    # Check for specific conditions
    if "who has" in query and "cancer" in query:
        condition = re.search(r"who has (\w+ cancer)", query)
        if condition:
            condition = condition.group(1)
            patient = collection.find_one({"diagnosis.condition": {"$regex": condition, "$options": "i"}}, {"_id": 0})
            if patient:
                name = patient.get("patient", {}).get("name", patient.get("name", "Unknown"))
                return {"response": f"The patient with {condition} is {name}."}
            return {"response": f"No patient with {condition} found in the database."}

    # Name matching with possessive handling
    patient_data = None
    patient_name = None
    for name_part in query.split():
        # Remove possessive 's or s'
        cleaned_part = re.sub(r"'s$", "", name_part)
        patient = collection.find_one({
            "$or": [
                {"patient.name": {"$regex": cleaned_part, "$options": "i"}},
                {"name": {"$regex": cleaned_part, "$options": "i"}}
            ]
        }, {"_id": 0})
        if patient:
            patient_data = patient
            patient_name = patient.get("patient", {}).get("name", patient.get("name", "Unknown"))
            print(f"Matched patient: {patient_name}")
            break

    # Construct prompt
    if patient_data:
        # Patient-specific query: Send full patient data
        patient_json = json.dumps(patient_data)
        prompt = f"""
        I am OncoAide, an oncology assistant. Below is the complete record for {patient_name}:
        {patient_json}

        Answer the user’s question: {user_query.query}
        Provide a clear, structured, and medically relevant response based only on this data.
        Do not invent patients or add information not present in the record.
        """
        print(f"Sending data to LLM for patient: {patient_name} (size: {len(prompt)} characters)")
    else:
        # General query: No patient data
        prompt = f"""
        I am OncoAide, an oncology assistant. No patient data is provided for this query.
        Answer the user’s question: {user_query.query}
        Provide a clear, relevant response as OncoAide. If the query requires patient data, inform the user to specify a patient name (e.g., 'Tell me about Alice Johnson').
        """
        print(f"Sending general query to LLM: {query}")

    response = query_groq_llm(prompt)
    return {"response": response}

@app.post("/upload-patient")
async def upload_patient(file: UploadFile = File(...)):
    contents = await file.read()
    filename = file.filename.lower()

    try:
        if filename.endswith(".json"):
            patient_data = json.loads(contents.decode("utf-8"))
            if isinstance(patient_data, list):
                collection.insert_many(patient_data)
                print(f"Inserted {len(patient_data)} new patients: {patient_data}")
                return {"message": f"Uploaded {len(patient_data)} patients successfully!"}
            else:
                collection.insert_one(patient_data)
                print(f"Inserted single new patient: {patient_data}")
                return {"message": f"Patient {patient_data.get('patient', {}).get('name', patient_data.get('name', 'record'))} uploaded successfully!"}
        elif filename.endswith(".txt"):
            text = contents.decode("utf-8")
            patient_data = {}
            for line in text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    patient_data[key.strip()] = value.strip()
            collection.insert_one(patient_data)
            print(f"Inserted single new patient from text: {patient_data}")
            return {"message": f"Patient {patient_data.get('name', 'record')} uploaded successfully!"}
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use JSON or TXT.")
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")