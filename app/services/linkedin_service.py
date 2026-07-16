"""
app/services/linkedin_service.py
──────────────────────────────────
LinkedIn API integration service.
Handles OAuth2 authentication, post creation with image upload,
and analytics fetching.

LinkedIn API Reference:
    https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
TIMEOUT = httpx.Timeout(30.0)


class LinkedInServiceError(Exception):
    """Raised when LinkedIn API calls fail."""
    pass


class LinkedInPublishResult:
    """Result of a LinkedIn publish operation."""

    def __init__(
        self,
        post_id: str,
        post_url: str,
        person_urn: str,
    ) -> None:
        self.post_id = post_id
        self.post_url = post_url
        self.person_urn = person_urn

    def to_dict(self) -> Dict[str, str]:
        return {
            "post_id": self.post_id,
            "post_url": self.post_url,
            "person_urn": self.person_urn,
        }


class LinkedInService:
    """
    LinkedIn API wrapper.

    Supports:
    - OAuth2 authorization URL generation
    - Access token exchange
    - Post creation (text + image)
    - Post analytics fetching
    """

    def __init__(self, access_token: Optional[str] = None) -> None:
        self.access_token = access_token or settings.linkedin_access_token
        self.person_urn = settings.linkedin_person_urn

    def _get_headers(self) -> Dict[str, str]:
        """Build authenticated request headers."""
        if not self.access_token:
            raise LinkedInServiceError(
                "LinkedIn access token is not configured. "
                "Set LINKEDIN_ACCESS_TOKEN in your .env file or complete OAuth flow."
            )
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

    def get_auth_url(self) -> str:
        """
        Generate LinkedIn OAuth2 authorization URL.
        User should visit this URL to grant permissions.

        Returns:
            Authorization URL string
        """
        params = {
            "response_type": "code",
            "client_id": settings.linkedin_client_id,
            "redirect_uri": settings.linkedin_redirect_uri,
            "scope": "openid profile email w_member_social",
            "state": "linkedin_agent_auth",
        }
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response dict with access_token, expires_in, etc.
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.linkedin_redirect_uri,
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise LinkedInServiceError(f"Token exchange failed: {response.text}")

            token_data = response.json()
            log.info("LinkedIn access token obtained successfully")
            return token_data

    async def get_profile(self) -> Dict[str, Any]:
        """
        Fetch the authenticated user's LinkedIn profile.

        Returns:
            Profile data dict
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{LINKEDIN_API_BASE}/userinfo",
                headers=self._get_headers(),
            )

            if response.status_code == 401:
                raise LinkedInServiceError("Access token is invalid or expired")

            response.raise_for_status()
            return response.json()

    async def upload_image(self, image_url: str) -> Optional[str]:
        """
        Upload an image to LinkedIn (required before attaching to a post).

        Strategy:
        1. Register upload intent with LinkedIn
        2. Upload the image binary
        3. Return the LinkedIn image URN

        Args:
            image_url: Public URL of the image to upload

        Returns:
            LinkedIn image URN (e.g., "urn:li:image:C5622AQH...") or None
        """
        if not image_url:
            return None

        try:
            person_urn = self.person_urn
            if not person_urn:
                log.warning("LinkedIn person URN not configured, skipping image upload")
                return None

            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                # Step 1: Initialize upload
                init_response = await client.post(
                    f"{LINKEDIN_API_BASE}/images?action=initializeUpload",
                    json={
                        "initializeUploadRequest": {
                            "owner": person_urn,
                        }
                    },
                    headers=headers,
                )
                init_response.raise_for_status()
                init_data = init_response.json()

                upload_url = init_data["value"]["uploadUrl"]
                image_urn = init_data["value"]["image"]

                # Step 2: Download image bytes OR decode base64
                if image_url.startswith("data:image/"):
                    import base64
                    # Format is data:image/jpeg;base64,.....
                    header, encoded = image_url.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                else:
                    img_response = await client.get(image_url)
                    img_response.raise_for_status()
                    image_bytes = img_response.content

                # Step 3: Upload binary to LinkedIn
                upload_response = await client.put(
                    upload_url,
                    content=image_bytes,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/octet-stream",
                    },
                )
                upload_response.raise_for_status()

            log.info(f"Image uploaded to LinkedIn | urn={image_urn}")
            return image_urn

        except Exception as e:
            log.warning(f"Image upload to LinkedIn failed: {e}. Post will be published without image.")
            return None

    async def publish_post(
        self,
        content: str,
        image_url: Optional[str] = None,
        image_alt_text: Optional[str] = None,
    ) -> LinkedInPublishResult:
        """
        Publish a post to LinkedIn.

        Args:
            content: Full post text content
            image_url: Optional image URL to attach
            image_alt_text: Alt text for the image

        Returns:
            LinkedInPublishResult with post_id and URL

        Raises:
            LinkedInServiceError: If publishing fails
        """
        person_urn = self.person_urn
        if not person_urn:
            raise LinkedInServiceError(
                "LINKEDIN_PERSON_URN is not configured. "
                "Set it in your .env file (e.g., urn:li:person:YOUR_ID)"
            )

        # Upload image if provided
        image_urn = None
        if image_url:
            image_urn = await self.upload_image(image_url)

        # Build post payload
        post_body: Dict[str, Any] = {
            "author": person_urn,
            "commentary": content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        # Attach image if uploaded
        if image_urn:
            post_body["content"] = {
                "media": {
                    "altText": image_alt_text or "Post image",
                    "id": image_urn,
                }
            }

        log.info(f"Publishing post to LinkedIn | person={person_urn} | has_image={bool(image_urn)}")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{LINKEDIN_API_BASE}/posts",
                json=post_body,
                headers=self._get_headers(),
            )

            if response.status_code == 401:
                raise LinkedInServiceError("LinkedIn access token is expired or invalid")
            if response.status_code == 403:
                raise LinkedInServiceError(
                    "Insufficient LinkedIn permissions. "
                    "Your app needs 'w_member_social' permission."
                )
            if response.status_code not in (200, 201):
                raise LinkedInServiceError(
                    f"LinkedIn API error {response.status_code}: {response.text}"
                )

            # LinkedIn returns post ID in the response header
            post_urn = response.headers.get("x-restli-id", "")
            if not post_urn and response.content:
                try:
                    post_urn = response.json().get("id", "")
                except Exception:
                    pass

        post_id = post_urn.split(":")[-1] if post_urn else "unknown"
        post_url = f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else ""

        log.info(f"Post published successfully | post_id={post_id}")
        return LinkedInPublishResult(
            post_id=post_id,
            post_url=post_url,
            person_urn=person_urn,
        )

    async def get_post_analytics(self, post_urn: str) -> Dict[str, int]:
        """
        Fetch analytics for a published post.

        Args:
            post_urn: LinkedIn post URN

        Returns:
            Dict with views, likes, comments, shares
        """
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(
                    f"{LINKEDIN_API_BASE}/socialActions/{post_urn}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            return {
                "likes": data.get("likesSummary", {}).get("totalLikes", 0),
                "comments": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                "shares": data.get("shareStatistics", {}).get("uniqueImpressionsCount", 0),
                "views": 0,  # Requires additional API call with analytics scope
            }
        except Exception as e:
            log.warning(f"Could not fetch post analytics: {e}")
            return {"likes": 0, "comments": 0, "shares": 0, "views": 0}


# Module-level singleton
linkedin_service = LinkedInService()
