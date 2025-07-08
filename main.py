from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Enable CORS for React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Atlas connection
MONGO_URL = os.getenv("MONGO_URL")
print("Connecting to MongoDB at:", MONGO_URL)
client = AsyncIOMotorClient(MONGO_URL)
db = client.game  # DB name will be 'game'

# ---------------- Models ----------------

class NumberedTile(BaseModel):
    position: List[int]
    number: int

class GameCreate(BaseModel):
    creator: str
    maxNumber: int
    numberedTiles: List[NumberedTile]

class Attempt(BaseModel):
    player: str
    path: List[List[int]]
    duration: float
    successful: bool
    mainTime: Optional[float] = None

# ---------------- Routes ----------------

@app.post("/games")
async def create_game(game: GameCreate):
    print("Received Game:", game)
    try:
        game_data = game.dict()
        game_data["createdAt"] = datetime.utcnow()
        result = await db.games.insert_one(game_data)
        return {"game_id": str(result.inserted_id)}
    except Exception as e:
        print("❌ Error creating game:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/games/{game_id}")
async def get_game(game_id: str):
    try:
        game = await db.games.find_one({"_id": ObjectId(game_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid game ID format")
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game["_id"] = str(game["_id"])
    return game

@app.post("/games/{game_id}/attempt")
async def submit_attempt(game_id: str, attempt: Attempt):
    attempt_data = attempt.dict()
    attempt_data["game_id"] = game_id
    attempt_data["timestamp"] = datetime.utcnow()
    await db.attempts.insert_one(attempt_data)
    return {"message": "Attempt recorded"}

@app.get("/games/{game_id}/attempts")
async def get_attempts(game_id: str):
    attempts = await db.attempts.find({"game_id": game_id}).to_list(100)
    for attempt in attempts:
        attempt["_id"] = str(attempt["_id"])
    return attempts
