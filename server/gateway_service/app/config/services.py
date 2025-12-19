import os

SERVICES = {
    "auth": os.getenv("AUTH_SERVICE_URL"),
    "chat": os.getenv("CHAT_SERVICE_URL"),
    "workflow": os.getenv("WORKFLOW_SERVICE_URL"),
    "admin": os.getenv("ADMIN_SERVICE_URL")
}