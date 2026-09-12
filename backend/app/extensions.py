from supabase import Client, create_client

from app.config import Config

# Singleton, service-role client — same convention as Alethia. This is the
# only writer to listings/sellers/matches/notification_log; the RN client
# reads via the anon key under RLS instead.
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
