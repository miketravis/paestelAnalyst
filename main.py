import os
import uvicorn
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from google.cloud.sql.connector import Connector, IPTypes
from contextlib import asynccontextmanager

# --- Environment Variable Setup ---
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")

# --- SQLAlchemy Model Setup ---
Base = declarative_base()


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

class ItemCreate(BaseModel):
    name: str

# --- Database Connection Logic ---
db_engine: Engine | None = None
DBSessionLocal: sessionmaker | None = None
db_connector: Connector | None = None


# Function to get the database connection
def get_db_connection() -> Engine:
    global db_connector
    db_connector = Connector()

    # Check if we're running in Cloud Run (which sets K_SERVICE)
    is_cloud_run = os.environ.get("K_SERVICE") is not None
    ip_type = IPTypes.PRIVATE if is_cloud_run else IPTypes.PUBLIC
    print(f"Connecting with IP type: {ip_type.name}")  # For debugging

    # This inner function 'getconn' is what SQLAlchemy will call
    # to get a new connection from the pool
    def getconn():
        conn = db_connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",  # <-- Driver is pg8000
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=ip_type
        )
        return conn

    # Create the SQLAlchemy engine
    engine = create_engine(
        "postgresql+pg8000://",  # <-- Driver string is pg8000
        creator=getconn
    )
    return engine


# Lifespan event manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App startup... connecting to database.")
    global db_engine, DBSessionLocal

    try:
        db_engine = get_db_connection()

        # This block creates the table
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # Test connection
            Base.metadata.create_all(bind=conn) # Create tables
            conn.commit()
            print("Database connection successful and tables created.")

        DBSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        print("Sessionmaker created.")

    except Exception as e:
        print(f"FATAL: Database connection failed during startup: {e}")

    yield  # App is running

    print("App shutdown... closing database connector.")
    if db_connector:
        db_connector.close()
    if db_engine:
        db_engine.dispose()


# --- FastAPI App Setup ---
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get a DB session
def get_db():
    if DBSessionLocal is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    db = DBSessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"Hello": "From FastAPI!"}


@app.post("/items/")
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    try:
        new_item = Item(name=item.name)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create item: {e}")


@app.get("/items/")
def read_items(db: Session = Depends(get_db)):
    try:
        items = db.query(Item).all()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read items: {e}")


# This block is only for local testing
if __name__ == "__main__":
    print("Running in local development mode.")
    uvicorn.run(app, host="0.0.0.0", port=8000)