import os

import requests
from django.utils import timezone

from .models import GoogleDriveToken

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
DEFAULT_REDIRECT_URI = 'https://schoolh-bay.vercel.app/open-learning/google-drive/callback/'
DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
]


class GoogleDriveService:
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
        self.redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', DEFAULT_REDIRECT_URI)
        self.root_folder_id = os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    def authorization_url(self, state):
        if not self.is_configured():
            raise RuntimeError('GOOGLE_CLIENT_ID وGOOGLE_CLIENT_SECRET غير معيّنين')
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(DRIVE_SCOPES),
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        }
        from urllib.parse import urlencode
        return f'{GOOGLE_AUTH_URL}?{urlencode(params)}'

    def exchange_code(self, code):
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.redirect_uri,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def refresh_access_token(self, refresh_token):
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def save_tokens(self, token_dict):
        token, _ = GoogleDriveToken.objects.get_or_create(pk=1)
        token.set_tokens(token_dict)
        token.save()
        return token

    def get_credentials(self):
        token = GoogleDriveToken.objects.filter(pk=1).first()
        if not token:
            return None
        data = token.get_tokens()
        if not data.get('refresh_token') and not data.get('access_token'):
            return None
        if token.token_expiry and token.token_expiry <= timezone.now() and data.get('refresh_token'):
            try:
                refreshed = self.refresh_access_token(data['refresh_token'])
            except Exception:
                return data
            data.update(refreshed)
            token.set_tokens(data)
            token.save()
        return data

    def is_connected(self):
        token = GoogleDriveToken.objects.filter(pk=1).first()
        return bool(token and token.get_tokens().get('refresh_token'))

    def upload_file(self, *args, **kwargs):
        raise NotImplementedError('upload_file سيُنفَّذ في مرحلة رفع الملفات')

    def delete_file(self, *args, **kwargs):
        raise NotImplementedError('delete_file سيُنفَّذ في مرحلة رفع الملفات')

    def get_file(self, *args, **kwargs):
        raise NotImplementedError('get_file سيُنفَّذ في مرحلة رفع الملفات')

    def create_folder(self, *args, **kwargs):
        raise NotImplementedError('create_folder سيُنفَّذ في مرحلة رفع الملفات')

    def get_file_url(self, *args, **kwargs):
        raise NotImplementedError('get_file_url سيُنفَّذ في مرحلة رفع الملفات')
