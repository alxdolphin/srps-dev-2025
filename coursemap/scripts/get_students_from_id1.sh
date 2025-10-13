#!/bin/bash

# students run philly api - get students starting from id 1
# simple script to get student information starting from id 1

API_TOKEN="${COURSEMAP_API_TOKEN}"
BASE_URL="${COURSEMAP_API_URL}"

echo "Students Run Philly - Students from ID 1"
echo "======================================="
echo ""

# function to get student info by id
get_student_info() {
    local student_id="$1"
    echo "🔍 student id: $student_id"
    
    # get the student data
    local student_data=$(curl -s "$BASE_URL/students/all?api_token=$API_TOKEN" -H "Accept: application/json" | jq ".data.students[] | select(.id == $student_id)")
    
    if [ "$student_data" = "null" ] || [ -z "$student_data" ]; then
        echo "   ❌ student id $student_id not found"
    else
        echo "   ✅ found: $(echo "$student_data" | jq -r '.first_name') $(echo "$student_data" | jq -r '.last_name')"
        echo "   email: $(echo "$student_data" | jq -r '.email')"
        echo "   team id: $(echo "$student_data" | jq -r '.team_id')"
        echo "   school: $(echo "$student_data" | jq -r '.school')"
        echo "   grade: $(echo "$student_data" | jq -r '.grade')"
        echo "   active: $(echo "$student_data" | jq -r '.active')"
    fi
    echo ""
}

# get students starting from id 1
echo "getting students starting from id 1..."
echo ""

# try to get students 1-20
for id in {1..20}; do
    get_student_info "$id"
done

echo "✅ student lookup complete!"
