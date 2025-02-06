class Database:
    def __init__(self):
        # In-memory storage using dictionary
        # {user_id: {"points": points, "username": username}}
        self.users = {}
        # Username to user_id mapping
        self.username_to_id = {}

    def _update_username_mapping(self, user_id: int, username: str):
        """Update username to user_id mapping"""
        if username:
            # Remove old mapping if exists
            old_username = self.users[user_id].get("username") if user_id in self.users else None
            if old_username and old_username in self.username_to_id:
                del self.username_to_id[old_username]
            # Add new mapping
            self.username_to_id[username] = user_id

    def clear_all_points(self):
        """Clear all points from the database"""
        # Clear all points but keep usernames
        for user_id in self.users:
            self.users[user_id]["points"] = 0
        return True

    def get_user_id_by_username(self, username: str) -> int:
        """Get user_id by username"""
        return self.username_to_id.get(username)

    def get_all_users(self) -> list:
        """Get list of all usernames"""
        return list(self.username_to_id.keys())

    def add_points(self, user_id: int, points: int, username: str = None) -> bool:
        """Add points to a user"""
        if user_id not in self.users:
            self.users[user_id] = {"points": 0, "username": username}

        self.users[user_id]["points"] += points
        if username:
            self.users[user_id]["username"] = username
            self._update_username_mapping(user_id, username)
        return True

    def subtract_points(self, user_id: int, points: int, username: str = None) -> bool:
        """Subtract points from a user"""
        if user_id not in self.users:
            self.users[user_id] = {"points": 0, "username": username}

        self.users[user_id]["points"] -= points
        if username:
            self.users[user_id]["username"] = username
            self._update_username_mapping(user_id, username)
        return True

    def get_user_points(self, user_id: int) -> int:
        """Get points for a specific user"""
        return self.users.get(user_id, {"points": 0})["points"]

    def get_top_users(self, limit: int = 10) -> list:
        """Get top users by points"""
        sorted_users = sorted(
            self.users.items(),
            key=lambda x: x[1]["points"],
            reverse=True
        )
        return sorted_users[:limit]