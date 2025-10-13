#!/bin/bash

# Students Run Philly API - Complete Curl Commands
# Generated from API discovery session
# Framework: Laravel (PHP)
# API Token: sourced from .envrc via COURSEMAP_API_TOKEN

API_TOKEN="${COURSEMAP_API_TOKEN}"
BASE_URL="${COURSEMAP_API_URL}"

echo "Students Run Philly API - Curl Commands"
echo "======================================="
echo ""

# Function to make API calls and show results
make_api_call() {
    local endpoint="$1"
    local description="$2"
    local method="${3:-GET}"
    
    echo "🔗 $description"
    echo "   Endpoint: $method $BASE_URL$endpoint"
    echo "   Command:"
    echo "   curl -s \"$BASE_URL$endpoint?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
    echo ""
    
    # Actually make the call and show result
    echo "   Response:"
    if [ "$method" = "GET" ]; then
        curl -s "$BASE_URL$endpoint?api_token=$API_TOKEN" -H "Accept: application/json" | jq . | head -20
    else
        curl -s -X "$method" "$BASE_URL$endpoint?api_token=$API_TOKEN" -H "Accept: application/json" | jq . | head -20
    fi
    echo ""
    echo "   ---"
    echo ""
}

# 1. User Management Endpoints
echo "1. USER MANAGEMENT ENDPOINTS"
echo "============================"
make_api_call "/users/get-my-students-users" "Get My Users and My Students Lists"
make_api_call "/users/all" "Get All Users"

# 2. Student Management Endpoints
echo "2. STUDENT MANAGEMENT ENDPOINTS"
echo "==============================="
make_api_call "/students/all" "Get All Students"
make_api_call "/students/miles" "Get All Students Miles"

# 3. Team Management Endpoints
echo "3. TEAM MANAGEMENT ENDPOINTS"
echo "============================"
make_api_call "/teams/all" "Get All Teams"

# 4. File Management Endpoints
echo "4. FILE MANAGEMENT ENDPOINTS"
echo "============================"
make_api_call "/uploads/all" "Get All Uploads"

# 5. Waiver Management Endpoints
echo "5. WAIVER MANAGEMENT ENDPOINTS"
echo "=============================="
make_api_call "/waivers/all" "Get All Waivers"

# Additional curl commands for specific use cases
echo "6. ADDITIONAL CURL COMMANDS"
echo "==========================="
echo ""

echo "🔗 Get specific student data (example with student ID 8029)"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.students[] | select(.id == 8029)'"
echo ""

echo "🔗 Get students from specific team (example with team ID 153)"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.students[] | select(.team_id == 153)'"
echo ""

echo "🔗 Get only student names and emails"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.students[] | {id, first_name, last_name, email}'"
echo ""

echo "🔗 Get team information with student count"
echo "   curl -s \"$BASE_URL/teams/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.teams[] | {id, name, school: .affiliate_school}'"
echo ""

echo "🔗 Get waiver information"
echo "   curl -s \"$BASE_URL/waivers/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.waivers[] | {id, name, assign_to}'"
echo ""

echo "🔗 Get upload information"
echo "   curl -s \"$BASE_URL/uploads/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.uploads[] | {id, title, file_type, created_at}'"
echo ""

echo "🔗 Get user information with roles"
echo "   curl -s \"$BASE_URL/users/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data.users[] | {id, first_name, last_name, email, role_id}'"
echo ""

echo "🔗 Get mileage data for students"
echo "   curl -s \"$BASE_URL/students/miles?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data'"
echo ""

# Laravel-specific patterns and write operations
echo "7. LARAVEL-SPECIFIC PATTERNS & WRITE OPERATIONS"
echo "==============================================="
echo ""

echo "🔗 Laravel Resource Routes (RESTful patterns)"
echo "   # These follow Laravel's resource routing conventions:"
echo "   # GET    /students        -> index (list all)"
echo "   # GET    /students/{id}   -> show (get specific)"
echo "   # POST   /students        -> store (create new)"
echo "   # PUT    /students/{id}   -> update (update specific)"
echo "   # DELETE /students/{id}   -> destroy (delete specific)"
echo ""

echo "🔗 Try Laravel resource routes (may not be implemented)"
echo "   curl -s \"$BASE_URL/students?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/8029?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/teams?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/teams/153?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Laravel API Resource patterns (with data wrapping)"
echo "   # Laravel often wraps responses in 'data' key"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq '.data'"
echo ""

