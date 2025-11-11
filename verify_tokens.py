"""
Quick script to verify tokens are in the database
"""
import mysql.connector
from config.config import DBHOST, DBUSERNAME, DBPASSWORD, DATABASENAME

db_config = {
    "host": DBHOST,
    "user": DBUSERNAME,
    "password": DBPASSWORD,
    "database": DATABASENAME,
    "port": 3306
}

print("\n" + "="*70)
print(" Token Database Verification")
print("="*70)

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM tokens WHERE id = 1")
    row = cursor.fetchone()
    
    if row:
        print("\n✅ Token found in database!")
        print(f"\n   ID: {row['id']}")
        print(f"   Access Token: {row['access_token'][:30]}... (truncated)")
        print(f"   Refresh Token: {row['refresh_token'][:30]}... (truncated)")
        print(f"   Expires In: {row['expire_in']} seconds")
        print(f"   Created At: {row['created_at']}")
        
        # Check if it's expired
        from datetime import datetime, timedelta
        created_at = row['created_at']
        expire_in = row['expire_in']
        expiry_time = created_at + timedelta(seconds=expire_in)
        now = datetime.now()
        
        if now < expiry_time:
            time_left = expiry_time - now
            print(f"\n   ✅ Token is VALID (expires in {time_left})")
        else:
            print(f"\n   ⚠️  Token is EXPIRED")
            print(f"   (Don't worry, it will auto-refresh when used)")
    else:
        print("\n❌ No token found in database!")
        print("\n   Run: python reauthorize_oauth.py")
    
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")

