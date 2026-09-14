from __future__ import annotations

import json
from pathlib import Path
from urllib import request, error, parse

try:
    import msal
except Exception:  # pragma: no cover - handled by configuration diagnostics
    msal = None

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class GraphConfigurationError(RuntimeError):
    pass


class GraphApiError(RuntimeError):
    def __init__(self, status, message, payload=None):
        super().__init__(f"Microsoft Graph HTTP {status}: {message}")
        self.status = status
        self.payload = payload


def graph_config_from_mapping(root):
    """Read the non-interactive Graph configuration from a secrets-like mapping.

    Nothing in this helper logs or returns private key contents.  The certificate path
    points to a VPS-only file, normally below /opt/clarte360/secrets/.
    """
    root = dict(root or {})
    raw = root.get("microsoft_graph") or root.get("MICROSOFT_GRAPH") or {}
    raw = dict(raw or {})
    return {
        "enabled": bool(raw.get("enabled", False)),
        "tenant_id": str(raw.get("tenant_id") or "").strip(),
        "client_id": str(raw.get("client_id") or "").strip(),
        "organizer_user_id": str(raw.get("organizer_user_id") or "").strip(),
        "organizer_upn": str(raw.get("organizer_upn") or "teams@clarte360.com").strip(),
        "certificate_path": str(raw.get("certificate_path") or "").strip(),
        "certificate_thumbprint": str(raw.get("certificate_thumbprint") or "").replace(" ", "").strip(),
        "guest_invites_enabled": bool(raw.get("guest_invites_enabled", False)),
        "stable_link_mode": bool(raw.get("stable_link_mode", True)),
        "request_timeout_seconds": int(raw.get("request_timeout_seconds") or 30),
    }


def graph_config_missing(cfg):
    if not cfg.get("enabled"):
        return ["enabled"]
    keys = ("tenant_id", "client_id", "organizer_user_id", "certificate_path", "certificate_thumbprint")
    missing = [k for k in keys if not cfg.get(k)]
    p = cfg.get("certificate_path")
    if p and not Path(p).exists():
        missing.append("certificate_path (fichier introuvable)")
    if msal is None:
        missing.append("dépendance msal")
    return missing


class GraphClient:
    def __init__(self, cfg):
        self.cfg = dict(cfg or {})
        missing = graph_config_missing(self.cfg)
        if missing:
            raise GraphConfigurationError("Configuration Microsoft Graph incomplète : " + ", ".join(missing))
        cert_path = Path(self.cfg["certificate_path"])
        private_key = cert_path.read_text(encoding="utf-8")
        authority = f"https://login.microsoftonline.com/{self.cfg['tenant_id']}"
        self.app = msal.ConfidentialClientApplication(
            self.cfg["client_id"],
            authority=authority,
            client_credential={
                "private_key": private_key,
                "thumbprint": self.cfg["certificate_thumbprint"],
            },
        )
        self.timeout = int(self.cfg.get("request_timeout_seconds") or 30)

    def _token(self):
        result = self.app.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        token = result.get("access_token") if isinstance(result, dict) else None
        if not token:
            detail = (result or {}).get("error_description") or (result or {}).get("error") or "jeton indisponible"
            raise GraphConfigurationError(f"Authentification Microsoft Graph impossible : {detail}")
        return token

    def request_json(self, method, path, body=None):
        url = path if str(path).startswith("http") else GRAPH_ROOT + "/" + str(path).lstrip("/")
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, method=method.upper())
        req.add_header("Authorization", "Bearer " + self._token())
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except error.HTTPError as ex:
            raw = ex.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                msg = ((payload.get("error") or {}).get("message") or raw)[:1000]
            except Exception:
                payload = None
                msg = raw[:1000]
            raise GraphApiError(ex.code, msg, payload) from ex

    def create_online_meeting(self, subject, start_iso, end_iso, attendees=None):
        body = {
            "startDateTime": start_iso,
            "endDateTime": end_iso,
            "subject": subject,
            # Beneficiaries must not be able to start/admit everybody by default.
            "lobbyBypassSettings": {"scope": "organizer", "isDialInBypassEnabled": False},
            "allowedPresenters": "organizer",
        }
        if attendees:
            body["participants"] = {"attendees": attendees}
        uid = parse.quote(self.cfg["organizer_user_id"], safe="")
        return self.request_json("POST", f"/users/{uid}/onlineMeetings", body)

    def update_online_meeting(self, meeting_id, patch):
        uid = parse.quote(self.cfg["organizer_user_id"], safe="")
        mid = parse.quote(str(meeting_id), safe="")
        return self.request_json("PATCH", f"/users/{uid}/onlineMeetings/{mid}", patch)

    def get_user(self, user_id_or_upn):
        uid = parse.quote(str(user_id_or_upn), safe="")
        return self.request_json("GET", f"/users/{uid}?$select=id,displayName,mail,userPrincipalName,userType")

    def find_user_by_email(self, email):
        """Search an existing Entra identity before any invitation/creation request.

        Returns one exact mail/UPN match or None. This deliberately prevents blind
        guest creation and duplicate identities.
        """
        e=str(email or '').strip().lower()
        if not e:
            return None
        safe=e.replace("'", "''")
        filt=parse.quote(f"mail eq '{safe}' or userPrincipalName eq '{safe}'", safe="'()=$ ")
        data=self.request_json("GET", f"/users?$filter={filt}&$select=id,displayName,mail,userPrincipalName,userType")
        vals=data.get('value',[]) if isinstance(data,dict) else []
        exact=[]
        for u in vals:
            mails={(u.get('mail') or '').strip().lower(),(u.get('userPrincipalName') or '').strip().lower()}
            if e in mails: exact.append(u)
        return exact[0] if len(exact)==1 else None

    def invite_guest(self, email, redirect_url, send_invitation_message=True, display_name=None):
        body = {
            "invitedUserEmailAddress": email,
            "inviteRedirectUrl": redirect_url,
            "sendInvitationMessage": bool(send_invitation_message),
        }
        if display_name:
            body["invitedUserDisplayName"] = display_name
        return self.request_json("POST", "/invitations", body)

    def list_attendance_reports(self, meeting_id):
        uid = parse.quote(self.cfg["organizer_user_id"], safe="")
        mid = parse.quote(str(meeting_id), safe="")
        return self.request_json("GET", f"/users/{uid}/onlineMeetings/{mid}/attendanceReports").get("value", [])

    def list_attendance_records(self, meeting_id, report_id):
        uid = parse.quote(self.cfg["organizer_user_id"], safe="")
        mid = parse.quote(str(meeting_id), safe="")
        rid = parse.quote(str(report_id), safe="")
        return self.request_json("GET", f"/users/{uid}/onlineMeetings/{mid}/attendanceReports/{rid}/attendanceRecords").get("value", [])