echo "🔗 Laravel pagination (if implemented)"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&page=1&per_page=10\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Laravel filtering (if implemented)"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&filter[team_id]=153\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&search=John\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Laravel sorting (if implemented)"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&sort=first_name&order=asc\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Create new student (Laravel POST pattern)"
echo "   curl -s -X POST \"$BASE_URL/students?api_token=$API_TOKEN\" \\"
echo "     -H \"Accept: application/json\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -H \"X-Requested-With: XMLHttpRequest\" \\"
echo "     -d '{\"first_name\": \"John\", \"last_name\": \"Doe\", \"email\": \"john@example.com\", \"team_id\": 153}'"
echo ""

echo "🔗 Update student (Laravel PUT pattern)"
echo "   curl -s -X PUT \"$BASE_URL/students/8029?api_token=$API_TOKEN\" \\"
echo "     -H \"Accept: application/json\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -H \"X-Requested-With: XMLHttpRequest\" \\"
echo "     -d '{\"first_name\": \"Updated Name\"}'"
echo ""

echo "🔗 Delete student (Laravel DELETE pattern)"
echo "   curl -s -X DELETE \"$BASE_URL/students/8029?api_token=$API_TOKEN\" \\"
echo "     -H \"Accept: application/json\" \\"
echo "     -H \"X-Requested-With: XMLHttpRequest\""
echo ""

echo "🔗 Laravel form data (alternative to JSON)"
echo "   curl -s -X POST \"$BASE_URL/students?api_token=$API_TOKEN\" \\"
echo "     -H \"Accept: application/json\" \\"
echo "     -H \"X-Requested-With: XMLHttpRequest\" \\"
echo "     -d \"first_name=John&last_name=Doe&email=john@example.com&team_id=153\""
echo ""

# Environment setup
echo "8. ENVIRONMENT SETUP"
echo "===================="
echo ""

echo "🔗 Set environment variables for easier use"
echo "   export SRPS_API_TOKEN=\"$API_TOKEN\""
echo "   export SRPS_API_URL=\"$BASE_URL\""
echo ""

echo "🔗 Using environment variables"
echo "   curl -s \"\$SRPS_API_URL/students/all?api_token=\$SRPS_API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

# Error handling examples
echo "9. ERROR HANDLING EXAMPLES"
echo "=========================="
echo ""

echo "🔗 Check API status"
echo "   curl -s -w \"HTTP Status: %{http_code}\\n\" \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Handle errors gracefully"
echo "   response=\$(curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\")"
echo "   if echo \"\$response\" | jq -e '.status == \"success\"' > /dev/null; then"
echo "     echo \"API call successful\""
echo "     echo \"\$response\" | jq ."
echo "   else"
echo "     echo \"API call failed\""
echo "     echo \"\$response\" | jq ."
echo "   fi"
echo ""

echo "10. LARAVEL API INSIGHTS & DEBUGGING"
echo "===================================="
echo ""

echo "🔗 Laravel API Resource Structure"
echo "   # Laravel APIs typically return:"
echo "   # {"
echo "   #   \"status\": \"success\","
echo "   #   \"message\": \"Description\","
echo "   #   \"data\": { ... }"
echo "   # }"
echo ""

echo "🔗 Laravel validation errors (if POST/PUT fails)"
echo "   # Laravel returns validation errors in this format:"
echo "   # {"
echo "   #   \"status\": \"failed\","
echo "   #   \"message\": \"Validation failed\","
echo "   #   \"data\": {"
echo "   #     \"errors\": {"
echo "   #       \"field_name\": [\"Error message\"]"
echo "   #     }"
echo "   #   }"
echo "   # }"
echo ""

echo "🔗 Laravel CSRF protection (if enabled)"
echo "   # Some Laravel APIs require CSRF tokens:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN\" \\"
echo "     -H \"Accept: application/json\" \\"
echo "     -H \"X-CSRF-TOKEN: your_csrf_token_here\""
echo ""

echo "🔗 Laravel rate limiting (if enabled)"
echo "   # Laravel may have rate limits, check headers:"
echo "   curl -s -I \"$BASE_URL/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\""
echo ""

echo "🔗 Laravel API versioning"
echo "   # The API uses /api/v2/ - try other versions:"
echo "   curl -s \"https://api.studentsrunphilly.org/api/v1/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"https://api.studentsrunphilly.org/api/students/all?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

echo "11. BATCH OPERATIONS"
echo "===================="
echo ""

