from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (must load env before importing app/config)
from app.config import Config  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
