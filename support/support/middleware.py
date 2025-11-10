from urllib.parse import parse_qs
import jwt
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from asgiref.sync import sync_to_async

User = get_user_model()

class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        qs = parse_qs(query_string)
        token_list = qs.get("token", [])

        user = None
        if token_list:
            token = token_list[0]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("user_id")
                if user_id:
                    user = await self.get_user(user_id)
            except Exception as e:
                print("JWT error:", e)

        scope["user"] = user or AnonymousUser()
        return await self.app(scope, receive, send)

    @staticmethod
    async def get_user(user_id):
        try:
            return await sync_to_async(User.objects.get)(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
