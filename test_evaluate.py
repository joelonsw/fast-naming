#!/usr/bin/env python3
"""
Test script for POST /evaluate API
"""

import requests
import json
import sys

def test_evaluate_api(result_number: int):
    """Test the POST /evaluate API with a given result number."""
    
    url = "http://localhost:8000/evaluate"
    
    # Prepare request data
    data = {
        "result_number": result_number
    }
    
    print(f"🎯 Testing POST /evaluate API with result_number={result_number}")
    print(f"📡 URL: {url}")
    print(f"📝 Request data: {json.dumps(data, ensure_ascii=False, indent=2)}")
    print("-" * 50)
    
    try:
        # Make API call
        response = requests.post(url, json=data)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API call successful!")
            print(f"📋 Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            # Show summary
            if result.get('success'):
                print("\n📈 Summary:")
                print(f"   - Score file: {result.get('score_file')}")
                print(f"   - Total submissions: {result.get('total_submissions')}")
                print(f"   - Evaluation criteria: {result.get('evaluation_criteria')}")
                
                # Check if score file was created
                score_file = result.get('score_file')
                if score_file and score_file.startswith('result/score'):
                    print(f"\n✅ Score file created: {score_file}")
                else:
                    print(f"\n⚠️ Score file path: {score_file}")
            else:
                print(f"❌ API returned success=False: {result.get('message')}")
                
        else:
            print(f"❌ API call failed with status {response.status_code}")
            try:
                error_detail = response.json()
                print(f"📝 Error detail: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
            except:
                print(f"📝 Error text: {response.text}")
                
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def main():
    """Main function to run the test."""
    
    if len(sys.argv) != 2:
        print("Usage: python test_evaluate.py <result_number>")
        print("Example: python test_evaluate.py 1")
        sys.exit(1)
    
    try:
        result_number = int(sys.argv[1])
        test_evaluate_api(result_number)
    except ValueError:
        print("❌ Error: result_number must be an integer")
        sys.exit(1)

if __name__ == "__main__":
    main()
