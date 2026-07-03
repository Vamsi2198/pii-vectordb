import json
from datetime import datetime


def log_access(user:str, role:str, question:str, results):
    entry = {
        "time": datetime.utcnow().isoformat(),
        "user":user,
        "role":role,
        "question":question,
        "retrieved": [
            {"source": hit["meta"]["source"], "allowed_roles": hit["meta"].get("allowed_roles")}
            for hit in results
        ],
    }
    with open("audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")