"""
Helper: prints the TG_SECRET_HASH value for a given password.
Usage: python hash_password.py <your_password>
"""
import sys
sys.path.insert(0, ".")
from Utils.cardinal_tools import hash_password

if len(sys.argv) < 2:
    print("Usage: python hash_password.py <your_password>")
    sys.exit(1)

password = sys.argv[1]
if (len(password) < 8 or password.lower() == password or
        password.upper() == password or not any(c.isdigit() for c in password)):
    print("Weak password! Must be 8+ chars with uppercase, lowercase, and a digit.")
    sys.exit(1)

print(f"TG_SECRET_HASH={hash_password(password)}")
