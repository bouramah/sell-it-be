from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/kfstore"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    # "nimba" (fournisseur retenu, cf. app/services/sms.py) ou "console" (par défaut,
    # journalise sans envoyer — utilisé tant que SMS_API_KEY/SMS_API_SECRET ne sont pas
    # renseignés). SMS_API_KEY = ACCOUNT_SID Nimba, SMS_API_SECRET = AUTH_TOKEN Nimba,
    # SMS_SENDER_ID = nom d'expéditeur validé sur le compte Nimba.
    sms_provider: str = "nimba"
    sms_api_key: str = ""
    sms_api_secret: str = ""
    sms_sender_id: str = "KFSTORE"


settings = Settings()
