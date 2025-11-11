"""
Quick Setup Script for Voice AI Dashboard

Run this AFTER activating your virtual environment:
  cd C:\Projects\HolidayBrandAI
  venv\Scripts\activate     (Windows)
  source venv/bin/activate  (Mac/Linux)
  python setup_dashboard.py
"""

import sys

print("\n" + "="*70)
print(" Voice AI Dashboard - Quick Setup")
print("="*70 + "\n")

print("This script will set up the multi-location token system for the dashboard.\n")

# Step 1: Create database table
print("Step 1: Creating database table...")
print("-" * 70)

try:
    from utils.multi_location_tokens import create_multi_token_table
    create_multi_token_table()
    print("✅ Database table created successfully!\n")
except ImportError as e:
    print(f"❌ Import Error: {e}\n")
    print("Please activate your virtual environment first:")
    print("  venv\\Scripts\\activate     (Windows)")
    print("  source venv/bin/activate  (Mac/Linux)\n")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error creating database table: {e}\n")
    print("Please ensure:")
    print("  1. Your database credentials are correct in config/config.py")
    print("  2. Your database is running")
    print("  3. You have mysql-connector-python installed: pip install mysql-connector-python")
    sys.exit(1)

# Step 2: Instructions
print("Step 2: Start the backend API")
print("-" * 70)
print("Run this command in a terminal:")
print("  cd C:\\Projects\\HolidayBrandAI")
print("  uvicorn main:app --reload")
print("")
print("The API will be available at: http://localhost:8000")
print("API docs will be at: http://localhost:8000/docs\n")

print("Step 3: Start the frontend dashboard")
print("-" * 70)
print("Run this command in another terminal:")
print("  cd C:\\Projects\\HolidayBrandAIDashboard")
print("  npm run dev")
print("")
print("The dashboard will be available at: http://localhost:3000\n")

print("Step 4: Authorize locations")
print("-" * 70)
print("1. Open the dashboard at http://localhost:3000")
print("2. Navigate to Voice AI Management")
print("3. Click on the '🔐 Manage Locations' tab")
print("4. Click 'Authorize New Location'")
print("5. Complete the OAuth flow for each location\n")

print("="*70)
print(" Setup Complete! 🎉")
print("="*70)
print("\nRead the full guide:")
print("  C:\\Projects\\HolidayBrandAIDashboard\\VOICE_AI_DASHBOARD_GUIDE.md\n")

