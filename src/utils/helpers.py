import os

def first_existing_path(candidates):
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None
