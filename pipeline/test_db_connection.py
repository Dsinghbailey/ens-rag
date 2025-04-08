import os
from dotenv import load_dotenv
import logging
from sqlalchemy import create_engine, text, make_url
from sqlalchemy.exc import SQLAlchemyError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
db_conn_string = os.environ.get("DATABASE_URL")

if not db_conn_string:
    logging.error("DATABASE_URL environment variable not set.")
    exit(1)

# Parse the database URL
db_url = make_url(db_conn_string)
logging.info(f"Testing connection to database with connection string: {db_conn_string}")

try:
    # Create engine
    engine = create_engine(db_conn_string)

    # Test connection
    with engine.connect() as connection:
        # Execute a simple query
        result = connection.execute(text("SELECT 1"))
        row = result.fetchone()

        if row and row[0] == 1:
            logging.info("✅ Database connection successful!")

            # Check if pgvector extension is enabled
            try:
                result = connection.execute(
                    text("SELECT * FROM pg_extension WHERE extname = 'vector'")
                )
                if result.fetchone():
                    logging.info("✅ pgvector extension is installed.")
                else:
                    logging.warning(
                        "❌ pgvector extension is NOT installed. Run: CREATE EXTENSION vector;"
                    )
            except SQLAlchemyError as e:
                logging.warning(f"Could not check pgvector extension: {e}")

            # Check if the target table exists
            try:
                table_name = "processed_chunks_llamaindex"
                schema_name = "public"
                result = connection.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        f"WHERE table_schema = '{schema_name}' AND table_name = '{table_name}')"
                    )
                )
                if result.fetchone()[0]:
                    logging.info(f"✅ Table {schema_name}.{table_name} exists.")
                else:
                    logging.info(
                        f"❌ Table {schema_name}.{table_name} does not exist yet (will be created during ingestion)."
                    )
            except SQLAlchemyError as e:
                logging.warning(f"Could not check if table exists: {e}")

except SQLAlchemyError as e:
    logging.error(f"❌ Database connection failed: {e}")
    exit(1)
