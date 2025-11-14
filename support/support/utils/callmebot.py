# support/utils/callmebot.py
import requests
import logging
logger = logging.getLogger(__name__)

CALLMEBOT_API = "https://api.callmebot.com/whatsapp.php"

def send_whatsapp_free(to: str, text: str, apikey: str) -> bool:
    """
    Envoi gratuit via CallMeBot
    to : +242066950364
    text : 500 car max
    apikey : clé reçue à l’étape 1
    """
    if not to.startswith("+"):
        to = "+" + to
    params = {"phone": to, "text": text, "apikey": apikey}
    try:
        r = requests.get(CALLMEBOT_API, params=params, timeout=10)
        r.raise_for_status()
        logger.info("CallMeBot OK : %s", r.text)
        return True
    except Exception as e:
        logger.error("CallMeBot error : %s", e)
        return False