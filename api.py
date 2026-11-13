import requests as _plain

try:
    from curl_cffi import requests as cf_requests
    _USE_CFFI = True
except ImportError:
    _USE_CFFI = False


BASE = "https://filewale.com"


class FileWaleError(Exception):
    pass


def _origin_headers(path: str) -> dict:
    h = {
        "accept": "application/json, text/plain, */*",
        "origin": BASE,
    }
    if path.startswith("/auth/login"):
        h["content-type"] = "application/json"
        h["referer"] = BASE + "/login"
    elif path.startswith("/users/me"):
        h["referer"] = BASE + "/dashboard"
        h["x-shadowgrow-auth-critical"] = "1"
    elif path.startswith("/wallet/"):
        h["referer"] = BASE + "/dashboard/wallet"
    elif path.startswith("/subscriptions/plans"):
        h["referer"] = BASE + "/subscriptions"
    elif path.startswith("/subscriptions/my-subscriptions"):
        h["referer"] = BASE + "/dashboard/subscriptions"
    elif path.startswith("/subscriptions/"):
        h["referer"] = BASE + "/dashboard"
    elif path.startswith("/tax/") or path.startswith("/payments/"):
        h["referer"] = BASE + "/checkout"
        h["content-type"] = "application/json"
    else:
        h["referer"] = BASE + "/dashboard"
    return h


class FileWaleClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _new_session(self):
        if _USE_CFFI:
            return cf_requests.Session(impersonate="chrome", timeout=self.timeout)
        return _plain.Session()

    def _req(self, method, path, token=None, session=None, **kwargs):
        headers = kwargs.pop("headers", {}) or {}
        headers.update(_origin_headers(path))
        if token:
            headers["authorization"] = f"Bearer {token}"
        sess = session or self._new_session()
        owns = session is None
        url = f"{self.base}{path}"
        try:
            r = sess.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        except Exception as e:
            if owns:
                try: sess.close()
                except Exception: pass
            raise FileWaleError(f"network: {type(e).__name__}: {e}") from e
        if owns:
            try: sess.close()
            except Exception: pass
        if r.status_code == 429:
            raise FileWaleError("rate_limit")
        if r.status_code in (401, 403):
            raise FileWaleError(f"http_{r.status_code}")
        if r.status_code >= 400:
            raise FileWaleError(f"http {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except ValueError as e:
            raise FileWaleError(f"non-json: {r.text[:200]}") from e

    # ------------------------------------------------------------------
    # Auth / profile
    # ------------------------------------------------------------------
    def login(self, identifier, password, session=None):
        data = self._req(
            "POST", "/auth/login", session=session,
            json={"identifier": identifier, "password": password},
        )
        if not data.get("success"):
            raise FileWaleError("login success=false")
        payload = data.get("data") or {}
        token = payload.get("accessToken")
        if not token:
            raise FileWaleError("no access token")
        return {"token": token, "user": payload.get("user") or {}}

    def me(self, token, session=None):
        data = self._req("GET", "/users/me", token=token, session=session)
        if not data.get("success"):
            raise FileWaleError("me success=false")
        return data.get("data") or {}

    # ------------------------------------------------------------------
    # Wallet
    # ------------------------------------------------------------------
    def wallet_balance(self, token, session=None):
        try:
            data = self._req("GET", "/wallet/me/balance", token=token, session=session)
        except FileWaleError:
            return {}
        return data.get("data") or {}

    # ------------------------------------------------------------------
    # Subscriptions — now using the richer endpoints
    # ------------------------------------------------------------------
    def my_subscription(self, token, session=None):
        """Legacy single-sub endpoint. Kept for compatibility."""
        try:
            data = self._req(
                "GET", "/subscriptions/my-subscription",
                token=token, session=session,
            )
        except FileWaleError:
            return {}
        if not data.get("success"):
            return {}
        return data.get("data") or {}

    def all_subscriptions(self, token, lifecycle="active", session=None):
        """GET /subscriptions/my-subscriptions/all?lifecycle=active
        Returns the list of active subs. Better than my-subscription
        because it covers multi-plan accounts."""
        try:
            data = self._req(
                "GET",
                f"/subscriptions/my-subscriptions/all?lifecycle={lifecycle}",
                token=token, session=session,
            )
        except FileWaleError:
            return []
        if not data.get("success"):
            return []
        payload = data.get("data")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("subscriptions", "items", "results", "data"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    def get_plan(self, plan_id, token, session=None):
        """GET /subscriptions/plans/{id} — authoritative plan detail,
        price, currency, quotas. This is the source of truth for pricing."""
        try:
            data = self._req(
                "GET", f"/subscriptions/plans/{plan_id}",
                token=token, session=session,
            )
        except FileWaleError:
            return {}
        if not data.get("success"):
            return {}
        return data.get("data") or {}

    def estimate_order(self, token, unit_amount, quantity=1,
                       item_type="subscription", exchange_rate=1, session=None):
        """POST /tax/estimate-order — returns tax + total for a prospective
        order. Useful if you want to show buyers the exact final cost."""
        try:
            data = self._req(
                "POST", "/tax/estimate-order",
                token=token, session=session,
                json={
                    "items": [{
                        "unitAmount": unit_amount,
                        "quantity": quantity,
                        "itemType": item_type,
                    }],
                    "exchangeRate": exchange_rate,
                },
            )
        except FileWaleError:
            return {}
        if not data.get("success"):
            return {}
        return data.get("data") or {}

    def payment_providers(self, token, session=None):
        """GET /payments/providers — returns the enabled checkout gateways."""
        try:
            data = self._req("GET", "/payments/providers", token=token, session=session)
        except FileWaleError:
            return []
        payload = data.get("data") if data.get("success") else None
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for k in ("providers", "items", "results"):
                if isinstance(payload.get(k), list):
                    return payload[k]
        return []

    # ------------------------------------------------------------------
    # Composite — everything the store needs to price + publish one account
    # ------------------------------------------------------------------
    def _pick_best_sub(self, subs):
        """Given a list of subscriptions, pick the one with the highest
        plan.price. Falls back to the first active entry."""
        if not subs:
            return {}
        priced = []
        for s in subs:
            plan = (s or {}).get("plan") or {}
            try:
                price = float(plan.get("price") or 0)
            except (TypeError, ValueError):
                price = 0.0
            priced.append((price, s))
        priced.sort(key=lambda x: x[0], reverse=True)
        return priced[0][1] if priced else subs[0]

    def snapshot(self, identifier, password):
        """Login → profile + wallet + plan (enriched via /plans/{id}) in one
        HTTP session. This is what app.py calls when admin adds an account."""
        sess = self._new_session()
        try:
            auth = self.login(identifier, password, session=sess)
            token = auth["token"]
            user = auth["user"]

            try:
                user = self.me(token, session=sess) or user
            except FileWaleError:
                pass

            wallet = self.wallet_balance(token, session=sess)

            # prefer the rich list endpoint, fall back to legacy single sub
            subs = self.all_subscriptions(token, "active", session=sess)
            sub = self._pick_best_sub(subs) if subs else {}
            if not sub:
                sub = self.my_subscription(token, session=sess)

            # enrich with canonical plan data if we got an id
            plan_raw = (sub or {}).get("plan") or {}
            plan_id = plan_raw.get("id") or plan_raw.get("planId")
            if plan_id:
                full_plan = self.get_plan(plan_id, token, session=sess)
                if full_plan:
                    merged = dict(plan_raw)
                    merged.update(full_plan if isinstance(full_plan, dict) else {})
                    sub = dict(sub) if sub else {}
                    sub["plan"] = merged

            return {
                "user": user,
                "wallet": wallet,
                "subscription": sub,
                "subscriptions": subs,
                "token": token,
            }
        finally:
            try:
                sess.close()
            except Exception:
                pass


def categorize(plan_name: str) -> str:
    name = (plan_name or "").lower()
    if any(
        k in name
        for k in ("gold", "golden", "royal", "premium", "diamond", "platinum")
    ):
        return "gold"
    if any(
        k in name for k in ("silver", "basic", "starter", "standard")
    ):
        return "silver"
    return "silver"