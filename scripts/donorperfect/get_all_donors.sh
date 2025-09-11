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

# create csv header with the new query fields
echo "donor_id,first_name,middle_name,last_name,email,address,address2,city,state,zip,country,gift_total" > "$OUTPUT_DIR/$output_file"

# pagination variables
page_start=1
page_end=500
total_processed=0

# loop through pages to get all donors using TOP with WHERE clause for pagination
last_donor_id=0
while true; do
    echo "fetching donors with donor_id > $last_donor_id..."
    
    # build sql query with simple pagination using WHERE clause
    sql_query="SELECT TOP 500 donor_id, first_name, middle_name, last_name, email, address, address2, city, state, zip, country, gift_total FROM dp WHERE donor_id > $last_donor_id ORDER BY donor_id ASC"
    
    # url encode the sql query
    encoded_sql=$(printf '%s\n' "$sql_query" | sed 's/ /%20/g; s/,/%2C/g; s/(/%28/g; s/)/%29/g; s/</%3C/g; s/>/%3E/g; s/=/=%3D/g; s/&/%26/g')
    
    # make api call - the sql query goes directly in the action parameter
    curl -s "${DP_API_URL}?apikey=${DP_API_KEY}&action=${encoded_sql}" \
      -o "donors_raw_${last_donor_id}.xml"
    
    # check if api call was successful
    if [ $? -ne 0 ]; then
        echo "error: api call failed for donor_id > $last_donor_id"
        exit 1
    fi
    
    # check if we got valid xml response
    if ! grep -q "<result>" "donors_raw_${last_donor_id}.xml"; then
        echo "error: invalid response from api for donor_id > $last_donor_id"
        echo "response content:"
        cat "donors_raw_${last_donor_id}.xml"
        exit 1
    fi
    
    # check if we got any records (if no records, we've reached the end)
    record_count=$(grep -c '<record>' "donors_raw_${last_donor_id}.xml")
    if [ "$record_count" -eq 0 ]; then
        echo "no more records found, pagination complete"
        break
    fi
    
    echo "processing $record_count records with donor_id > $last_donor_id..."
    
    # extract each record and convert to csv, also track the highest donor_id
    highest_donor_id=$last_donor_id
    sed 's/<\/record><record>/<\/record>\n<record>/g' "donors_raw_${last_donor_id}.xml" | \
    grep '<record>' | \
    while read -r record; do
        # extract field values from each record
        donor_id=$(echo "$record" | sed -n "s/.*name='donor_id'[^>]*value='\([^']*\)'.*/\1/p")
        first_name=$(echo "$record" | sed -n "s/.*name='first_name'[^>]*value='\([^']*\)'.*/\1/p")
        middle_name=$(echo "$record" | sed -n "s/.*name='middle_name'[^>]*value='\([^']*\)'.*/\1/p")
        last_name=$(echo "$record" | sed -n "s/.*name='last_name'[^>]*value='\([^']*\)'.*/\1/p")
        email=$(echo "$record" | sed -n "s/.*name='email'[^>]*value='\([^']*\)'.*/\1/p")
        address=$(echo "$record" | sed -n "s/.*name='address'[^>]*value='\([^']*\)'.*/\1/p")
        address2=$(echo "$record" | sed -n "s/.*name='address2'[^>]*value='\([^']*\)'.*/\1/p")
        city=$(echo "$record" | sed -n "s/.*name='city'[^>]*value='\([^']*\)'.*/\1/p")
        state=$(echo "$record" | sed -n "s/.*name='state'[^>]*value='\([^']*\)'.*/\1/p")
        zip=$(echo "$record" | sed -n "s/.*name='zip'[^>]*value='\([^']*\)'.*/\1/p")
        country=$(echo "$record" | sed -n "s/.*name='country'[^>]*value='\([^']*\)'.*/\1/p")
        gift_total=$(echo "$record" | sed -n "s/.*name='gift_total'[^>]*value='\([^']*\)'.*/\1/p")
        
        # output the csv line with all fields
        echo "$donor_id,$first_name,$middle_name,$last_name,$email,$address,$address2,$city,$state,$zip,$country,$gift_total"
        
        # track the highest donor_id for next iteration
        if [ "$donor_id" -gt "$highest_donor_id" ]; then
            highest_donor_id=$donor_id
        fi
    done >> "$OUTPUT_DIR/$output_file"
    
    # update last_donor_id for next iteration (get the highest from the processed records)
    last_donor_id=$(grep -o "name='donor_id'[^>]*value='[^']*'" "donors_raw_${last_donor_id}.xml" | sed "s/.*value='\([^']*\)'.*/\1/" | sort -n | tail -1)
    
    # update counters
    total_processed=$((total_processed + record_count))
    
    # clean up temporary file for this page
    rm "donors_raw_${last_donor_id}.xml"
    
    # add delay between requests to be respectful to the api
    if [ -n "$REQUEST_DELAY" ]; then
        sleep "$REQUEST_DELAY"
    fi
done

echo "pagination complete, processed $total_processed total records"

echo "done! donor records saved to $OUTPUT_DIR/$output_file"
