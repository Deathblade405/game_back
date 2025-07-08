from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://game-front-pedx.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.getenv("MONGO_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
client = AsyncIOMotorClient(MONGO_URL)
db = client.game

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_pwd, hashed_pwd) -> bool:
    return pwd_context.verify(plain_pwd, hashed_pwd)

def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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

class UserRegister(BaseModel):
    name: str
    gamer_key: str
    phone: str
    password: str
    role: str  # boss or player

class UserLogin(BaseModel):
    phone: str
    password: str

@app.post("/auth/register")
async def register(user: UserRegister):
    if await db.users.find_one({"phone": user.phone}):
        raise HTTPException(status_code=400, detail="Phone already registered")
    hashed = hash_password(user.password)
    data = user.dict()
    data["password"] = hashed
    data["createdAt"] = datetime.utcnow()
    await db.users.insert_one(data)
    return {"message": "User registered successfully"}

@app.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"phone": data.phone})
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user["_id"]), "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]), "name": user["name"],
            "gamer_key": user["gamer_key"], "phone": user["phone"],
             "role": user["role"]
        }
    }

# ---------------- Game Routes ----------------

@app.post("/games/")
async def create_game(game: GameCreate):
    game_data = game.dict()
    game_data["createdAt"] = datetime.utcnow()
    result = await db.games.insert_one(game_data)
    return {"game_id": str(result.inserted_id)}

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
