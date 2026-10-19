import os
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 1. Initialize FastAPI Application
app = FastAPI(title="MHT-CET Predictor API")

# 2. Allow requests from any website frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "cet_predictor.db")

def get_db_connection():
    if not os.path.exists(DB_FILE):
        raise HTTPException(status_code=500, detail="Database file missing. Run seed.py first.")
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# 3. Define standard API response format
class CollegeResult(BaseModel):
    institute_code: str
    institute_name: str
    choice_code: str
    branch_name: str
    category: str
    cutoff_percentile: float
    closing_rank: Optional[int] = None
    percentile_diff: float
    admission_chance: str

# 4. Root API Endpoint (Health Check)
@app.get("/")
def home():
    return {"status": "online", "message": "MHT-CET API is working!"}

# 5. College Predictor Endpoint
@app.get("/api/predict", response_model=List[CollegeResult])
def predict_colleges(
    percentile: float = Query(..., ge=0.0, le=100.0, description="User CET Percentile"),
    category: str = Query("GOPENS", description="Category Code"),
    branch: Optional[str] = Query(None, description="Branch search filter"),
    margin: float = Query(3.0, description="Cutoff margin allowance")
):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT 
            c.institute_code,
            c.institute_name,
            k.choice_code,
            k.branch_name,
            k.category,
            k.percentile AS cutoff_percentile,
            k.closing_rank
        FROM cutoffs k
        JOIN colleges c ON k.institute_code = c.institute_code
        WHERE k.category = ?
          AND k.percentile <= ?
    """
    params = [category, percentile + margin]

    if branch and branch.strip():
        sql += " AND k.branch_name LIKE ?"
        params.append(f"%{branch.strip()}%")

    sql += " ORDER BY k.percentile DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        diff = round(percentile - r["cutoff_percentile"], 4)
        chance = "High" if diff >= 2.0 else ("Moderate" if diff >= 0.0 else "Borderline")

        results.append({
            "institute_code": r["institute_code"],
            "institute_name": r["institute_name"],
            "choice_code": r["choice_code"],
            "branch_name": r["branch_name"],
            "category": r["category"],
            "cutoff_percentile": r["cutoff_percentile"],
            "closing_rank": r["closing_rank"],
            "percentile_diff": diff,
            "admission_chance": chance
        })

    return results
