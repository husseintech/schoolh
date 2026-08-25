import os
import json

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

    def _auth_headers(self):
        creds = self.get_credentials()
        if not creds or not creds.get('access_token'):
            raise RuntimeError('Google Drive غير متصل. يجب على المدير ربط الحساب أولاً')
        return {'Authorization': f'Bearer {creds["access_token"]}'}

    def _find_folder(self, name, parent_id):
        q = "mimeType='application/vnd.google-apps.folder' and name=%s and '%s' in parents and trashed=false" % (repr(name), parent_id)
        resp = requests.get(
            'https://www.googleapis.com/drive/v3/files',
            headers=self._auth_headers(),
            params={'q': q, 'fields': 'files(id,name)', 'pageSize': '1'},
            timeout=30,
        )
        resp.raise_for_status()
        files = resp.json().get('files', [])
        return files[0]['id'] if files else None

    def _build_folder(self, name, parent_id):
        existing = self._find_folder(name, parent_id)
        if existing:
            return existing
        meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        resp = requests.post(
            'https://www.googleapis.com/drive/v3/files',
            headers=self._auth_headers(),
            json=meta,
            params={'fields': 'id'},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()['id']

    def ensure_lesson_folder(self, class_name, subject_name, lesson_title):
        parent = self.root_folder_id
        if not parent:
            return None
        parent = self._build_folder(class_name or 'بدون صف', parent)
        parent = self._build_folder(subject_name or 'بدون مادة', parent)
        parent = self._build_folder(lesson_title or 'بدون درس', parent)
        return parent

    def upload_file(self, filename, data, mimetype, class_name=None, subject_name=None, lesson_title=None):
        parent = self.ensure_lesson_folder(class_name, subject_name, lesson_title) or self.root_folder_id
        metadata = {'name': filename}
        if parent:
            metadata['parents'] = [parent]
        boundary = '----schoolh_drive_boundary'
        head = (
            f'--{boundary}\r\n'
            f'Content-Type: application/json; charset=UTF-8\r\n\r\n'
            f'{json.dumps(metadata)}\r\n'
            f'--{boundary}\r\n'
            f'Content-Type: {mimetype}\r\n\r\n'
        ).encode('utf-8')
        tail = f'\r\n--{boundary}--\r\n'.encode('utf-8')
        payload = head + data + tail
        headers = self._auth_headers()
        headers['Content-Type'] = f'multipart/related; boundary={boundary}'
        resp = requests.post(
            'https://www.googleapis.com/upload/drive/v3/files',
            params={'uploadType': 'multipart', 'fields': 'id,webViewLink,name,mimeType,size'},
            headers=headers,
            data=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_file(self, file_id):
        resp = requests.delete(
            f'https://www.googleapis.com/drive/v3/files/{file_id}',
            headers=self._auth_headers(),
            timeout=30,
        )
        if resp.status_code not in (204, 200):
            resp.raise_for_status()
        return True

    def get_file(self, file_id):
        resp = requests.get(
            f'https://www.googleapis.com/drive/v3/files/{file_id}',
            headers=self._auth_headers(),
            params={'fields': 'id,name,mimeType,size,webViewLink'},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def download_file(self, file_id):
        meta = self.get_file(file_id)
        resp = requests.get(
            f'https://www.googleapis.com/drive/v3/files/{file_id}',
            headers=self._auth_headers(),
            params={'alt': 'media'},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.content, meta.get('mimeType', 'application/octet-stream'), meta.get('name', 'file')
