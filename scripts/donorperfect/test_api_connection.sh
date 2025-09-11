#!/bin/bash

# test script to verify donoperfect api connection
# requires environment variables: DP_API_URL and DP_API_KEY

# check if required environment variables are set
if [ -z "$DP_API_URL" ] || [ -z "$DP_API_KEY" ]; then
    echo "error: required environment variables not set"
    echo "please set DP_API_URL and DP_API_KEY"
    exit 1
fi

echo "testing donoperfect api connection..."
echo "api url: $DP_API_URL"
echo "api key: ${DP_API_KEY:0:10}..." # show only first 10 chars for security

# make a simple test call to get a few donor records
curl -s "${DP_API_URL}?apikey=${DP_API_KEY}&action=dp_donorsearch&params=@donor_id=null,@last_name=null,@first_name=null,@opt_line=null,@address=null,@city=null,@state=null,@zip=null,@country=null,@filter_id=null,@user_id=null" \
  -o "test_response.xml"

# check if api call was successful
if [ $? -ne 0 ]; then
    echo "error: api call failed"
    exit 1
fi

# check if we got valid xml response
if grep -q "<result>" test_response.xml; then
    echo "✓ api connection successful"
    echo "response preview:"
    head -20 test_response.xml
    echo "..."
    echo "total records found: $(grep -c '<record>' test_response.xml)"
else
    echo "✗ api connection failed"
    echo "response content:"
    cat test_response.xml
    exit 1
fi

# clean up
rm test_response.xml
