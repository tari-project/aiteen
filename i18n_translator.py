import pandas as pd
import os
import traceback
from openai import OpenAI, OpenAIError
import json
import argparse
from dotenv import load_dotenv
load_dotenv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Translate missing locale strings using OpenAI.')
    parser.add_argument('--input-dir', default='locale_comparison',
                       help='Input directory containing comparison CSV files (default: locale_comparison)')
    parser.add_argument('--output-dir', default='locale_comparison',
                       help='Output directory for translated CSV files (default: locale_comparison)')
    return parser.parse_args()

def load_csv_files(english_path, locale_comparison_path):
    english_labels_df = pd.read_csv(english_path)
    locale_key_comparison_df = pd.read_csv(locale_comparison_path)
    return english_labels_df, locale_key_comparison_df


# Function to create the GPT-4 prompt and send a batch translation request
def gpt_translate(translation_list, locale, translate_context):
    # Map locales to the full names of their languages
    locale_to_language = {
        'en': 'English',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'cn': 'Chinese',
        'ru': 'Russian',
        'hi': 'Hindi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'tr': 'Turkish',
        'nl': 'Dutch',
        'pl': 'Polish',
        'sv': 'Swedish',
        'da': 'Danish',
        'fi': 'Finnish',
        'no': 'Norwegian',
        'cs': 'Czech',
        'hu': 'Hungarian',
        'el': 'Greek',
        'th': 'Thai',
        'vi': 'Vietnamese',
        'id': 'Indonesian',
        'ms': 'Malay',
        'fil': 'Filipino',
        'ar': 'Arabic',
        'he': 'Hebrew',
        'af': 'Afrikaans',
    }

    # Construct system prompt using f-string
    system_prompt = """
    Task:
    Translate the following short text phrases into %s, ensuring accurate and context-appropriate translations for UI elements such as button labels and section titles.

    Context:
    These phrases belong to a software platform related to cryptocurrency and blockchain. Use the following specific translations for key technical terms and jargon.
    
    Glossary of Specific Terms:
    Floor: Refers to a threshold level or minimum value.
    Current Block Time: Refers to the time the latest block was added to the blockchain.
    Seed Words: Refers to words used to recover or back up a cryptocurrency wallet.
    Miner / Auto Miner: Refers to a software component or process that mines cryptocurrency.
    GPU/CPU Mining: Refers to using the GPU or CPU to mine cryptocurrency.
    Hashrate: Refers to the processing power or speed at which a mining device can solve complex cryptographic puzzles.
    Wallet Balance: Refers to the amount of cryptocurrency held in a user's digital wallet.
    Referral Code: Refers to a unique code used to invite others and earn rewards.
    P2Pool: Refers to a decentralized peer-to-peer mining pool.
    Logs: Refers to data or files that record system activity for debugging or tracking purposes.
    Tribe/Squad Stats: Refers to statistics for a group of miners working together.
    Idle Timeout: Refers to the amount of time after which a machine is considered idle.
    Tip of Chains: Refers to the most recent block added to the blockchain.
    Monero Address: Refers to a cryptographic address used for Monero transactions.
    Airdrop Game: Refers to a game or event where users earn free cryptocurrency or tokens.
    Testnet: Refers to a simulated blockchain environment for testing purposes.
    Merge Mining: Refers to mining two different cryptocurrencies simultaneously with the same resources.
    Referral Program: Refers to a program where users invite friends and earn rewards for their participation.
    Visual Mode: Refers to a display mode that changes how information is shown visually in the interface.
    Tor: Refers to The Onion Router, a privacy-focused network for anonymous communication.

    Instructions:
    Do not translate technical terms like GPU, CPU, hash rate, or product names like Tari Universe. 
    Maintain clarity for UI elements such as button labels and headings.
    Output your result as a JSON array with the format:
    {"result": [{ "key": "<label_key>", "en": "<English value>", "translated_value": "<translated_value>", "locale": "%s" }]}}
    """ % (locale_to_language[locale], locale)


    # Prepare translation input list
    translation_input = [{"key": item['label_key'], "text": item['value']} for item in translation_list]
    print(f"Translating {len(translation_input)} phrases to {locale_to_language[locale]}...")

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(translation_input)}
            ],
            temperature=0,
            timeout=120,
        )
           # Print the raw response for debugging
        raw_result = response.choices[0].message.content

        # Check if the result is empty or malformed
        if not raw_result:
            print("Error: Empty response from GPT-4")
            return None

        # Try parsing the result
        return json.loads(raw_result)["result"]

    except OpenAIError as e:
        print(f"OpenAI API Error: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON Error: {str(e)}")
        return None



