from core.database.database_manager import DatabaseManager
from core.utils.database_viewer import inspect_database

opts = {
  "id": {
    "type": "INTEGER",
    "primary": True,
    "allow_null": False
  },
  "username": {
    "type": "TEXT",
    "allow_null": False
  },
  "email": {
    "type": "TEXT",
    "allow_null": True
  },
  "profile_id": {
    "type": "INTEGER",
    "foreign": ["profiles", "id"],
    "allow_null": True
  }
}

db = DatabaseManager(bot_id="Customelolibot")
# db.delete_table("test")
# db.create_table("test", opts)

# row1 =  {
#   "id": 1,
#   "username": "testuser",
#   "email": "stuff@stuff",
#   "profile_id": None}

# row2 =  {
#   "id": 2,
#   "username": "testuser22",
#   "email": "stuff@stuff",
#   "profile_id": 5}

# db.add_entry("test", row1)
# db.add_entry("test", row2)
db.delete_row("test", "id", 1)

inspect_database("databases/bot_Customelolibot.db")

