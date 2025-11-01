from core.database.database_manager import DatabaseManager

def assign_superadmin(user_id: int):
    # Use the same database as the bot
    db = DatabaseManager(bot_id="Customelolibot")
    
    # Assign superadmin role
    db.add_role(user_id, "superadmin")
    
    # Verify the role was set
    roles = db.get_roles()
    print(f"Current roles after update: {roles}")

if __name__ == "__main__":
    # Your user ID from the error messages
    USER_ID = 7537666736
    assign_superadmin(USER_ID)
    print(f"✅ Assigned superadmin role to user {USER_ID}")