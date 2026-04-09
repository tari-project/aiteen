import os
import json
import csv
import argparse

# Function to recursively find JSON files
def find_json_files(base_directory):
    json_files = []
    for root, _, files in os.walk(base_directory):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))
    return json_files

# Function to load a JSON file and return its content along with the file name
def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f), os.path.basename(file_path)

# Recursive function to extract all keys including nested ones as key paths, along with their file and value
def extract_keys(data, json_file, parent_key=''):
    keys = {}
    for key, value in data.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            # If the value is a dict, recurse to extract nested keys
            keys.update(extract_keys(value, json_file, full_key))
        else:
            # Otherwise, store the key, the file, and the value
            keys[full_key] = (json_file, value)
    return keys

# Function to load keys and values from all English JSON files
def load_en_keys(en_json_files):
    all_keys = {}
    for json_file in en_json_files:
        en_data, json_file_name = load_json(json_file)
        all_keys.update(extract_keys(en_data, json_file_name))
    return all_keys

# Function to compare the English keys with other locale keys, considering identical values as missing
import logging

logging.basicConfig(level=logging.INFO)

def compare_keys(en_data, other_locale_data, translate_func=lambda x: x):
    # Extract nested keys from the English data
    en_keys = extract_keys(en_data, "en.json")  # Provide a placeholder for json_file
    # Extract nested keys from the locale data
    other_keys = extract_keys(other_locale_data, "locale.json")  # Provide a placeholder for json_file

    # Find keys that are missing or have the same value as in English
    missing_keys = {
        key for key, (file, en_value) in en_keys.items()
        if key not in other_keys or other_keys[key][1] == en_value
    }

    # Find extraneous keys that are present in the locale but not in English
    extraneous_keys = {
        key for key in other_keys.keys() - en_keys.keys()
    }

    return missing_keys, extraneous_keys

# Function to search for keys in all files recursively under the search path
def search_for_key_in_files(key, search_path):
    for root, _, files in os.walk(search_path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    contents = f.read()
                    if key in contents:
                        return True  # Key is found
            except:
                pass  # Skip unreadable files
    return False  # Key not found

# Function to write a CSV for English labels
def write_english_labels_csv(en_data, output_file):
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["label_key", "value", "json_file"])  # Now includes 'value'
        for label_key, (json_file, value) in en_data.items():  # Unpack value with the json_file
            writer.writerow([label_key, value, json_file])  # Write the key, value, and file

# Function to write a consolidated comparison CSV for all locales
def write_consolidated_comparison_csv(comparison_data, output_file):
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["locale", "status", "label_key", "json_file"])
        for locale, data in comparison_data.items():
            for key, (json_file, _) in data['missing_keys']:  # Adjusted for file + value
                writer.writerow([locale, "missing", key, json_file])
            for key, (json_file, _) in data['extraneous_keys']:  # Adjusted for file + value
                writer.writerow([locale, "extraneous", key, json_file])

# Function to write unused keys to a CSV file
def write_unused_keys_to_csv(unused_keys, output_file):
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["unused_key"])
        for key in unused_keys:
            writer.writerow([key])

# Unused keys function
def find_unused_keys(en_locale_path, search_base_path, output_dir):
    en_json_files = find_json_files(en_locale_path)
    all_en_keys = load_en_keys(en_json_files)
    
    unused_keys = []
    for key in all_en_keys:
        print(f"Searching for key: {key}")
        if not search_for_key_in_files(key, search_base_path):
            unused_keys.append(key)

    output_file = os.path.join(output_dir, 'unused_keys.csv')
    write_unused_keys_to_csv(unused_keys, output_file)
    print(f"Unused keys written to {output_file}")

def compare_keys_in_locales(base_path, en_path, output_dir):
    en_files = find_json_files(en_path)
    all_en_data = {}

    # Load and unnest English JSON files into key-value pairs with their files
    for en_file in en_files:
        en_data, json_file = load_json(en_file)
        all_en_data.update(extract_keys(en_data, json_file))  # Track file with key

    # Write English labels to CSV
    english_labels_output_file = os.path.join(output_dir, 'english_labels.csv')
    write_english_labels_csv(all_en_data, english_labels_output_file)

    comparison_data = {}
    other_locales = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and d != 'en']
    print(f"Comparing English keys with {len(other_locales)} other locales.")

    for locale in other_locales:
        locale_path = os.path.join(base_path, locale)
        locale_files = find_json_files(locale_path)
        locale_data = {}

        # Load and unnest locale JSON files into key-value pairs with their files
        for locale_file in locale_files:
            locale_json_data, json_file = load_json(locale_file)
            locale_data.update(extract_keys(locale_json_data, json_file))  # Track file with key

        # Compare the fully unpacked keys, treating identical values as missing
        missing_keys, extraneous_keys = compare_keys(all_en_data, locale_data, translate_func=lambda x: x)

        # Associate missing/extraneous keys with their respective JSON files
        missing_keys_with_file = [(key, all_en_data[key]) for key in missing_keys]
        extraneous_keys_with_file = [(key, locale_data[key]) for key in extraneous_keys]

        comparison_data[locale] = {
            'missing_keys': missing_keys_with_file,
            'extraneous_keys': extraneous_keys_with_file
        }

    # Write comparison results to a consolidated CSV file
    consolidated_output_file = os.path.join(output_dir, 'locale_key_comparison_consolidated.csv')
    write_consolidated_comparison_csv(comparison_data, consolidated_output_file)
    print(f"Comparison CSV written to {consolidated_output_file}")

# Main function to parse arguments and invoke appropriate functions
def main():
    parser = argparse.ArgumentParser(description="CLI tool for comparing locale JSON keys and finding unused keys.")
    parser.add_argument("mode", choices=["compare", "unused"], help="Mode of operation: 'compare' or 'unused'.")
    parser.add_argument("--en-locale-path", required=True, help="Path to the English locale directory.")
    parser.add_argument("--base-path", required=True, help="Base path for all locales (for comparison).")
    parser.add_argument("--output-dir", required=True, help="Directory to store the output CSV files.")
    parser.add_argument("--search-path", required=False, help="Path to search for unused keys (required for 'unused' mode).")

    args = parser.parse_args()

    if args.mode == "compare":
        compare_keys_in_locales(args.base_path, args.en_locale_path, args.output_dir)
    elif args.mode == "unused":
        if not args.search_path:
            print("Error: --search-path is required for 'unused' mode.")
            return
        find_unused_keys(args.en_locale_path, args.search_path, args.output_dir)

if __name__ == "__main__":
    main()
