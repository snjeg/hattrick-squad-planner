from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from requests_oauthlib import OAuth1Session

REQUEST_TOKEN_URL = "https://chpp.hattrick.org/oauth/request_token.ashx"
AUTHORIZE_URL = "https://chpp.hattrick.org/oauth/authorize.aspx"
ACCESS_TOKEN_URL = "https://chpp.hattrick.org/oauth/access_token.ashx"
XML_URL = "https://chpp.hattrick.org/chppxml.ashx"


@dataclass(frozen=True, slots=True)
class RequestToken:
    token: str
    secret: str
    authorization_url: str


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    secret: str


class CHPPClient(Protocol):
    def fetch_own_senior_players(self, access_token: AccessToken | None = None) -> str: ...


class FinanceCHPPClient(CHPPClient, Protocol):
    def fetch_own_economy(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str: ...

    def fetch_own_arena(self, access_token: AccessToken | None = None) -> str: ...

    def fetch_own_matches(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str: ...


class MockCHPPClient:
    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def fetch_own_senior_players(self, access_token: AccessToken | None = None) -> str:
        return self.fixture_path.read_text(encoding="utf-8")

    def _fixture(self, name: str) -> str:
        return (self.fixture_path.parent / name).read_text(encoding="utf-8")

    def fetch_own_economy(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str:
        return self._fixture("economy.xml")

    def fetch_own_arena(self, access_token: AccessToken | None = None) -> str:
        return self._fixture("arena.xml")

    def fetch_own_matches(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str:
        return self._fixture("matches.xml")


class OAuthCHPPClient:
    def __init__(self, consumer_key: str, consumer_secret: str, players_version: str) -> None:
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.players_version = players_version

    def begin_authorization(self, callback_url: str) -> RequestToken:
        session = OAuth1Session(
            self.consumer_key, client_secret=self.consumer_secret, callback_uri=callback_url
        )
        payload = session.fetch_request_token(REQUEST_TOKEN_URL)
        token = payload["oauth_token"]
        secret = payload["oauth_token_secret"]
        return RequestToken(
            token=token,
            secret=secret,
            authorization_url=session.authorization_url(AUTHORIZE_URL),
        )

    def complete_authorization(
        self, request_token: str, request_secret: str, verifier: str
    ) -> AccessToken:
        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=request_token,
            resource_owner_secret=request_secret,
            verifier=verifier,
        )
        payload = session.fetch_access_token(ACCESS_TOKEN_URL)
        return AccessToken(token=payload["oauth_token"], secret=payload["oauth_token_secret"])

    def _fetch_xml(
        self,
        file: str,
        version: str,
        access_token: AccessToken | None,
        **parameters: int,
    ) -> str:
        if access_token is None:
            raise ValueError("Live CHPP sync requires an OAuth access token")
        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=access_token.token,
            resource_owner_secret=access_token.secret,
        )
        query: dict[str, str | int] = {"file": file, "version": version}
        query.update(parameters)
        response = session.get(f"{XML_URL}?{urlencode(query)}", timeout=30)
        response.raise_for_status()
        return response.text

    def fetch_own_senior_players(self, access_token: AccessToken | None = None) -> str:
        return self._fetch_xml("players", self.players_version, access_token)

    def fetch_own_economy(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str:
        return self._fetch_xml("economy", "1.3", access_token, teamId=team_id)

    def fetch_own_arena(self, access_token: AccessToken | None = None) -> str:
        return self._fetch_xml("arenadetails", "1.2", access_token)

    def fetch_own_matches(
        self, team_id: int, access_token: AccessToken | None = None
    ) -> str:
        return self._fetch_xml("matches", "2.2", access_token, teamID=team_id)
