#!/usr/bin/env python3
"""
Database Verification Script

Quick verification tool to check that the database was properly populated
and all systems are working correctly.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from dotenv import load_dotenv
load_dotenv()

import requests
import json

def verify_api_health():
    """Verify API is responding"""
    try:
        response = requests.get("http://localhost:8000/api/v1/health/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Health: {data['status']}")
            return True
        else:
            print(f"❌ API Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API not accessible: {e}")
        return False

def verify_database_stats():
    """Verify database has been populated"""
    try:
        response = requests.get("http://localhost:8000/api/v1/cases/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Database Stats:")
            print(f"   Cases: {stats.get('total_cases', 0)}")
            print(f"   Chunks: {stats.get('total_chunks', 0)}")
            print(f"   Words: {stats.get('total_words', 0)}")
            print(f"   Embeddings: {stats.get('total_embeddings', 0)}")
            return stats.get('total_cases', 0) > 0
        else:
            print(f"❌ Database stats failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Database stats not accessible: {e}")
        return False

def verify_search_functionality():
    """Verify search is working"""
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/cases/search/phrase",
            params={"query": "property", "limit": 1},
            timeout=5
        )
        if response.status_code == 200:
            results = response.json()
            if results:
                print(f"✅ Search working: Found {len(results)} result(s)")
                return True
            else:
                print("⚠️  Search working but no results found")
                return True
        else:
            print(f"❌ Search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Search not accessible: {e}")
        return False

def main():
    """Main verification function"""
    print("🔍 Legal AI System Verification")
    print("==============================")
    
    all_good = True
    
    # Test API health
    all_good &= verify_api_health()
    
    # Test database population
    all_good &= verify_database_stats()
    
    # Test search functionality  
    all_good &= verify_search_functionality()
    
    if all_good:
        print("\n🎉 All systems verified and working!")
        print("📖 Visit http://localhost:8000/docs for API documentation")
    else:
        print("\n⚠️  Some issues detected - check logs above")
        sys.exit(1)

if __name__ == "__main__":
    main()