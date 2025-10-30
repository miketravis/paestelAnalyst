import os
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from google.cloud.sql.connector import Connector, IPTypes

# --- Database Setup ---

# Load environment variables
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")

# Define your SQLAlchemy model
Base = declarative_base()
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

# Initialize the Cloud SQL Connector
connector = Connector()

# Function to get the database connection
def get_db_connection() -> Engine:
    def getconn():
        # Connect using the Cloud SQL Connector
        conn = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PRIVATE  # Use private IP
        )
        return conn

    # Create the SQLAlchemy engine
    engine = create_engine("postgresql+pg8000://", creator=getconn)
    return engine

# Initialize engine and session
engine = get_db_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI App ---

app = FastAPI()

# This is crucial for your Vercel frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change "*" to your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the table on app startup
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.on_event("shutdown")
def on_shutdown():
    connector.close()

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"Hello": "From FastAPI on Cloud Run!"}

@app.post("/items/")
def create_item(name: str, db: Session = Depends(get_db)):
    new_item = Item(name=name)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.get("/items/")
def read_items(db: Session = Depends(get_db)):
    items = db.query(Item).all()
    return items

# This block allows you to run locally with `python main.py`
if __name__ == "__main__":
    # For local dev, you'd need to set the env vars or use a .env file
    # and likely run the Cloud SQL Auth Proxy locally
    uvicorn.run(app, host="0.0.0.0", port=8000)