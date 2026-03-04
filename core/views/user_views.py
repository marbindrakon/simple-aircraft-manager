import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

User = get_user_model()

class UserSearchView(APIView):
    """Search users by username or full name for role assignment."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])
        users = User.objects.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        ).order_by('username')[:10]
        results = []
        for u in users:
            full_name = f"{u.first_name} {u.last_name}".strip()
            results.append({
                'id': str(u.pk),
                'username': u.username,
                'display': f"{u.username} ({full_name})" if full_name else u.username,
            })
        return Response(results)

