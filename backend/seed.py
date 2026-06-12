from database import get_database
from auth import get_password_hash
import datetime


async def seed_users():
    db = get_database()
    users_col = db.users

    admin_email = "admin@ejercito.mil.ar"
    user_email = "user@ejercito.mil.ar"

    # Seeding Admin
    existing_admin = await users_col.find_one({"email": admin_email})
    if not existing_admin:
        admin_user = {
            "email": admin_email,
            "password_hash": get_password_hash("admin123"),
            "role": "admin",
            "created_at": datetime.datetime.utcnow(),
        }
        await users_col.insert_one(admin_user)
        print(f"Seeded Admin: {admin_email} con contraseña 'admin123'")
    else:
        print(f"Admin ya existe: {admin_email}")

    # Seeding User
    existing_user = await users_col.find_one({"email": user_email})
    if not existing_user:
        common_user = {
            "email": user_email,
            "password_hash": get_password_hash("user123"),
            "role": "user",
            "created_at": datetime.datetime.utcnow(),
        }
        await users_col.insert_one(common_user)
        print(f"Seeded User: {user_email} con contraseña 'user123'")
    else:
        print(f"User ya existe: {user_email}")
