# app/oauth_client.py
from authlib.integrations.flask_client import OAuth

oauth = OAuth()

def init_oauth(app):
    oauth.init_app(app)

    # Google (OIDC)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # Naver (OAuth2)
    oauth.register(
        name='naver',
        client_id=app.config['NAVER_CLIENT_ID'],
        client_secret=app.config['NAVER_CLIENT_SECRET'],
        authorize_url='https://nid.naver.com/oauth2.0/authorize',
        access_token_url='https://nid.naver.com/oauth2.0/token',
        api_base_url='https://openapi.naver.com/v1/nid/',
        client_kwargs={'scope': 'name email profile_image'}
    )
