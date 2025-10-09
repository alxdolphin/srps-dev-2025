#!/bin/bash

# students run philly api - get student information by id (fixed)
# this script gets student information starting from id 1

API_TOKEN="${COURSEMAP_API_TOKEN}"
BASE_URL="${COURSEMAP_API_URL}"

echo "Students Run Philly - Student Information Lookup (Fixed)"
echo "======================================================="
echo ""

# check the actual data structure first
echo "🔍 checking data structure..."
first_student=$(curl -s "$BASE_URL/students/all?api_token=$API_TOKEN" -H "Accept: application/json" | jq '.data.students.data[0]')
echo "   first student data:"
echo "$first_student" | jq '.' | head -10
echo ""

# function to get student info by id
get_student_info() {
    local student_id="$1"
    echo "🔍 looking up student id: $student_id"
    
    # get the student data from the correct path
    local student_data=$(curl -s "$BASE_URL/students/all?api_token=$API_TOKEN" -H "Accept: application/json" | jq ".data.students.data[] | select(.id == $student_id)")
    
    if [ "$student_data" = "null" ] || [ -z "$student_data" ]; then
        echo "   ❌ student id $student_id not found"
    else
        echo "   ✅ student found:"
        echo "$student_data" | jq '.'
    fi
    echo ""
}

# function to get student summary by id
get_student_summary() {
    local student_id="$1"
    echo "📋 student id $student_id summary:"
    
    local student_data=$(curl -s "$BASE_URL/students/all?api_token=$API_TOKEN" -H "Accept: application/json" | jq ".data.students.data[] | select(.id == $student_id)")
    
    if [ "$student_data" = "null" ] || [ -z "$student_data" ]; then
        echo "   ❌ student id $student_id not found"
    else
        echo "   name: $(echo "$student_data" | jq -r '.first_name') $(echo "$student_data" | jq -r '.last_name')"
        echo "   email: $(echo "$student_data" | jq -r '.email')"
        echo "   phone: $(echo "$student_data" | jq -r '.phone')"
        echo "   team id: $(echo "$student_data" | jq -r '.team_id')"
        echo "   school: $(echo "$student_data" | jq -r '.school')"
        echo "   grade: $(echo "$student_data" | jq -r '.grade')"
        echo "   active: $(echo "$student_data" | jq -r '.active')"
        echo "   created: $(echo "$student_data" | jq -r '.created_at')"
    fi
    echo ""
}

# get students starting from id 1
echo "getting students starting from id 1..."
echo ""

# try to get students 1-10
for id in {1..10}; do
    get_student_summary "$id"
done

echo "✅ student lookup complete!"
