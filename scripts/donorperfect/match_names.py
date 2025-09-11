#!/usr/bin/env python3
"""
Script to match names between Leaders and Donors CSV files.
Matches first name and last name combinations and prints results to console.
"""

import csv
import sys
from pathlib import Path

def normalize_name(name):
    """normalize name for comparison - lowercase and strip whitespace"""
    if not name:
        return ""
    return name.strip().lower()

def load_leaders(file_path):
    """load leaders data and return list of (first_name, last_name, full_record) tuples"""
    leaders = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                first_name = normalize_name(row.get('First Name', ''))
                last_name = normalize_name(row.get('Last Name', ''))
                if first_name and last_name:
                    leaders.append((first_name, last_name, row))
    except FileNotFoundError:
        print(f"error: leaders file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"error reading leaders file: {e}")
        sys.exit(1)
    
    return leaders

def load_donors(file_path):
    """load donors data and return list of (first_name, last_name, full_record) tuples"""
    donors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                first_name = normalize_name(row.get('first_name', ''))
                last_name = normalize_name(row.get('last_name', ''))
                if first_name and last_name:
                    donors.append((first_name, last_name, row))
    except FileNotFoundError:
        print(f"error: donors file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"error reading donors file: {e}")
        sys.exit(1)
    
    return donors

def find_matches(leaders, donors):
    """find matching names between leaders and donors"""
    matches = []
    
    # create lookup dictionary for donors for faster matching
    donor_lookup = {}
    for first_name, last_name, record in donors:
        key = f"{first_name} {last_name}"
        if key not in donor_lookup:
            donor_lookup[key] = []
        donor_lookup[key].append(record)
    
    # find matches
    for first_name, last_name, leader_record in leaders:
        key = f"{first_name} {last_name}"
        if key in donor_lookup:
            for donor_record in donor_lookup[key]:
                matches.append({
                    'leader': leader_record,
                    'donor': donor_record,
                    'matched_name': f"{first_name.title()} {last_name.title()}"
                })
    
    return matches

def print_matches(matches):
    """print matches to console in a formatted way"""
    if not matches:
        print("no matches found between leaders and donors")
        return
    
    print(f"found {len(matches)} matching name(s):")
    print("=" * 80)
    
    for i, match in enumerate(matches, 1):
        leader = match['leader']
        donor = match['donor']
        
        print(f"\n{match['matched_name']} (match #{i})")
        print("-" * 40)
        
        # leader info
        print("leader:")
        print(f"  id: {leader.get('ID', 'n/a')}")
        print(f"  team: {leader.get('Team Name', 'n/a')}")
        print(f"  employer: {leader.get('Employer', 'n/a')}")
        print(f"  email: {leader.get('Email', 'n/a')}")
        
        # donor info
        print("donor:")
        print(f"  id: {donor.get('donor_id', 'n/a')}")
        print(f"  email: {donor.get('email', 'n/a')}")
        print(f"  donor_type: {donor.get('donor_type', 'n/a')}")

def main():
    """main function"""
    # file paths
    project_root = Path(__file__).parent.parent.parent
    leaders_file = project_root / "data" / "donor_data" / "Leaders_2025-09-11-031751.csv"
    donors_file = project_root / "data" / "donor_data" / "donors_20250911_030205.csv"
    
    print("loading leaders data...")
    leaders = load_leaders(leaders_file)
    print(f"loaded {len(leaders)} leaders")
    
    print("loading donors data...")
    donors = load_donors(donors_file)
    print(f"loaded {len(donors)} donors")
    
    print("finding matches...")
    matches = find_matches(leaders, donors)
    
    print_matches(matches)

if __name__ == "__main__":
    main()
