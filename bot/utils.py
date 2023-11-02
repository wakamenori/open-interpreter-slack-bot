def get_temp_dir(user_id: str, thread_ts: str) -> str:
    return f"/work/{user_id}/{thread_ts}"
