
import asyncio
import sys
import os

# Add the current directory to sys.path to import local modules
sys.path.append(os.getcwd())

from core.database import AsyncSessionFactory, User, UserRole, log_audit
from core.security import hash_password
from sqlalchemy import select

async def test_register():
    print("Testing registration logic...")
    async with AsyncSessionFactory() as db:
        username = "testuser_debug"
        password = "testpassword123"
        
        # Check if exists
        result = await db.execute(select(User).where(User.username == username))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User {username} already exists, deleting for clean test.")
            await db.delete(existing)
            await db.commit()
            
        try:
            new_user = User(
                username=username,
                hashed_password=hash_password(password),
                role=UserRole.guest
            )
            db.add(new_user)
            await db.flush()
            print(f"User flushed, ID: {new_user.id}")
            
            await log_audit(
                db=db,
                user_id=new_user.id,
                action_type="REGISTER",
                details={"ip": "127.0.0.1"}
            )
            print("Audit logged.")
            
            await db.commit()
            print("Commit successful!")
        except Exception as e:
            print(f"Error during registration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_register())
