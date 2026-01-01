#!/usr/bin/env python3
"""
Reset admin password for testing
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

def reset_admin_password():
    # Create database connection
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # SQL to update admin password
        new_password_hash = hashlib.sha256('admin'.encode()).hexdigest()
        
        from sqlalchemy import text
        
        result = db.execute(
            text("UPDATE users SET hashed_password = :password WHERE email = :email"),
            {"password": new_password_hash, "email": "admin@example.com"}
        )
        
        db.commit()
        
        if result.rowcount > 0:
            print(f"✓ Admin password reset to 'admin'")
            print(f"  Email: admin@example.com")
            print(f"  Password: admin")
        else:
            print("✗ Admin user not found")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin_password()