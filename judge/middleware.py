import logging
import time
import re
from ipaddress import ip_address
from urllib.parse import quote as urlquote

from django.conf import settings
from django.contrib.sessions.models import Session
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import Resolver404, resolve, reverse
from django_redis import get_redis_connection

logger = logging.getLogger("judge.request")


_IP_RE = re.compile(r"""
    ^\s*
    (?:\[(?P<ipv6>[^\]]+)\]|(?P<ipv4>[^:]+))
    (?::(?P<port>\d+))?
    \s*$
""", re.X)


def _extract_ip(raw_ip: str) -> str:
    """Bỏ phần :port nếu có và xác thực IP hợp lệ"""
    if not raw_ip:
        return ""
    m = _IP_RE.match(raw_ip)
    if not m:
        return ""
    ip = m.group("ipv6") or m.group("ipv4") or ""
    try:
        return str(ip_address(ip))
    except ValueError:
        return ""


def get_client_ip(request) -> str:
    """
    Lấy IP thật của client khi có Cloudflare hoặc reverse proxy.
    Ưu tiên:
    1. CF-Connecting-IP  (Cloudflare)
    2. X-Forwarded-For    (proxy chuỗi IP)
    3. X-Real-IP          (nếu Nginx set)
    4. REMOTE_ADDR        (fallback)
    """
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return _extract_ip(cf_ip.strip())

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        first_ip = xff.split(",")[0].strip()
        return _extract_ip(first_ip)

    real_ip = request.META.get("HTTP_X_REAL_IP")
    if real_ip:
        return _extract_ip(real_ip)

    remote = request.META.get("REMOTE_ADDR")
    return _extract_ip(remote)


class BlockedIpMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        if ip and (ip in settings.BLOCKED_IPS or ip.startswith("43.")):
            raise Http404()

        response = self.get_response(request)
        return response


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.r = get_redis_connection("default")
        self.window = 10
        self.limit = 80
        self.block_seconds = 10
        self.prefix = "rl"

    def __call__(self, request):
        # CHẶN TRƯỚC KHI VÀO VIEW
        resp = self._check_rate(request)
        if resp is not None:
            return resp  # => trả HttpResponse 429 tại đây

        # Không bị chặn thì cho đi tiếp
        response = self.get_response(request)
        return response

    def _check_rate(self, request):
        ip = get_client_ip(request)
        if not ip:
            return None  # Không lấy được IP thì không chặn
        now = time.time()
        zkey = f"{self.prefix}:win:{ip}"
        bkey = f"{self.prefix}:block:{ip}"

        ttl = self.r.ttl(bkey)
        if ttl and ttl > 0:
            return self._too_many(ttl)

        pipe = self.r.pipeline()
        pipe.zremrangebyscore(zkey, "-inf", now - self.window)
        pipe.zadd(zkey, {str(now): now})
        pipe.zcard(zkey)
        pipe.expire(zkey, self.window + self.block_seconds + 5)
        _, _, count, _ = pipe.execute()

        if count > self.limit:
            self.r.set(bkey, "1", ex=self.block_seconds)
            return self._too_many(self.block_seconds)

        return None

    def _too_many(self, retry_after):
        resp = JsonResponse(
            {"detail": "Bạn thao tác quá nhanh, vui lòng thử lại sau.",
             "retry_after_seconds": int(retry_after)},
            status=429,
        )
        resp["Retry-After"] = str(int(retry_after))
        return resp


class LogRequestsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = "AnonymousUser" if request.user.is_anonymous else request.user.username
        ip = get_client_ip(request)
        # Log the user access URL
        info = f"User {user} in IP:{ip} accessed {request.path} - {request.method}"
        logger.info(info)

        response = self.get_response(request)
        return response


# One session_key to one Person anytime
class OneSessionPerUser(object):
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_session_key = request.user.logged_in_user.session_key

            if (
                current_session_key
                and current_session_key != request.session.session_key
            ):
                Session.objects.filter(session_key=current_session_key).delete()

            request.user.logged_in_user.session_key = request.session.session_key
            request.user.logged_in_user.save()

        return self.get_response(request)


class ShortCircuitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            callback, args, kwargs = resolve(
                request.path_info,
                getattr(request, "urlconf", None),
            )
        except Resolver404:
            callback, args, kwargs = None, None, None

        if getattr(callback, "short_circuit_middleware", False):
            return callback(request, *args, **kwargs)
        return self.get_response(request)


class DMOJLoginMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.profile = request.user.profile
            logout_path = reverse("auth_logout")
            # webauthn_path = reverse('webauthn_assert')
            change_password_path = reverse("password_change")
            change_password_done_path = reverse("password_change_done")
            # has_2fa = profile.is_totp_enabled or profile.is_webauthn_enabled
            # if (has_2fa and not request.session.get('2fa_passed', False) and
            #         request.path not in (login_2fa_path, logout_path, webauthn_path) and
            #         not request.path.startswith(settings.STATIC_URL)):
            #     return HttpResponseRedirect(login_2fa_path + '?next=' + urlquote(request.get_full_path()))
            if (
                request.session.get("password_pwned", False)
                and request.path
                not in (change_password_path, change_password_done_path, logout_path)
                and not request.path.startswith(settings.STATIC_URL)
            ):
                return HttpResponseRedirect(
                    change_password_path + "?next=" + urlquote(request.get_full_path()),
                )
        else:
            request.profile = None
        return self.get_response(request)


class DMOJImpersonationMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_impersonate:
            request.no_profile_update = True
            request.profile = request.user.profile
        return self.get_response(request)


class ContestMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        profile = request.profile
        if profile:
            profile.update_contest()
            request.participation = profile.current_contest
            request.in_contest = request.participation is not None
        else:
            request.in_contest = False
            request.participation = None
        return self.get_response(request)