echo "🔗 Get all data in one script"
echo "   #!/bin/bash"
echo "   API_TOKEN=\"$API_TOKEN\""
echo "   BASE_URL=\"$BASE_URL\""
echo "   "
echo "   echo \"Fetching all Students Run Philly data...\""
echo "   "
echo "   echo \"Students:\" > srps_data.json"
echo "   curl -s \"\$BASE_URL/students/all?api_token=\$API_TOKEN\" -H \"Accept: application/json\" >> srps_data.json"
echo "   "
echo "   echo \"Teams:\" >> srps_data.json"
echo "   curl -s \"\$BASE_URL/teams/all?api_token=\$API_TOKEN\" -H \"Accept: application/json\" >> srps_data.json"
echo "   "
echo "   echo \"Users:\" >> srps_data.json"
echo "   curl -s \"\$BASE_URL/users/all?api_token=\$API_TOKEN\" -H \"Accept: application/json\" >> srps_data.json"
echo "   "
echo "   echo \"Data saved to srps_data.json\""
echo ""

echo "12. LARAVEL ROUTE DISCOVERY"
echo "==========================="
echo ""

echo "🔗 Try common Laravel API patterns"
echo "   # These are common Laravel API route patterns:"
echo "   curl -s \"$BASE_URL/api/students?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/api/teams?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/api/users?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Laravel API documentation endpoints (if available)"
echo "   curl -s \"$BASE_URL/api/documentation?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/api/routes?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/api/endpoints?api_token=$API_TOKEN\" -H \"Accept: application/json\" | jq ."
echo ""

echo "13. DISCOVERED API CAPABILITIES"
echo "==============================="
echo ""

echo "🔗 Pagination Support"
echo "   # The API supports Laravel-style pagination:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&page=1&per_page=10\" -H \"Accept: application/json\" | jq ."
echo "   # Returns paginated data with: current_page, data, from, last_page, next_page_url, per_page, prev_page_url, to, total"
echo ""

echo "🔗 Sorting Support"
echo "   # Sort by any field:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&sort=first_name&order=asc\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&sort=last_name&order=desc\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&sort=created_at&order=desc\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Search Support"
echo "   # Search functionality:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&search=John\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&search=Smith\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Field Selection Support"
echo "   # Select specific fields (note: may not be fully implemented):"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&fields=id,first_name,last_name,email\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Relationship Loading Support"
echo "   # Load relationships:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&include=team\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&with=team,waivers\" -H \"Accept: application/json\" | jq ."
echo ""

echo "🔗 Limit and Offset Support"
echo "   # Limit results:"
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&limit=5\" -H \"Accept: application/json\" | jq ."
echo "   curl -s \"$BASE_URL/students/all?api_token=$API_TOKEN&offset=10&limit=5\" -H \"Accept: application/json\" | jq ."
echo ""

echo "14. COMPLETE API SUMMARY"
echo "========================"
echo ""

echo "✅ WORKING ENDPOINTS (7 total):"
echo "   1. GET /api/v2/users/get-my-students-users"
echo "   2. GET /api/v2/students/all"
echo "   3. GET /api/v2/teams/all"
echo "   4. GET /api/v2/uploads/all"
echo "   5. GET /api/v2/waivers/all"
echo "   6. GET /api/v2/users/all"
echo "   7. GET /api/v2/students/miles"
echo ""

echo "✅ SUPPORTED PARAMETERS:"
echo "   • page, per_page (pagination)"
echo "   • sort, order (sorting)"
echo "   • search (searching)"
echo "   • include, with (relationships)"
echo "   • fields (field selection)"
echo "   • limit, offset (limiting)"
echo ""

echo "✅ LARAVEL FEATURES:"
echo "   • Laravel pagination with metadata"
echo "   • Laravel-style query parameters"
echo "   • JSON API responses with status/message/data structure"
echo "   • Token-based authentication"
echo "   • CORS support"
echo ""

echo "❌ NOT SUPPORTED:"
echo "   • Standard REST resource routes (/students, /students/{id})"
echo "   • POST/PUT/DELETE operations (read-only API)"
echo "   • Individual resource access (/students/1)"
echo "   • Authentication endpoints (/auth/login)"
echo "   • Admin endpoints (/admin/*)"
echo "   • System endpoints (/system/*)"
echo ""

echo "=========================================="
echo "Students Run Philly API Curl Commands Complete"
echo "=========================================="
