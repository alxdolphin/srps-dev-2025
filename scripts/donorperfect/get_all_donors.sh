#!/bin/bash

# simple script to pull all donor records from donoperfect api and save to csv
# uses dynamic select query for better reliability and performance
# requires environment variables: DP_API_URL and DP_API_KEY

# check if required environment variables are set
if [ -z "$DP_API_URL" ] || [ -z "$DP_API_KEY" ]; then
    echo "error: required environment variables not set"
    echo "please set DP_API_URL and DP_API_KEY"
    exit 1
fi

# output file
output_file="donors_$(date +%Y%m%d_%H%M%S).csv"

# create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "fetching all donor records..."
echo "output will be saved to: $OUTPUT_DIR/$output_file"

# make api call to get all donors using dynamic select query
# URL encode the SQL query - comprehensive field list from dp_savedonor parameters
sql_query="SELECT donor_id, first_name, last_name, middle_name, suffix, title, salutation, prof_title, opt_line, address, address2, city, state, zip, country, address_type, home_phone, business_phone, fax_phone, mobile_phone, email, org_rec, donor_type, nomail, nomail_reason, narrative, donor_rcpt_type FROM dp"
encoded_sql=$(printf '%s\n' "$sql_query" | sed 's/ /%20/g; s/,/%2C/g')

curl -s "${DP_API_URL}?apikey=${DP_API_KEY}&action=${encoded_sql}" \
  -o "donors_raw.xml"

# check if api call was successful
if [ $? -ne 0 ]; then
    echo "error: api call failed"
    exit 1
fi

# check if we got valid xml response
if ! grep -q "<result>" donors_raw.xml; then
    echo "error: invalid response from api"
    echo "response content:"
    cat donors_raw.xml
    exit 1
fi

echo "api call successful, processing response..."

# convert xml to csv using simple text processing
# extract field values and create csv header with comprehensive field list
echo "donor_id,first_name,last_name,middle_name,suffix,title,salutation,prof_title,opt_line,address,address2,city,state,zip,country,address_type,home_phone,business_phone,fax_phone,mobile_phone,email,org_rec,donor_type,nomail,nomail_reason,narrative,donor_rcpt_type" > "$OUTPUT_DIR/$output_file"

# extract each record and convert to csv using a simpler approach
# split records by </record><record> and process each one
sed 's/<\/record><record>/<\/record>\n<record>/g' donors_raw.xml | \
grep '<record>' | \
while read -r record; do
    # extract field values from each record using single quotes (as used in the XML)
    donor_id=$(echo "$record" | sed -n "s/.*name='donor_id'[^>]*value='\([^']*\)'.*/\1/p")
    first_name=$(echo "$record" | sed -n "s/.*name='first_name'[^>]*value='\([^']*\)'.*/\1/p")
    last_name=$(echo "$record" | sed -n "s/.*name='last_name'[^>]*value='\([^']*\)'.*/\1/p")
    middle_name=$(echo "$record" | sed -n "s/.*name='middle_name'[^>]*value='\([^']*\)'.*/\1/p")
    suffix=$(echo "$record" | sed -n "s/.*name='suffix'[^>]*value='\([^']*\)'.*/\1/p")
    title=$(echo "$record" | sed -n "s/.*name='title'[^>]*value='\([^']*\)'.*/\1/p")
    salutation=$(echo "$record" | sed -n "s/.*name='salutation'[^>]*value='\([^']*\)'.*/\1/p")
    prof_title=$(echo "$record" | sed -n "s/.*name='prof_title'[^>]*value='\([^']*\)'.*/\1/p")
    opt_line=$(echo "$record" | sed -n "s/.*name='opt_line'[^>]*value='\([^']*\)'.*/\1/p")
    address=$(echo "$record" | sed -n "s/.*name='address'[^>]*value='\([^']*\)'.*/\1/p")
    address2=$(echo "$record" | sed -n "s/.*name='address2'[^>]*value='\([^']*\)'.*/\1/p")
    city=$(echo "$record" | sed -n "s/.*name='city'[^>]*value='\([^']*\)'.*/\1/p")
    state=$(echo "$record" | sed -n "s/.*name='state'[^>]*value='\([^']*\)'.*/\1/p")
    zip=$(echo "$record" | sed -n "s/.*name='zip'[^>]*value='\([^']*\)'.*/\1/p")
    country=$(echo "$record" | sed -n "s/.*name='country'[^>]*value='\([^']*\)'.*/\1/p")
    address_type=$(echo "$record" | sed -n "s/.*name='address_type'[^>]*value='\([^']*\)'.*/\1/p")
    home_phone=$(echo "$record" | sed -n "s/.*name='home_phone'[^>]*value='\([^']*\)'.*/\1/p")
    business_phone=$(echo "$record" | sed -n "s/.*name='business_phone'[^>]*value='\([^']*\)'.*/\1/p")
    fax_phone=$(echo "$record" | sed -n "s/.*name='fax_phone'[^>]*value='\([^']*\)'.*/\1/p")
    mobile_phone=$(echo "$record" | sed -n "s/.*name='mobile_phone'[^>]*value='\([^']*\)'.*/\1/p")
    email=$(echo "$record" | sed -n "s/.*name='email'[^>]*value='\([^']*\)'.*/\1/p")
    org_rec=$(echo "$record" | sed -n "s/.*name='org_rec'[^>]*value='\([^']*\)'.*/\1/p")
    donor_type=$(echo "$record" | sed -n "s/.*name='donor_type'[^>]*value='\([^']*\)'.*/\1/p")
    nomail=$(echo "$record" | sed -n "s/.*name='nomail'[^>]*value='\([^']*\)'.*/\1/p")
    nomail_reason=$(echo "$record" | sed -n "s/.*name='nomail_reason'[^>]*value='\([^']*\)'.*/\1/p")
    narrative=$(echo "$record" | sed -n "s/.*name='narrative'[^>]*value='\([^']*\)'.*/\1/p")
    donor_rcpt_type=$(echo "$record" | sed -n "s/.*name='donor_rcpt_type'[^>]*value='\([^']*\)'.*/\1/p")
    
    # output the CSV line with all fields
    echo "$donor_id,$first_name,$last_name,$middle_name,$suffix,$title,$salutation,$prof_title,$opt_line,$address,$address2,$city,$state,$zip,$country,$address_type,$home_phone,$business_phone,$fax_phone,$mobile_phone,$email,$org_rec,$donor_type,$nomail,$nomail_reason,$narrative,$donor_rcpt_type"
done >> "$OUTPUT_DIR/$output_file"

# clean up temporary file
rm donors_raw.xml

echo "done! donor records saved to $OUTPUT_DIR/$output_file"