# Function to process missing translations in batches and update the DataFrame
import logging

logging.basicConfig(level=logging.INFO)

import logging

logging.basicConfig(level=logging.INFO)

def process_missing_translations(english_labels_df, locale_key_comparison_df):
    # Filter rows with missing translations
    missing_translations_df = locale_key_comparison_df[locale_key_comparison_df['status'] == 'missing']
    
    # Merge with english_labels_df to get English values corresponding to the missing label_keys
    missing_with_english_df = missing_translations_df.merge(
        english_labels_df[['label_key', 'value']],
        on='label_key',
        how='left'
    )
    
    # Group missing translations by locale
    locales = missing_with_english_df['locale'].unique()
    
    all_translations = []
    
    # Process each locale separately
    for locale in locales:
        locale_missing = missing_with_english_df[missing_with_english_df['locale'] == locale]
        translation_list = locale_missing[['label_key', 'value']].to_dict(orient='records')
        
        # Call GPT-4 to translate the batch of phrases for this locale
        translations = gpt_translate(translation_list, locale, translate_context={})

        if translations:
            print(f"Translations returned for {locale}: {translations}")
            all_translations.extend(translations)
        else:
            print(f"Warning: No translations were returned for {locale}.")
    
    # Save intermediate translations to avoid repeating the whole process
    if all_translations:
        with open('locale_comparison/intermediate_translations.json', 'w', encoding='utf-8') as f:
            json.dump(all_translations, f, ensure_ascii=False, indent=4)
            print("Saved intermediate translations to 'intermediate_translations.json'")
    
    return all_translations

# Function to update the original DataFrame with the new translations
def update_translations_in_dataframe(translations, locale_key_comparison_df):
    # Ensure that the 'translated_value' column exists
    if 'translated_value' not in locale_key_comparison_df.columns:
        locale_key_comparison_df['translated_value'] = None

    # Add columns for the original English and text lengths if missing
    if 'original_en_value' not in locale_key_comparison_df.columns:
        locale_key_comparison_df['original_en_value'] = None
    if 'en_length' not in locale_key_comparison_df.columns:
        locale_key_comparison_df['en_length'] = None
    if 'translated_length' not in locale_key_comparison_df.columns:
        locale_key_comparison_df['translated_length'] = None

    # Update DataFrame with new translations
    for translation in translations:
        label_key = translation['key']
        translated_value = translation['translated_value']
        original_en_value = translation['en']

        # Find the rows to update
        mask = (locale_key_comparison_df['label_key'] == label_key) & \
               (locale_key_comparison_df['locale'] == translation['locale'])

        if not mask.any():
            print(f"Warning: No matching row found for key '{label_key}' and locale '{translation['locale']}'")
            continue

        # Perform the updates
        locale_key_comparison_df.loc[mask, 'translated_value'] = translated_value
        locale_key_comparison_df.loc[mask, 'original_en_value'] = original_en_value
        locale_key_comparison_df.loc[mask, 'en_length'] = len(original_en_value)
        locale_key_comparison_df.loc[mask, 'translated_length'] = len(translated_value)
        locale_key_comparison_df.loc[mask, 'status'] = 'translated'

    return locale_key_comparison_df



# Save the DataFrame back to CSV
def save_updated_df(df, output_path):
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Updated file saved at: {output_path}")

# Main function to run the process
def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up paths from arguments
    english_labels_path = os.path.join(args.input_dir, 'english_labels.csv')
    locale_key_comparison_path = os.path.join(args.input_dir, 'locale_key_comparison_consolidated.csv')
    output_path = os.path.join(args.output_dir, 'translated_locale_key_comparison_consolidated.csv')
    
    english_labels_df, locale_key_comparison_df = load_csv_files(english_labels_path, locale_key_comparison_path)
    
    # Process the missing translations
    translations = process_missing_translations(english_labels_df, locale_key_comparison_df)
    
    # Update the original DataFrame with translations
    updated_locale_key_comparison_df = update_translations_in_dataframe(translations, locale_key_comparison_df)
    
    # Save the updated DataFrame
    save_updated_df(updated_locale_key_comparison_df, output_path)

if __name__ == "__main__":
    main()
