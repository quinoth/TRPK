import httpx
from app.config.services import SERVICES
from app.core.security import decode_jwt

async def get_user_profile(token: str):
    user_data = decode_jwt(token)
    async with httpx.AsyncClient() as client:
        # Получаем данные из разных сервисов
        try:
            auth_resp = await client.get(
                f"{SERVICES['auth']}/api/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            chat_resp = await client.get(
                f"{SERVICES['chat']}/api/chat/history/private?with_email={user_data['sub']}&limit=5",
                headers={"Authorization": f"Bearer {token}"}
            )
            workflow_resp = await client.get(
                f"{SERVICES['workflow']}/api/test/results",
                headers={"Authorization": f"Bearer {token}"}
            )
            return {
                "user": auth_resp.json(),
                "recent_chats": chat_resp.json().get("messages", []),
                "test_results": workflow_resp.json()
            }
        except Exception as e:
            return {"error": str(e)}