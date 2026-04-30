
import os
from dotenv import load_dotenv
load_dotenv()
print(f"SECRET_KEY: [{os.getenv('SECRET_KEY')}]")
print(f"ALGORITHM: [{os.getenv('ALGORITHM')}]")
