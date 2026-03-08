from fastapi import FastAPI, Depends
from app.auth.deps import get_current_user
from app.auth.keycloak import User


app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"message": f"Hello, {user.username}!"}